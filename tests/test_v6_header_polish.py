"""Acceptance criteria of agent-os/specs/2026-10-28-v6-header-polish."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT

TAGLINE = "Weather disruption risk across the US hub network"


def header_of(page: str) -> str:
    return re.search(r"<header>(.*?)</header>", page, re.DOTALL).group(1)


def test_criterion_1_header_shows_name_and_tagline(service, budget):
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    page = TestClient(app).get("/").text
    header = header_of(page)
    assert "HubRisk agent" in header and TAGLINE in header
    assert "models" not in header and "guard" not in header and "version" not in header
    status_line = next(line for line in page.splitlines() if "getElementById('status').textContent" in line)
    assert "h.models" not in status_line and "h.version" not in status_line and "h.guard" not in status_line


def test_criterion_2_unhealthy_state_is_visible_without_models():
    page = (ROOT / "src" / "app" / "api" / "static" / "index.html").read_text(encoding="utf-8")
    status_line = next(line for line in page.splitlines() if "getElementById('status').textContent" in line)
    assert "h.status === 'ok'" in status_line and "'status: ' + h.status" in status_line


def test_criterion_3_docs_and_roadmap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "HubRisk agent" in readme and TAGLINE in readme
    roadmap = (ROOT / "agent-os" / "product" / "roadmap.md").read_text(encoding="utf-8")
    assert "**v6 header polish**" in roadmap and "**v7 alerts**" in roadmap and "**v8 voice**" in roadmap


def test_criterion_4_brevity_follow_up():
    import json

    from app.agent import prompts
    from app.evals.cases import EvalCase, load_cases
    from app.evals.runner import Report

    assert prompts.PROMPT_VERSION == "1.3.0" and "2-4 sentences" in prompts.INSTRUCTIONS
    assert "Do not restate threshold rules" in prompts.INSTRUCTIONS and "under 100 words" in prompts.INSTRUCTIONS
    assert "offer of the full breakdown" in prompts.INSTRUCTIONS and "only when the user asks" in prompts.INSTRUCTIONS
    from app.agent.schema import Turn
    from app.evals.runner import check
    from app.scoring.models import HazardScore, RankingRow

    assert "trend_unit" in HazardScore.model_fields and "trend_unit" in RankingRow.model_fields
    capped = EvalCase(id="w", category="x", question="q", expect=["answered"], max_words=3)
    assert check(capped, Turn(status="answered", answer="one two three four")) == ["answer is 4 words, over 3"]
    assert {c.id: c.max_words for c in load_cases(ROOT / "evals" / "cases.yaml")}["dallas-why"] == 110
    assert EvalCase(id="c", category="x", question="q", expect=["answered"]).max_chars == 1000
    path = ROOT / "evals" / "results" / "v6-baseline.json"
    assert path.exists(), "run `uv run agent eval --tag v6-baseline` with keys set and commit it"
    r = Report.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert r.prompt_version == "1.3.0" and all(c.passed for c in r.cases if c.category == "in_scope")
    limits = {c.id: c.max_chars for c in load_cases(ROOT / "evals" / "cases.yaml")}
    assert not [(c.id, len(run.answer)) for c in r.cases for run in c.runs if len(run.answer) > limits.get(c.id, 1000)]


def test_criterion_5_sources_collapsed(service, budget):
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    page = TestClient(app).get("/").text
    toggle = page.index("createElement('details')")
    assert page.index("'Sources: '") > toggle and page.index("'Limitations: '") < toggle
