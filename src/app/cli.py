"""CLI: `agent serve`, `agent chat`, `agent eval`. Composition root for the whole app."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx2
import typer
from dotenv import load_dotenv

from app.agent import prompts
from app.agent.core import Conversation, Service, build_agent
from app.agent.tools import ToolContext
from app.api.app import create_app
from app.api.ratelimit import RateLimiter
from app.api.sessions import SessionStore
from app.config import CONFIG_DIR, ROOT, AgentConfig, Settings, load_agent_config, load_prices
from app.data.hubs import HubRegistry
from app.data.ingest import ingest as ingest_history
from app.data.nws import NWSClient
from app.data.openmeteo import OpenMeteoClient
from app.data.snapshot import Manifest
from app.data.store import Store
from app.decide.guard import Guard, build_guard_model, offline_guard_model
from app.evals.cases import load_cases
from app.evals.report import render_markdown
from app.evals.runner import run_all
from app.llm.budget import Budget
from app.llm.models import build_chain, retrying_http_client, without_vendors
from app.scoring.config import load_scoring_config
from app.scoring.engine import Engine

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
cli = typer.Typer(no_args_is_help=True, add_completion=False)
log = logging.getLogger(__name__)
TEST_FLAG = typer.Option(False, "--test", help="offline TestModel: no key, no spend")
QUESTION = typer.Argument(None)
DOWN_OPT = typer.Option([], help="vendor prefix to drop from the chain, e.g. anthropic (outage simulation)")
NOTE_OPT = typer.Option([], help="free-text note recorded in the report")
HUB_OPT = typer.Option([], "--hub", help="hub id to ingest (repeatable); default: every hub")
CASES_OPT = typer.Option(None, help="case file; default evals/cases.yaml, or evals/smoke.yaml with --test")


@dataclass
class App:
    settings: Settings
    config: AgentConfig
    service: Service
    budget: Budget
    model_names: list[str]
    guard_name: str
    store: Store | None = None


def compose(*, model_mode: str | None = None, down: list[str] | None = None) -> App:
    """Build everything from .env + config. `down` drops models from the chain to simulate a vendor outage."""
    load_dotenv()
    settings = Settings()
    if model_mode:
        settings.model_mode = model_mode
    config = load_agent_config()
    prices = load_prices()
    chain = build_chain(without_vendors(config.models.chain, down), settings, config.models)
    if settings.model_mode == "test":
        guard_model = offline_guard_model()
        guard_name = "test"
    else:
        decision = None
        if settings.key_for(config.models.guard_decision):
            decision = build_chain([config.models.guard_decision], settings, config.models).model
        fallback = build_chain([config.models.guard_fallback], settings, config.models).model
        guard_model = build_guard_model(decision, fallback, config.models.guard_confidence)
        guard_name = (f"{config.models.guard_decision} → " if decision else "") + config.models.guard_fallback
    budget = Budget(settings.db_path, settings.budget_usd)
    registry = HubRegistry.load()
    snapshot_dir = snapshot_path(settings.snapshot_dir)
    store = Store.open_if_present(snapshot_dir)
    if store is None:
        log.warning("no snapshot at %s: historical data unavailable until `agent ingest` runs", snapshot_dir)
    if settings.model_mode == "test":  # offline: live calls fail fast and degrade, never touch the network
        live_http = httpx2.AsyncClient(transport=httpx2.MockTransport(lambda r: httpx2.Response(503, json={"title": "test mode"})))
    else:
        live_http = retrying_http_client(
            attempts=config.models.retry_attempts, timeout_s=config.models.timeout_s, max_wait_s=config.models.retry_max_wait_s
        )
    engine = Engine(store, registry, load_scoring_config()) if store else None
    deps = ToolContext(
        product_name=config.name, hubs=registry, store=store, nws=NWSClient(live_http, settings.nws_user_agent), engine=engine
    )
    service = Service(build_agent(chain.model), Guard(guard_model), budget, config.limits, prices, deps)
    return App(settings, config, service, budget, chain.names, guard_name, store)


def default_cases(test: bool) -> Path:
    """The live set asserts facts in the wording; the smoke set only statuses and tools (test-mode answers are canned)."""
    return ROOT / "evals" / ("smoke.yaml" if test else "cases.yaml")


def snapshot_path(p: Path) -> Path:
    return p if p.is_absolute() else ROOT / p


@cli.command()
def serve(host: str = "0.0.0.0", port: int | None = None, test: bool = TEST_FLAG) -> None:
    """Run the web chat and JSON API."""
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = compose(model_mode="test" if test else None)
    web = create_app(
        app.service,
        SessionStore(max_turns=app.config.limits.max_turns, ttl_s=app.config.limits.session_ttl_s),
        app.budget,
        model_names=app.model_names,
        data=app.store.summary() if app.store else None,
        guard_name=app.guard_name,
        limiter=RateLimiter(per_ip_per_hour=app.config.limits.per_ip_per_hour, global_per_day=app.config.limits.global_per_day),
        admin_token=app.settings.admin_token,
    )
    uvicorn.run(web, host=host, port=port or app.settings.port)


@cli.command()
def chat(question: list[str] | None = QUESTION, test: bool = TEST_FLAG) -> None:
    """One question, or an interactive loop when none is given."""
    app = compose(model_mode="test" if test else None)
    conv = Conversation(max_turns=app.config.limits.max_turns)

    async def one(q: str) -> None:
        turn = await app.service.ask(conv, q)
        meta = [turn.status, turn.served_by or turn.guardrail or "", f"{turn.cost_usd:.4f} USD", f"{turn.latency_ms} ms"]
        if turn.failed_attempts:
            meta.append("fallback after " + ", ".join(turn.failed_attempts))
        typer.echo(turn.answer)
        typer.secho(" · ".join(m for m in meta if m), fg="bright_black")

    if question:
        asyncio.run(one(" ".join(question)))
        return
    typer.echo("Interactive chat; empty line to quit.")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        asyncio.run(one(q))


@cli.command("eval")
def eval_cmd(
    cases: Path | None = CASES_OPT,
    repeat: int = typer.Option(1, min=1),
    out: Path = ROOT / "evals" / "results",
    tag: str = "latest",
    test: bool = TEST_FLAG,
    down: list[str] = DOWN_OPT,
    note: list[str] = NOTE_OPT,
) -> None:
    """Run evals/cases.yaml, write evals/results/<tag>.{json,md}, exit 0 pass / 1 fail / 2 flaky."""
    app = compose(model_mode="test" if test else None, down=down)
    loaded = load_cases(cases or default_cases(test))
    notes = list(note) + ([f"simulated outage: {', '.join(down)}"] if down else [])
    report = asyncio.run(
        run_all(
            app.service, loaded, repeat=repeat, models=app.model_names, guard=app.guard_name,
            config_version=app.config.version, max_turns=app.config.limits.max_turns, notes=notes,
            prompt_version=prompts.PROMPT_VERSION,
        )
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{tag}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (out / f"{tag}.md").write_text(render_markdown(report), encoding="utf-8")
    typer.echo(render_markdown(report))
    raise typer.Exit(code=report.exit_code)


@cli.command()
def ingest(start: str = "2016-01-01", end: str = "2025-12-31", hub: list[str] = HUB_OPT, out: Path | None = None) -> None:
    """Fetch daily history for every hub from Open-Meteo and write the committed snapshot (run once, commit)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    settings, config, registry = Settings(), load_agent_config(), HubRegistry.load()
    out_dir = snapshot_path(out or settings.snapshot_dir)

    async def run() -> Manifest:
        http = retrying_http_client(attempts=config.models.retry_attempts, timeout_s=60, max_wait_s=config.models.retry_max_wait_s)
        async with http:
            return await ingest_history(
                registry, OpenMeteoClient(http), date.fromisoformat(start), date.fromisoformat(end), out_dir, hub_ids=hub or None
            )

    m = asyncio.run(run())
    typer.echo(f"snapshot written to {out_dir}: {m.hubs} hubs, {m.rows} rows, {m.start}..{m.end}")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to a legacy code page; reports use UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    cli()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["CONFIG_DIR", "cli", "compose", "main"]
