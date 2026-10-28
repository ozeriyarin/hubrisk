# Spec: v0 platform

## Goal

Stand up the domain-agnostic platform HubRisk runs on: model chain with retries and cross-vendor fallback, typed
guard, spend budget, FastAPI API with a chat page, sessions, rate limits, eval runner with an exit-code gate,
offline tests, CI and a Render Blueprint. After this spec the app runs keyless (`MODEL_MODE=test`), every gate is
tested, and later specs only add hubs, data, scoring and prompts.

## Scope

**In:** everything under `src/app/` except domain code; `config/agent.yaml`, `config/prices.yaml`; `evals/` runner
and a smoke case set; `tests/`; `.github/workflows/ci.yml`; `render.yaml`; README and DESIGN skeletons.

**Out:** hubs, weather data, scoring, domain tools and prompts (v1–v3); live deployment (v4); alerts and voice.

## Acceptance criteria

1. `build_chain` skips a model whose vendor key is missing with a log line and raises `RuntimeError` when no key is set.
2. When the first model raises `ModelAPIError` or returns a truncated reply, the next model answers; `Turn.served_by` names it and `Turn.failed_attempts` lists the failure.
3. The HTTP transport retries 429 and 5xx up to `retry_attempts` honouring `Retry-After`, does not retry 401, and vendor SDK retries are off.
4. With every model down, `Service.ask` returns status `unavailable` and the ledger keeps the reservation as failed.
5. Empty, over-long, control-character or regex-matched injection input is rejected before any model call and spends nothing.
6. The guard maps `Screening` to `in_scope` / `off_topic` / `injection`; a decision-model error or any field confidence below `guard_confidence` falls back to Haiku; refusals are the fixed strings in `prompts.py` and release the reservation.
7. The budget reserves before a call, settles with real cost after, releases on refusal, keeps the estimate on failure, refuses with `budget_exhausted` at the monthly cap, resets by month, and prices an unknown model at the most expensive row.
8. A turn exceeding `request_limit` or `cost_limit` ends with status `cannot_answer`, not an exception.
9. Conversation history is sent on follow-ups and trimmed to `max_turns`.
10. `GET /health` lists chain models and guard name; `POST /api/chat` returns the `Turn` plus `session_id`, reports `session_reset` for an unknown id, and returns 422 on an empty message.
11. Requests over `per_ip_per_hour` or `global_per_day` get 429 with `Retry-After`.
12. Sessions expire after `session_ttl_s` and the store evicts least-recently-used beyond 500; `DELETE /api/sessions/{id}` returns 204.
13. `GET /api/stats` returns 401 without the admin token and the ledger stats with it.
14. `EvalCase` rejects duplicate ids and strings in both `must_contain` and `must_not_contain`; `check` reports status, must_contain, must_not_contain and tool reasons.
15. The eval runner exits 0 when all runs pass, 1 when a case fails every run, 2 when only flaky; `--down <vendor>` removes that vendor from the chain and the report records it; reports are written as `<tag>.json` and `<tag>.md`.
16. With `MODEL_MODE=test` and no keys, the app composes, the guard labels ordinary questions `in_scope`, and `agent eval --test` on the committed cases exits 0.
17. `config/agent.yaml` and `config/prices.yaml` validate, both carry `version`, every chain model has a price, and the product name is `hubrisk`.
18. The coverage test fails naming the spec and expected file when a criterion lacks its test, and criteria of different specs never satisfy each other.
19. `GET /` serves the single-file chat page titled HubRisk that calls `/api/chat`.
20. `.github/workflows/ci.yml` runs ruff, pytest and the offline eval smoke; `render.yaml` builds with `uv sync --frozen --no-dev`, starts `agent serve`, probes `/health`, and lists every vendor key as `sync: false`.

## Design

Package `app` under `src/`, one subpackage per concern, `cli.compose` the only composition root.

- `app/config.py`: `Settings` (env, pydantic-settings), `AgentConfig` from `config/agent.yaml`, prices from
  `config/prices.yaml`, both versioned.
- `app/llm/models.py`: the only module importing vendor SDKs. `retrying_http_client` (tenacity transport: 429/5xx/
  network, Retry-After aware, capped), `build_model` with SDK retries off, `build_chain` → `FallbackModel` over the
  keyed models, `served_by` / `failed_attempts` readers. `MODEL_MODE=test` → `TestModel` that calls all tools.
- `app/llm/budget.py`: SQLite ledger; `reserve` (BEGIN IMMEDIATE) → `settle` / `release(failed)`; `estimate_cost`.
- `app/decide/guard.py`: `check_input` (regex layer), `Screening`, `build_guard_model` (Jev → Haiku on error or low
  confidence), `Guard.screen` → `Verdict`, `offline_guard_model()` for test mode.
- `app/agent/`: `schema.py` (`AnswerOut`, `Turn`, `Status`), `prompts.py` (scope, instructions, fixed refusal
  strings), `tools.py` (`FunctionToolset`; `about` placeholder until v3), `core.py` (`Service.ask` order: input check
  → reserve → guard → run with `UsageLimits` → settle; typed errors become `Turn.status`).
- `app/api/`: FastAPI routes `/health`, `POST /api/chat`, `DELETE /api/sessions/{id}`, `GET /api/stats`, static page
  at `/`; `RateLimiter` sliding windows; `SessionStore` TTL + LRU with one lock per session.
- `app/evals/`: `EvalCase` schema, runner with pass/fail/flaky and exit codes, markdown report.
- `app/data/`, `app/scoring/`: empty packages reserved for v1 and v2.
- Tests: criterion tests for a spec folder `<date>-<slug>` live in `tests/test_<slug_with_underscores>.py`;
  `tests/test_spec_coverage.py` checks only that file for that spec. Unit tests stay in their own files.

Fixes over the base scaffold: test-mode guard built on a `FunctionModel` so in-scope questions pass offline; per-spec
coverage rule; product name `hubrisk`; `prices.yaml` versioned; `OPENROUTER_API_KEY` in `render.yaml`;
`.gitattributes` with LF endings.

## Tasks

1. Save spec documentation (`spec.md`, `shape.md`, `standards.md`, `references.md`).
2. Lift the scaffold: `pyproject.toml` (name `hubrisk`), `uv.lock`, `.python-version`, `.gitignore`, `.env.example`,
   `config/`, `src/app/`, `tests/`, `evals/`, `.github/`, `render.yaml`; add `.gitattributes`, `data/.gitkeep`,
   `app/data/`, `app/scoring/`. `uv sync`.
3. Renames and config fixes; verify model ids and prices, record the date in `prices.yaml`.
4. Fix the test-mode guard and tool calling; `agent eval --test` exits 0.
5. Per-spec coverage rule; `tests/test_v0_platform.py` with the 20 criterion tests.
6. `docs/DESIGN.md`, `README.md`, `CLAUDE.md`.
7. `ruff`, `pytest`, `agent eval --test --tag ci-smoke` (commit the report), roadmap closeout, commit.
