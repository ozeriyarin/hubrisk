# v10 evals — Shaping Notes

## Scope

Evals only: bigger set, grounding check, guard metrics, latency and cost per case, fresh reports, two doc items.

## Decisions

- Grounding is a hard check: the product rule is that the LLM never produces a number, so an answer number that
  is not in the tool results is a failure, not a warning. Rounding tolerance covers 20.3 vs 20.34.
- Numeric `must_contain` values are pulled from the engine, never typed from memory, and work for Hebrew answers.
- Guard metrics are computed from what each run recorded (`guardrail`, status, category); no new instrumentation.
- Tool results ride on the `Turn` but are excluded from the API response: the runner needs them, clients do not.
- Baseline at repeat 3 so flaky wording shows up; exit 2 is reported, exit 1 is fixed before closing.

## Context

- **Visuals:** none. **References:** `app/evals/{cases,runner,report}.py`, `app/agent/core.py::Service.ask`,
  `pydantic_ai.ToolReturnPart.model_response_str`, `app/scoring/engine.py` for the numbers.
- **Product alignment:** mission "measured, not vibes"; evals standard.

## Standards Applied

- evals — categories, committed reports, outage proof, numbers from tools.
- ai-calls — the model quotes tool values; grounding enforces it.
- testing — table-driven grounding tests, offline runner tests.
- python-style — pure `grounding.py`.
