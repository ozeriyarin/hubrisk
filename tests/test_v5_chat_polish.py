"""Acceptance criteria of agent-os/specs/2026-10-28-v5-chat-polish. Criterion 8 reads the committed baseline report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app import cli as cli_module
from app.agent import prompts
from app.agent.core import Conversation, Service
from app.agent.schema import AnswerOut, Turn
from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT
from app.evals.cases import EvalCase, load_cases
from app.evals.runner import Report, check
from app.llm.budget import Budget

PAGE = (ROOT / "src" / "app" / "api" / "static" / "index.html").read_text(encoding="utf-8")


def test_criterion_1_inline_svg_favicon():
    assert 'rel="icon"' in PAGE and "data:image/svg+xml" in PAGE
    assert ".ico" not in PAGE and "favicon" not in PAGE.lower().replace("data:image", "")


def test_criterion_2_answer_cap_and_brevity_rule():
    assert AnswerOut.model_fields["answer"].metadata[-1].max_length == 2000
    with pytest.raises(ValueError):
        AnswerOut(status="answered", answer="x" * 2001)
    text = prompts.INSTRUCTIONS
    assert "Be brief" in text and "sentences" in text and "lead with the ranking or the number" in text
    assert "more detail only when the user asks" in text


def test_criterion_3_eval_length_check():
    case = EvalCase(id="c", category="in_scope", question="q", expect=["answered"])
    assert case.max_chars == 1000  # 1200 in v5, tightened by the v6 follow-up
    assert check(case, Turn(status="answered", answer="short")) == []
    reasons = check(case, Turn(status="answered", answer="x" * 1001))
    assert reasons == ["answer is 1001 chars, over 1000"]
    assert check(EvalCase(id="c", category="x", question="q", expect=["answered"], max_chars=5), Turn(status="answered", answer="123456"))
    for c in load_cases(ROOT / "evals" / "cases.yaml"):
        if c.id in ("midwest-winter", "miami-vs-houston", "denver-snow-pct", "dallas-why"):
            assert c.max_chars == 1000


@pytest.mark.parametrize("message", ["hi", "Hello!", "hey there", "what can you do?", "What can you help me with", "help", "Who are you?", "good morning"])
def test_criterion_4_intro_matches_greetings(message):
    reply = prompts.intro_reply(message)
    assert reply and all(q in reply for q in prompts.EXAMPLE_QUESTIONS)


@pytest.mark.parametrize("message", [
    "hi, which hub is worst for snow?", "Which hubs in the Midwest are most exposed to winter disruption?",
    "help me compare Miami and Houston", "What can you tell me about Denver?", "Write me a poem about the sea.",
])
def test_criterion_4_intro_ignores_real_questions(message):
    assert prompts.intro_reply(message) is None


async def test_criterion_5_intro_turn_is_free(service: Service, budget: Budget):
    conv = Conversation(max_turns=3)
    turn = await service.ask(conv, "hi")
    assert turn.status == "answered" and turn.guardrail == "intro" and turn.tools_used == [] and turn.cost_usd == 0
    assert turn.sources == ["intro"] and all(q in turn.answer for q in prompts.EXAMPLE_QUESTIONS)
    assert budget.stats().calls == 0 and budget.stats().recent == [] and conv.last_question == "hi"


def test_criterion_6_greeting_cases_in_both_sets(tmp_path: Path, monkeypatch):
    for name in ("cases.yaml", "smoke.yaml"):
        by_id = {c.id: c for c in load_cases(ROOT / "evals" / name)}
        for cid in ("greet-hi", "greet-what-can-you-do"):
            assert by_id[cid].expect == ["answered"] and "midwest" in by_id[cid].must_contain, f"{name}: {cid}"
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ledger.db"))
    result = CliRunner().invoke(cli_module.cli, ["eval", "--test", "--tag", "smoke", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_criterion_7_meta_layout_and_no_slash_commands(service, budget):
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    page = TestClient(app).get("/").text
    assert "createElement('details')" in page and "'Sources: '" in page and "'Limitations: '" in page
    toggle = page.index("createElement('details')")
    assert page.index("'Sources: '") < toggle, "sources visible by default (v6 round 2)"
    assert page.index("'Limitations: '") > toggle, "limitations inside the toggle (v6 round 2)"
    assert "startsWith('/')" not in page and "slash" not in page.lower()


def test_criterion_8_v5_baseline_committed():
    path = ROOT / "evals" / "results" / "v5-baseline.json"
    if not path.exists():
        pytest.fail("v5-baseline.json is missing: run `uv run agent eval --repeat 2 --tag v5-baseline` with keys set")
    r = Report.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert r.prompt_version == "1.2.0" and r.exit_code in (0, 2)  # the prompt version this report was produced under
    assert all(c.passed for c in r.cases if c.category == "in_scope"), [c.id for c in r.cases if c.category == "in_scope" and not c.passed]
    limits = {"fp-system-word": 1500}  # the v5 report was produced under the v5 caps (1200 default)
    over = [(c.id, len(run.answer)) for c in r.cases for run in c.runs if len(run.answer) > limits.get(c.id, 1200)]
    assert not over, over
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Which hub has the most heavy-snow days per year?" in readme or "heavy-snow" in readme
