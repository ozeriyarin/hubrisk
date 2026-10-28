"""Acceptance criteria of agent-os/specs/2026-10-28-v9-cost. 4 and 5 read committed live reports."""

from __future__ import annotations

import json
import re

import pytest
from typer.testing import CliRunner

from app import cli as cli_module
from app.agent.core import build_agent
from app.agent.schema import Turn
from app.config import ROOT, load_agent_config
from app.evals.cases import EvalCase
from app.evals.report import render_markdown
from app.evals.runner import CaseResult, Report, RunResult
from app.llm.models import answer_chain, cache_settings
from tests.fakes import answer_model

CACHE_KEYS = {"anthropic_cache_instructions", "anthropic_cache_tool_definitions", "anthropic_cache_messages"}


def run(cost: float, input_tokens: int, read: int, write: int = 0) -> RunResult:
    return RunResult(status="answered", passed=True, reasons=[], served_by="m", guardrail=None, failed_attempts=[], tools=[],
                     cost_usd=cost, latency_ms=1, answer="ok", input_tokens=input_tokens, cache_read_tokens=read, cache_write_tokens=write)


def report_of(runs: list[RunResult], **kw) -> Report:
    case = CaseResult(id="c", category="in_scope", question="q", expect=["answered"], runs=runs)
    return Report(started_at="t", models=["m"], guard="g", config_version="0.3.0", repeat=len(runs), cases=[case], **kw)


def test_criterion_1_cache_config_and_agent_settings():
    cfg = load_agent_config()
    assert cfg.version == "0.3.0" and cfg.models.cache is True
    assert cache_settings(True) == dict.fromkeys(CACHE_KEYS, True) and cache_settings(False) is None
    assert set(build_agent(answer_model(), cache=True).model_settings) == CACHE_KEYS
    assert build_agent(answer_model(), cache=False).model_settings is None


def test_criterion_2_cache_tokens_reported():
    turn = Turn(status="answered", answer="x")
    assert turn.cache_read_tokens == 0 and turn.cache_write_tokens == 0
    r = report_of([run(0.01, 1000, 3000, 500), run(0.01, 1000, 0, 0)])
    assert r.cache_read_tokens == 3000 and r.cache_write_tokens == 500 and r.cache_share == 0.6
    md = render_markdown(r)
    assert "cache: read 3000 tokens, write 500, 60% of input served from cache" in md


def test_criterion_3_single_model_switch():
    chain = ["anthropic:a", "openai:b", "google-gla:c"]
    assert answer_chain(chain) == chain and answer_chain(chain, ["openai"]) == ["anthropic:a", "google-gla:c"]
    assert answer_chain(chain, ["openai"], "anthropic:claude-haiku-5-5") == ["anthropic:claude-haiku-5-5"]
    # Typer forces Rich colour under GITHUB_ACTIONS and Rich splits "--model" into styled pieces: strip ANSI first.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", CliRunner().invoke(cli_module.cli, ["eval", "--help"]).output)
    assert "--model" in plain


def load(tag: str) -> Report:
    path = ROOT / "evals" / "results" / f"{tag}.json"
    if not path.exists():
        pytest.fail(f"{path.name} is missing: run the live eval with keys set and commit it")
    return Report.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_criterion_4_cached_baseline_is_cheaper_and_passes():
    v6, v9 = load("v6-baseline"), load("v9-baseline")
    assert all(c.passed for c in v9.cases if c.category == "in_scope"), [c.id for c in v9.cases if not c.passed]
    assert v9.cache_read_tokens > 0 and v9.cache_share > 0.3, (v9.cache_read_tokens, v9.cache_share)
    assert v9.total_cost_usd <= 0.75 * v6.total_cost_usd, (v9.total_cost_usd, v6.total_cost_usd)
    assert v9.config_version == "0.3.0"


def test_criterion_5_haiku_experiment_and_readme():
    haiku = load("v9-haiku")
    assert any("single model: anthropic:claude-haiku-5-5" in n for n in haiku.notes)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Cost" in readme and "`v9-baseline`" in readme and "`v9-haiku`" in readme
    assert "per question" in readme.lower() and "cache" in readme.lower()
    assert EvalCase(id="c", category="x", question="q", expect=["answered"]).max_chars == 1000
