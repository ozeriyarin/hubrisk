"""Run every case N times through a Service and aggregate. Exit code: 0 all pass, 1 failures, 2 flaky only."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, Field, computed_field

from app.agent.core import Conversation, Service
from app.agent.schema import Turn
from app.evals.cases import EvalCase


class RunResult(BaseModel):
    status: str
    passed: bool
    reasons: list[str]
    served_by: str | None
    guardrail: str | None
    failed_attempts: list[str]
    tools: list[str]
    cost_usd: float
    latency_ms: int
    answer: str


class CaseResult(BaseModel):
    id: str
    category: str
    question: str
    expect: list[str]
    runs: list[RunResult]

    @computed_field
    @property
    def passes(self) -> int:
        return sum(r.passed for r in self.runs)

    @computed_field
    @property
    def passed(self) -> bool:
        return self.passes == len(self.runs)

    @computed_field
    @property
    def flaky(self) -> bool:
        return 0 < self.passes < len(self.runs)


class Report(BaseModel):
    started_at: str
    models: list[str]
    guard: str
    config_version: str
    prompt_version: str = "n/a"
    repeat: int
    cases: list[CaseResult]
    notes: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for c in self.cases for r in c.runs), 6)

    @computed_field
    @property
    def by_category(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for c in self.cases:
            d = out.setdefault(c.category, {"cases": 0, "passed": 0, "runs": 0, "runs_passed": 0})
            d["cases"] += 1
            d["passed"] += int(c.passed)
            d["runs"] += len(c.runs)
            d["runs_passed"] += c.passes
        return out

    @computed_field
    @property
    def served_by(self) -> dict[str, int]:
        return dict(Counter(r.served_by or r.guardrail or "none" for c in self.cases for r in c.runs))

    @computed_field
    @property
    def exit_code(self) -> int:
        if any(not c.passed and not c.flaky for c in self.cases):
            return 1
        return 2 if any(c.flaky for c in self.cases) else 0


def check(case: EvalCase, turn: Turn) -> list[str]:
    reasons: list[str] = []
    if turn.status not in case.expect:
        reasons.append(f"status {turn.status}, expected one of {case.expect}")
    low = turn.answer.lower()
    reasons += [f"answer lacks {s!r}" for s in case.must_contain if s.lower() not in low]
    reasons += [f"answer contains {s!r}" for s in case.must_not_contain if s.lower() in low]
    reasons += [f"tool {t!r} not called" for t in case.tools if t not in turn.tools_used]
    if len(turn.answer) > case.max_chars:
        reasons.append(f"answer is {len(turn.answer)} chars, over {case.max_chars}")
    return reasons


async def run_case(service: Service, case: EvalCase, max_turns: int) -> RunResult:
    conv = Conversation(max_turns=max_turns)
    cost = 0.0
    for prior in case.prior_turns:
        cost += (await service.ask(conv, prior)).cost_usd
    turn = await service.ask(conv, case.question)
    reasons = check(case, turn)
    return RunResult(
        status=turn.status, passed=not reasons, reasons=reasons, served_by=turn.served_by, guardrail=turn.guardrail,
        failed_attempts=turn.failed_attempts, tools=turn.tools_used, cost_usd=cost + turn.cost_usd,
        latency_ms=turn.latency_ms, answer=turn.answer,
    )


async def run_all(
    service: Service, cases: list[EvalCase], *, repeat: int, models: list[str], guard: str, config_version: str,
    max_turns: int, notes: list[str] | None = None, prompt_version: str = "n/a",
) -> Report:
    results: list[CaseResult] = []
    for case in cases:
        runs = [await run_case(service, case, max_turns) for _ in range(repeat)]
        results.append(CaseResult(id=case.id, category=case.category, question=case.question, expect=list(case.expect), runs=runs))
    return Report(
        started_at=datetime.now(UTC).isoformat(timespec="seconds"), models=models, guard=guard,
        config_version=config_version, prompt_version=prompt_version, repeat=repeat, cases=results, notes=notes or [],
    )
