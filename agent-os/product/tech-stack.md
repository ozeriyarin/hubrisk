# Tech Stack — HubRisk

## Frontend

Static single-file chat page served by FastAPI at `/`, talking to `POST /api/chat`. Voice (browser Web Speech
API) is a bonus item.

## Backend

- **Language / runtime:** Python 3.12, `src/app/` layout, uv (`uv.lock` committed). Typer CLI: `agent serve | chat | eval`.
- **Agent framework:** Pydantic AI 2.63 (`pydantic-ai-slim[anthropic,openai,google,typesafe,retries]`): `Agent`
  with `output_type=AnswerOut`, `FunctionToolset`, `UsageLimits(request_limit, cost_limit)`, `message_history`.
- **Models:** chain in `config/agent.yaml`: `anthropic:claude-sonnet-5-5` → `anthropic:claude-haiku-5-5` →
  `openai:gpt-5.2` → `google-gla:gemini-2.5-flash` via `FallbackModel(fallback_on=[ModelAPIError, truncated])`.
  Per-model HTTP retries with `AsyncHTTPX2TenacityTransport` (429/5xx/network, Retry-After aware, capped);
  vendor SDK retries off; a model whose key is missing is skipped at startup. All-down raises
  `FallbackExceptionGroup`. Model ids and `config/prices.yaml` verified at kickoff. Prompt caching of the static prefix (instructions, tool definitions,
  messages) is on for Anthropic via `models.cache`; cache reads and writes are recorded per turn and per report.
- **Guard:** regex layer → `Screening(in_scope, injection)` by TypeSafe Jev (`typesafe:jev-latest`), fallback to
  Haiku on error or any field confidence < 0.7. Refusals are fixed strings and spend nothing. If no TypeSafe key:
  Jev via OpenRouter, else Haiku alone (documented in DESIGN.md).
- **Budget:** SQLite ledger, monthly cap `BUDGET_USD`, reserve → settle → release; cost from `result.usage.cost`
  else `config/prices.yaml`; per-turn `cost_limit`; 20 req/IP/hour, 200/day.
- **API:** FastAPI + uvicorn: `/health`, `POST /api/chat`, `GET /api/stats` (admin token),
  `DELETE /api/sessions/{id}`. In-memory sessions (1 h TTL, LRU 500), one asyncio lock per session.
- **Scoring engine:** pure Python over DuckDB queries; thresholds and hazard weights in versioned YAML.

## Database

- **DuckDB over Parquet snapshots committed to the repo.** Open-Meteo daily history (2016–2025) for all hubs is
  ingested once locally and committed as Parquet; deploys need no re-ingest, so Render's ephemeral disk is
  irrelevant. DuckDB runs in-process and queries Parquet directly.
- **SQLite** at runtime only for the spend ledger.
- **Hub registry** in `config/hubs.yaml` (name, lat/lon, region, county FIPS).

## Data sources (public, keyless)

- **Open-Meteo archive API** — daily history: snowfall, wind gusts, precipitation, max/min temperature.
- **NOAA NWS API** (api.weather.gov) — active alerts and 7-day forecast per hub.
- **FEMA National Risk Index** — county hurricane/flood signal, optional.

## Other

- **Evals:** `evals/cases.yaml` (categories in_scope / off_topic / injection / false_positive / followup; fields
  expect, must_contain, must_not_contain, tools, prior_turns) → `agent eval --repeat N --tag T --down <vendor>` →
  `evals/results/T.{json,md}`; exit 0 pass / 1 fail / 2 flaky.
- **Tests:** pytest, offline; `FunctionModel`/`TestModel` fakes, `httpx2.MockTransport`; spec-coverage test
  enforces `test_criterion_<n>_<slug>` per acceptance criterion. Never patch the network.
- **CI:** GitHub Actions: ruff + pytest + offline eval smoke.
- **Deployment:** Render Blueprint (`render.yaml`), python runtime, `uv sync --frozen --no-dev`, `/health` probe,
  secrets `sync: false`. Repo: public `ozeriyarin/hubrisk`, commit straight to `main`.
- **Secrets:** env only (`.env.example`); `MODEL_MODE=test` for a keyless demo; provider-side spend limits set in
  each console.
- **Process tooling:** Agent OS v3 (`agent-os/`, `.claude/commands/agent-os/`), Claude Code, ruff.
