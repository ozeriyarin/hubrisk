"""Acceptance criteria of agent-os/specs/2026-10-28-v4-deploy. 4, 5 and 7 check committed records of live steps."""

from __future__ import annotations

import re
from pathlib import Path

import httpx2
import yaml
from typer.testing import CliRunner

from app import cli as cli_module
from app.cli import check_chat, check_health, verification_record
from app.config import ROOT, Settings
from app.llm.budget import Budget

HEALTH_OK = {
    "status": "ok", "version": "0.1.0", "models": ["anthropic:claude-sonnet-5-5", "google-gla:gemini-2.5-flash"],
    "guard": "typesafe:jev-latest -> anthropic:claude-haiku-5-5",
    "data": {"hubs": 15, "start": "2016-01-01", "end": "2025-12-31", "rows": 54795, "fetched_at": "x"},
}
CHAT_OK = {"status": "answered", "answer": "I rank hubs.", "served_by": "claude-sonnet-5-5", "tools_used": ["about"], "latency_ms": 900, "cost_usd": 0.01}


def test_criterion_1_render_blueprint():
    svc = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))["services"][0]
    assert "uv sync --frozen --no-dev" in svc["buildCommand"] and svc["startCommand"] == "uv run agent serve --port $PORT"
    assert svc["healthCheckPath"] == "/health" and svc["runtime"] == "python"
    env = {e["key"]: e for e in svc["envVars"]}
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "TYPESAFE_API_KEY"):
        assert env[key].get("sync") is False, key
    assert env["ADMIN_TOKEN"].get("generateValue") is True
    assert env["BUDGET_USD"]["value"] and env["DB_PATH"]["value"] and "hubrisk" in env["NWS_USER_AGENT"]["value"]
    assert env["PYTHON_VERSION"]["value"].startswith("3.12")


def test_criterion_2_port_from_env_and_ledger_parent_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORT", "4321")
    assert Settings(_env_file=None).port == 4321
    budget = Budget(tmp_path / "nested" / "deeper" / "ledger.db", cap_usd=1.0)
    assert budget.month_to_date() == 0.0 and (tmp_path / "nested" / "deeper" / "ledger.db").exists()


def test_criterion_3_verify_command_offline(monkeypatch):
    assert check_health(HEALTH_OK) == [] and check_chat(CHAT_OK) == []
    assert check_health({**HEALTH_OK, "models": ["test"]}) and check_health({**HEALTH_OK, "data": None})
    assert check_chat({"status": "unavailable", "answer": "down"})
    record = verification_record("https://x.onrender.com", HEALTH_OK, CHAT_OK)
    assert re.search(r"Verified \d{4}-\d{2}-\d{2} at https://x.onrender.com", record)
    assert "claude-sonnet-5-5" in record and "900 ms" in record and "15 hubs" in record
    calls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/health":
            return httpx2.Response(200, json=HEALTH_OK)
        return httpx2.Response(200, json=CHAT_OK if request.method == "POST" else {})

    real = cli_module.retrying_http_client

    def fake_client(**kw):
        return real(attempts=1, timeout_s=5, max_wait_s=0, wrapped=httpx2.MockTransport(handler))

    monkeypatch.setattr(cli_module, "retrying_http_client", fake_client)
    result = CliRunner().invoke(cli_module.cli, ["verify", "https://x.onrender.com/"])
    assert result.exit_code == 0, result.output
    assert calls == ["GET /health", "POST /api/chat"] and "Verified" in result.output

    def broken(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"status": "ok", "models": ["test"], "data": None} if request.url.path == "/health" else CHAT_OK)

    monkeypatch.setattr(cli_module, "retrying_http_client", lambda **kw: real(attempts=1, timeout_s=5, max_wait_s=0, wrapped=httpx2.MockTransport(broken)))
    result = CliRunner().invoke(cli_module.cli, ["verify", "https://x.onrender.com"])
    assert result.exit_code == 1 and "expected real models" in result.output


def deployment_section() -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("## Deployment")
    return readme[start:]


def test_criterion_4_live_health_recorded_in_readme():
    section = deployment_section()
    assert re.search(r"https://[a-z0-9-]+\.onrender\.com", section), "no live URL recorded"
    assert re.search(r"Verified \d{4}-\d{2}-\d{2} at https://", section), "no dated verification record"
    assert "15 hubs" in section


def test_criterion_5_readme_deployment_section():
    section = deployment_section()
    for phrase in ("/health", "/api/chat", "agent verify", "15 min", "cold start", "ephemeral", "BUDGET_USD", "Anthropic Console", "push to main"):
        assert phrase in section, phrase


def test_criterion_6_design_deployment_section():
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    start = design.index("## Deployment")
    section = design[start:]
    for phrase in ("uv sync --frozen --no-dev", "agent serve", "/health", "sync: false", "ephemeral", "production"):
        assert phrase in section, phrase


def test_criterion_7_session_transcript_committed():
    folder = ROOT / "docs" / "ai-session"
    assert (folder / "README.md").exists(), "docs/ai-session/README.md index is missing"
    transcripts = [p for p in folder.iterdir() if p.is_file() and p.name != "README.md"]
    assert any(p.stat().st_size > 100_000 for p in transcripts), [p.name for p in transcripts]
    index = (folder / "README.md").read_text(encoding="utf-8")
    assert "redact" in index.lower() and "export" in index.lower() and "API key" in index


def test_criterion_8_ci_and_roadmap():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    runs = " ".join(step.get("run", "") for job in ci["jobs"].values() for step in job["steps"])
    assert "ruff check" in runs and "pytest" in runs and "agent eval --test" in runs
    roadmap = (ROOT / "agent-os" / "product" / "roadmap.md").read_text(encoding="utf-8")
    assert "**v4 deploy**" in roadmap and "~~v4 deploy~~" in roadmap
