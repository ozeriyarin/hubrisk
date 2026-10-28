# v3 agent — Shaping Notes

## Scope

Prompts (static rules + dynamic data facts), the real eval set and an offline smoke set, `prompt_version` in
reports, sources on the chat page, and the first two committed live eval reports.

## Decisions

- Facts the prompt needs (data range, scoring version, hub ids, scopes) are injected from `ToolContext` at run
  time, never hard-coded, so the prompt tracks the snapshot and the config.
- Two eval sets: the real one asserts facts in the wording (`must_contain`), the smoke one only statuses and
  tools, because the test-mode answer is canned. CI runs the smoke; the real set runs with keys and its report is
  committed.
- A prompt change ships with a fresh baseline report; `PROMPT_VERSION` makes the pairing checkable.
- The Anthropic-down run is the end-to-end fallback proof the resilience story rests on.
- The baseline may exit 2 (flaky wording across repeats); it must not exit 1 and every in_scope case must pass.
- `AnswerOut`, guard, budget and chain are untouched.

## Context

- **Visuals:** none.
- **References:** `app/agent/core.py::build_agent`, `app/agent/prompts.py`, `app/evals/{cases,runner,report}.py`,
  `app/decide/guard.py::offline_guard_model`, `app/api/static/index.html`; Pydantic AI `@agent.instructions`.
- **Product alignment:** mission "the LLM never produces a number", "explain reasoning", "conversational follow-ups".

## Standards Applied

- ai-calls — prompts live in `prompts.py`; a change ships with an eval report.
- evals — categories with ≥ 3 cases, exit-code gate, `--down` outage proof, reports committed.
- guardrails — `SCOPE_DESCRIPTION` is the guard's definition of in-scope.
- testing — criterion tests in `tests/test_v3_agent.py`; offline fakes; the smoke set.
- python-style — pure `data_instructions` helper, typed everywhere.
