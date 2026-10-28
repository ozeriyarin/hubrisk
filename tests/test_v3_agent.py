"""Acceptance criteria of agent-os/specs/2026-10-28-v3-agent, one test per criterion. 7, 8 and 10 read committed reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelRequest, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from typer.testing import CliRunner

from app import cli as cli_module
from app.agent import prompts
from app.agent.core import Conversation, Service, build_agent, data_instructions
from app.agent.tools import ToolContext, build_toolset
from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT, load_agent_config
from app.data.hubs import HubRegistry
from app.data.store import Store
from app.decide.guard import Guard, offline_guard_model
from app.evals.cases import load_cases
from app.evals.runner import Report
from app.scoring.config import load_scoring_config
from app.scoring.engine import Engine
from tests.fakes import USAGE, final, screening_model

RESULTS = ROOT / "evals" / "results"
SAMPLE_QUESTIONS = {
    "Which hubs in the Midwest are most exposed to winter disruption?": "rank_hubs",
    "Compare Miami and Houston in terms of hurricane and flood exposure.": "compare_hubs",
    "What percentage of days in Denver last year had snowfall?": "hub_year_stats",
    "Why is the Dallas hub's weather disruption risk high?": "hub_score",
}


def real_deps() -> ToolContext:
    registry, store = HubRegistry.load(), Store(ROOT / "data" / "snapshots")
    return ToolContext(product_name="hubrisk", hubs=registry, store=store, engine=Engine(store, registry, load_scoring_config()))


def latest_baseline() -> Report:
    """The newest v<N>-baseline report: prompt changes ship a new one, and it must match the committed prompt."""
    files = sorted(RESULTS.glob("v*-baseline.json"), key=lambda p: int(p.name[1:].split("-")[0]))
    if not files:
        pytest.fail("no v<N>-baseline.json report is committed")
    return Report.model_validate(json.loads(files[-1].read_text(encoding="utf-8")))


def report(tag: str) -> Report:
    path = RESULTS / f"{tag}.json"
    if not path.exists():
        pytest.fail(f"{path.name} is missing: run `uv run agent eval` for this tag with keys set, then commit it")
    return Report.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_criterion_1_instructions_cover_every_tool_and_the_rules():
    text = prompts.INSTRUCTIONS
    for name in build_toolset().tools:
        assert name in text, f"INSTRUCTIONS does not mention tool {name}"
    for phrase in ("unit", "band", "trend", "proxy", "NotFound", "never", "limitations", "sources"):
        assert phrase in text, phrase


async def test_criterion_2_dynamic_instructions_from_deps():
    deps = real_deps()
    text = data_instructions(deps)
    assert "2016-01-01" in text and "2025-12-31" in text and "'last year' means 2025" in text
    assert f"Scoring version {deps.engine.config.version}" in text and "Midwest: chicago" in text and "winter" in text
    assert "snow = snow_cm >= 5" in text
    bare = data_instructions(ToolContext(product_name="t", hubs=deps.hubs))
    assert "NOT loaded" in bare and "current_conditions" in bare
    seen: list[str] = []

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(messages[0].instructions or "")
        return final({"status": "answered", "answer": "ok", "sources": [], "limitations": []})

    result = await build_agent(FunctionModel(fn, model_name="m")).run("hi", deps=deps)
    assert result.output.status == "answered" and "2016-01-01" in seen[0] and "Rules:" in seen[0]


async def test_criterion_3_scope_description_and_offline_guard_on_the_smoke_set():
    scope = prompts.SCOPE_DESCRIPTION.lower()
    for word in ("hub", "region", "hazard", "rank", "compar", "year", "alert", "forecast"):
        assert word in scope, word
    guard = Guard(offline_guard_model())
    for case in load_cases(ROOT / "evals" / "smoke.yaml"):
        if case.category == "injection" or prompts.intro_reply(case.question):
            continue
        previous = case.prior_turns[-1] if case.prior_turns else None
        label = (await guard.screen(case.question, previous=previous)).label
        expected = "off_topic" if case.category == "off_topic" else "in_scope"
        assert label == expected, f"{case.id}: {label}"
    assert (await guard.screen("And the year before?")).label == "off_topic"
    assert (await guard.screen("And the year before?", previous="Denver snowfall days?")).label == "in_scope"


def test_criterion_4_live_case_set_shape():
    cases = load_cases(ROOT / "evals" / "cases.yaml")
    counts = Counter(c.category for c in cases)
    for cat in ("in_scope", "off_topic", "injection", "false_positive", "followup"):
        assert counts[cat] >= 3, counts
    by_question = {c.question: c for c in cases}
    for question, tool in SAMPLE_QUESTIONS.items():
        case = by_question[question]
        assert case.tools == [tool] and case.must_contain and case.expect == ["answered"], case.id
    assert all(c.prior_turns for c in cases if c.category == "followup")


def test_criterion_5_smoke_set_and_cli_defaults(tmp_path: Path, monkeypatch):
    smoke = load_cases(ROOT / "evals" / "smoke.yaml")
    assert {c.category for c in smoke} >= {"in_scope", "off_topic", "injection", "false_positive", "followup"}
    assert not any(c.must_contain for c in smoke if not prompts.intro_reply(c.question))  # intro answers are fixed text
    assert cli_module.default_cases(test=True).name == "smoke.yaml" and cli_module.default_cases(test=False).name == "cases.yaml"
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ledger.db"))
    result = CliRunner().invoke(cli_module.cli, ["eval", "--test", "--tag", "smoke", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    ids = {c["id"] for c in json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))["cases"]}
    assert {"fu-year-before", "greet-hi"} <= ids


async def test_criterion_6_scripted_model_through_service_with_real_engine(config, prices, budget):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        called = any(isinstance(p, ToolCallPart) for m in messages if isinstance(m, ModelResponse) for p in m.parts)
        if not called:
            return ModelResponse(parts=[ToolCallPart("hub_score", {"hub": "dallas"})], usage=USAGE, model_name="m")
        returned = [p for m in messages if isinstance(m, ModelRequest) for p in m.parts if getattr(p, "tool_name", None) == "hub_score"]
        lead = returned[0].content.contributions[0][0]
        return final({"status": "answered", "answer": f"Dallas is high mainly because of {lead}.",
                      "sources": ["hub_score", "scoring 1.0.0"], "limitations": ["thresholds are assumptions"]})

    svc = Service(build_agent(FunctionModel(fn, model_name="m")), Guard(screening_model()), budget, config.limits, prices, real_deps())
    turn = await svc.ask(Conversation(max_turns=3), "Why is the Dallas hub's weather disruption risk high?")
    assert turn.status == "answered" and turn.tools_used == ["hub_score"] and "rain" in turn.answer
    assert turn.sources == ["hub_score", "scoring 1.0.0"] and turn.limitations == ["thresholds are assumptions"]


def test_criterion_7_baseline_report_is_committed_and_healthy():
    r = latest_baseline()
    assert r.config_version == load_agent_config().version and r.prompt_version == prompts.PROMPT_VERSION
    assert r.exit_code in (0, 2), r.exit_code
    passed = sum(c.passed for c in r.cases)
    assert passed / len(r.cases) >= 0.9, f"{passed}/{len(r.cases)}"
    assert all(c.passed for c in r.cases if c.category == "in_scope"), [c.id for c in r.cases if c.category == "in_scope" and not c.passed]


def test_criterion_8_anthropic_down_report_proves_fallback():
    r = report("v3-anthropic-down")
    assert any("simulated outage: anthropic" in n for n in r.notes)
    served = {run.served_by for c in r.cases for run in c.runs if run.served_by}
    assert served and not any(s.startswith("anthropic") or "claude" in s.lower() for s in served), served
    assert all(c.passed for c in r.cases if c.category == "in_scope")


def test_criterion_9_chat_page_shows_sources_and_limitations(service, budget):
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    page = TestClient(app).get("/").text
    assert "j.sources" in page and "j.limitations" in page


def test_criterion_10_prompt_version_recorded():
    assert re.fullmatch(r"\d+\.\d+\.\d+", prompts.PROMPT_VERSION)
    assert latest_baseline().prompt_version == prompts.PROMPT_VERSION
