# v5 chat polish — Shaping Notes

## Scope

Owner feedback after testing the deployed chat: favicon, shorter answers, greetings in scope, quieter meta line.

## Decisions

- Greetings are handled in code before the guard: deterministic, free, instant, and the intro always lists the
  four example questions. Patterns are anchored to the whole message so real questions never get intercepted.
- Brevity is enforced three ways: a prompt rule, a hard schema cap (2000 chars) and an eval check (1200 chars by
  default) so the baseline fails if answers creep up again.
- Sources and limitations stay visible on every answer because the assignment asks for assumptions and
  uncertainty to be communicated; model, tools, cost and latency are operator detail behind a toggle.
- The verify command asks a scored question so the live record keeps proving the model path.
- Prompt and schema changed → `PROMPT_VERSION` 1.2.0 and a new committed baseline.

## Context

- **Visuals:** none. **References:** `app/api/static/index.html`, `app/agent/{schema,prompts,core}.py`,
  `app/evals/{cases,runner}.py`, `app/cli.py::verify`.
- **Product alignment:** mission "answers an analyst can defend": short, sourced, caveated.

## Standards Applied

- ai-calls — prompt change ships with a fresh eval report; output stays typed.
- evals — new cases per category; length check in the runner.
- guardrails — the intro layer is deterministic code in front of the guard, refusals untouched.
- testing — criterion tests in `tests/test_v5_chat_polish.py`.
- python-style — pure `intro_reply`, one-line comments only.
