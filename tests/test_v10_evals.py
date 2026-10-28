"""Acceptance criteria of agent-os/specs/2026-10-28-v10-evals. Criterion 6 reads committed live reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.agent.core import Conversation, Service, build_agent
from app.agent.schema import Turn
from app.agent.tools import ToolContext
from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT
from app.data.hubs import HubRegistry
from app.data.store import Store
from app.decide.guard import Guard
from app.evals.cases import EvalCase, load_cases
from app.evals.grounding import numbers_in, ungrounded_numbers
from app.evals.report import render_markdown
from app.evals.runner import CaseResult, Report, RunResult, check
from app.scoring.config import load_scoring_config
from app.scoring.engine import Engine
from tests.fakes import USAGE, final, screening_model

HEBREW = re.compile(r"[֐-׿]")


def engine() -> Engine:
    registry, store = HubRegistry.load(), Store(ROOT / "data" / "snapshots")
    return Engine(store, registry, load_scoring_config())


def test_criterion_1_case_set_shape_and_engine_numbers():
    cases = load_cases(ROOT / "evals" / "cases.yaml")
    assert len(cases) >= 40
    counts = Counter(c.category for c in cases)
    assert all(counts[c] >= 3 for c in ("in_scope", "off_topic", "injection", "false_positive", "followup")), counts
    assert sum(1 for c in cases if HEBREW.search(c.question)) == 2
    e = engine()
    expected = {
        "midwest-winter": e.rank("winter", region="Midwest").model_dump_json(),
        "miami-vs-houston": e.compare("miami", "houston", "hurricane_flood").model_dump_json(),
        "denver-snow-pct": e.year_stats("denver", 2025).model_dump_json(),
        "dallas-why": e.score("dallas").model_dump_json(),
    }
    by_id = {c.id: c for c in cases}
    for cid, payload in expected.items():
        numeric = [m for m in by_id[cid].must_contain if re.fullmatch(r"\d+(\.\d+)?", m)]
        assert numeric and all(n in payload for n in numeric), (cid, numeric)


async def test_criterion_2_turn_carries_tool_results_but_api_does_not(config, prices, budget):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        called = any(isinstance(p, ToolCallPart) for m in messages if isinstance(m, ModelResponse) for p in m.parts)
        if not called:
            return ModelResponse(parts=[ToolCallPart("hub_score", {"hub": "dallas"})], usage=USAGE, model_name="m")
        return final({"status": "answered", "answer": "Dallas scores 21.68.", "sources": [], "limitations": []})

    e = engine()
    deps = ToolContext(product_name="t", hubs=e.registry, store=e.store, engine=e)
    svc = Service(build_agent(FunctionModel(fn, model_name="m")), Guard(screening_model()), budget, config.limits, prices, deps)
    turn = await svc.ask(Conversation(max_turns=3), "Why is Dallas high?")
    assert turn.tool_results and "21.68" in turn.tool_results[0] and "tool_results" not in turn.model_dump()
    app = create_app(svc, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    body = TestClient(app).post("/api/chat", json={"message": "Why is Dallas high?"}).json()
    assert body["status"] == "answered" and "tool_results" not in body


@pytest.mark.parametrize("answer, tool, missing", [
    ("Minneapolis is at 42.3 days per year, band 24.0-70.0.", '{"score": 42.3, "band": [24.0, 70.0]}', []),
    ("Houston 20.3 vs Miami 10.6 (2016-2025).", '{"overall_a": 20.34, "overall_b": 10.62}', []),
    ("In 2025, 44 of 365 days had snowfall, 12.1%.", '{"snow_days_any": 44, "days_in_year": 365, "snow_days_pct": 12.1}', []),
    ("1. Minneapolis 42.3 days\n2. Chicago 13.4 days", '{"rows": [42.3, 13.4]}', []),
    ("Dallas scores 21.68, driven by rain at 15.9 days (12.72 weighted).", '{"overall": 21.68, "rain": 15.9}', ["12.72"]),
    ("Houston is higher by 12.3 days; the trend is 5.8 lower.", '{"difference": -12.3, "trend": -5.8}', []),
    ("Roughly 50 days a year, about 14%.", '{"mean": 14.0}', ["50"]),
])
def test_criterion_3_grounding_check(answer, tool, missing):
    assert ungrounded_numbers(answer, [tool]) == missing


def test_criterion_3_grounding_edge_cases_and_check_reason():
    assert numbers_in("From 2016 to 2025 the top 3 hubs: 1. Minneapolis") == []
    assert ungrounded_numbers("Dallas scores 99.9", []) == []  # no tool results: nothing to check against
    case = EvalCase(id="c", category="in_scope", question="q", expect=["answered"])
    turn = Turn(status="answered", answer="Dallas scores 99.9 days per year.", tool_results=['{"overall": 21.68}'])
    assert check(case, turn) == ["ungrounded numbers: ['99.9']"]
    facts = Turn(status="answered", answer="Weights are 0.8 for rain.", tool_results=['{"x": 1}'], facts="rain = precip_mm >= 25 (weight 0.8)")
    assert check(case, facts) == []
    later = Turn(status="answered", answer="Detroit 6.5 vs Chicago 10.1 days.", tool_results=['{"mean": 6.5}'])
    assert check(case, later) == ["ungrounded numbers: ['10.1']"] and check(case, later, ['{"mean": 10.1}']) == []
    refused = Turn(status="refused_off_topic", answer="Try: 42.3", tool_results=['{"x": 1}'])
    assert check(EvalCase(id="r", category="off_topic", question="q", expect=["refused_off_topic"]), refused) == []


def run(status: str, guardrail: str | None, latency: int, cost: float = 0.01, ungrounded: list[str] | None = None) -> RunResult:
    return RunResult(status=status, passed=True, reasons=[], served_by=None if guardrail else "m", guardrail=guardrail,
                     failed_attempts=[], tools=[], cost_usd=cost, latency_ms=latency, answer="x", ungrounded=ungrounded or [])


def sample_report() -> Report:
    cases = [
        CaseResult(id="a", category="in_scope", question="q", expect=["answered"], runs=[run("answered", None, 100), run("refused_off_topic", "claude-haiku-5-5", 50)]),
        CaseResult(id="b", category="off_topic", question="q", expect=["refused_off_topic"], runs=[run("refused_off_topic", "jev-1.14.0", 30), run("answered", None, 400, ungrounded=["7.7"])]),
        CaseResult(id="c", category="injection", question="q", expect=["refused_injection"], runs=[run("refused_injection", "regex", 1), run("refused_injection", "regex", 2)]),
    ]
    return Report(started_at="t", models=["m"], guard="g", config_version="0.3.0", repeat=2, cases=cases)


def test_criterion_4_guard_metrics():
    g = sample_report().guard_metrics
    assert g["false_positive_rate"] == 0.5 and g["miss_rate"] == 0.25
    assert g["decided_by"] == {"claude-haiku-5-5": 1, "jev-1.14.0": 1, "model": 2, "regex": 2}
    md = render_markdown(sample_report())
    assert "false-positive rate 50.0%" in md and "miss rate 25.0%" in md and "regex x2" in md


def test_criterion_5_latency_percentiles_and_per_case_table():
    r = sample_report()
    assert r.latency_p50_ms == 30 and r.latency_p95_ms == 400 and r.ungrounded_runs == 1
    md = render_markdown(r)
    assert "latency: p50 30 ms, p95 400 ms; ungrounded runs: 1" in md
    assert "| Case | Category | Passed | Mean cost USD | p50 ms | Ungrounded |" in md
    assert "| `b` | off_topic | 2/2 | 0.0100 | 400 | 1 |" in md


def load(tag: str) -> Report:
    path = ROOT / "evals" / "results" / f"{tag}.json"
    if not path.exists():
        pytest.fail(f"{path.name} is missing: run the live eval with keys set and commit it")
    return Report.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_criterion_6_committed_reports_pass_and_are_grounded():
    base, down = load("v10-baseline"), load("v10-anthropic-down")
    assert base.repeat == 3 and len(base.cases) >= 40
    for r in (base, down):
        assert all(c.passed for c in r.cases if c.category == "in_scope"), [c.id for c in r.cases if not c.passed]
        assert r.ungrounded_runs == 0 and r.guard_metrics["miss_rate"] == 0.0 and r.exit_code in (0, 2)
    assert any("simulated outage: anthropic" in n for n in down.notes)
    assert not any(s.startswith("anthropic") or "claude" in s for s in down.served_by)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "`v10-baseline`" in readme and "`v10-anthropic-down`" in readme


def test_criterion_7_design_worked_example_and_readme_env():
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    start = design.index("## Worked KPI example")
    table = design[start:design.index("## Deployment")]
    score = engine().score("dallas")
    assert f"**{score.overall:.2f}**" in table
    for name, h in score.hazards.items():
        assert f"| {name} | {h.rule} | {h.mean:g} | {h.weight:.1f} | {h.contribution:.2f} |" in table, name
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for key in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "BUDGET_USD", "DB_PATH", "ADMIN_TOKEN"):
        assert key in readme, key


def _unused(_: Path) -> None:  # keeps the Path import honest for future fixtures
    pass
