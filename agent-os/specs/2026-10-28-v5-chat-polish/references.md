# References for v5 chat polish

- `src/app/api/static/index.html` — single-file chat page; the meta line is built in the submit handler from the
  `/api/chat` JSON (`status`, `served_by`, `failed_attempts`, `tools_used`, `cost_usd`, `latency_ms`, `sources`,
  `limitations`).
- `src/app/agent/schema.py::AnswerOut` — `answer` max length; validation failure retries once (`retries=1`).
- `src/app/agent/prompts.py` — `INSTRUCTIONS`, `PROMPT_VERSION`; new `intro_reply` and `INTRO` live here.
- `src/app/agent/core.py::Service.ask` — order: input checks → (intro) → reserve → guard → model → settle.
- `src/app/evals/cases.py::EvalCase`, `src/app/evals/runner.py::check` — where `max_chars` is declared and checked.
- `src/app/cli.py::verify` — the chat question it sends.
- Baseline facts: see `agent-os/specs/2026-10-28-v3-agent/references.md`.
