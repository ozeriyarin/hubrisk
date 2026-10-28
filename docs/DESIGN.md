# HubRisk — Design

Weather disruption risk agent for a US logistics company's regional distribution hubs. This document covers the
system architecture, the repository structure and the data storage choice. Product goals live in
`agent-os/product/`, behaviour in `agent-os/specs/`, conventions in `agent-os/standards/`.

## System architecture

```
browser chat page ──HTTP──▶ FastAPI (app/api)
                               │  rate limit per IP + global, session store (TTL + LRU, one lock per session)
                               ▼
                           Service.ask (app/agent/core.py)
                               │ 1. regex input checks            (app/decide/guard.py, free)
                               │ 2. budget.reserve                (app/llm/budget.py, SQLite ledger)
                               │ 3. guard.screen → Screening      (TypeSafe Jev → Claude Haiku fallback)
                               │ 4. Agent.run(output_type=AnswerOut, UsageLimits)
                               │       └─ FallbackModel chain: Sonnet → Haiku → GPT → Gemini
                               │       └─ FunctionToolset: deterministic tools (hubs, scoring, live weather)
                               │ 5. budget.settle(real cost)
                               ▼
                           Turn (status, answer, sources, limitations, served_by, failed_attempts, cost, latency)
```

- **The LLM never produces a number.** Tools return typed Pydantic models; the model picks tools and explains.
  `AnswerOut` is enforced by Pydantic AI; a reply that fails validation is retried once, then the turn fails loudly.
- **Three retry layers, one job each:** the httpx transport retries 429/5xx/network per model with Retry-After;
  vendor SDK retries are off; `FallbackModel` moves to the next model on an API error or a truncated reply.
  All models down → `status: unavailable`, never a crash.
- **Guard before spend:** the regex layer costs nothing; the decision model is Jev (typed questions, calibrated
  confidence) with Haiku taking over below `guard_confidence` or on error. Refusals are fixed strings and release
  the budget reservation. In `MODEL_MODE=test` the guard is a keyword heuristic (`offline_guard_model`), a test
  double so smoke evals can distinguish in-scope from off-topic offline.
- **Spend is bounded twice:** the ledger enforces `BUDGET_USD` per month before every paid call (reserve →
  settle / release), plus `UsageLimits` per turn and per-IP / daily request limits. Provider consoles carry the
  same cap as the hard backstop.
- **Evals are the quality gate:** `evals/cases.yaml` by category, `agent eval` writes `evals/results/<tag>`,
  exit 0 pass / 1 fail / 2 flaky, `--down <vendor>` proves cross-vendor fallback end to end.

## Data layer (`app/data`)

- `hubs.py`: `HubRegistry` over `config/hubs.yaml`. Region filters are lookups, never model guesses.
- `openmeteo.py`: one archive request per hub for five daily variables; the response's `daily_units` must match
  the expected metric units or the client raises `SourceError`.
- `snapshot.py` / `store.py`: DuckDB writes the Parquet snapshot and reads it back through a `daily` view; every
  query runs on a per-call cursor. `Store.years` counts a year complete at 360 or more rows.
- `nws.py`: alerts via `/alerts/active?point=`, forecast via `/points` then the forecast URL; User-Agent on every
  request; per-hub cache (10 min, 1 min for failures); any failure degrades to `available=False` with a reason.
- `ingest.py`: sequential per-hub fetch with a pause and long-backoff retries (the archive answers 429 to bursts),
  one atomic snapshot write.

Still to come: `app/scoring` (v2) and the domain tools and prompts in `app/agent` (v3).

## Repository structure

```
config/        agent.yaml (models, limits), prices.yaml (fallback prices), hubs.yaml + scoring.yaml (v1/v2)
src/app/
  config.py    Settings (env) + YAML config loaders
  cli.py       Typer: agent serve | chat | eval | ingest; compose() is the only composition root
  llm/         models.py (chain, retries, fallback), budget.py (SQLite ledger)
  decide/      guard.py (regex layer, Screening, Jev→Haiku, offline guard)
  agent/       schema.py (AnswerOut, Turn), prompts.py, tools.py, core.py (Service)
  api/         app.py (routes), ratelimit.py, sessions.py, static/index.html (chat page)
  evals/       cases.py, runner.py, report.py
  data/        v1: hub registry, weather clients, ingest, DuckDB store
  scoring/     v2: deterministic KPI engine
data/          snapshots/*.parquet committed (v1); runtime SQLite ledger ignored
evals/         cases.yaml, results/<tag>.{json,md}
tests/         offline pytest; test_<spec-slug>.py holds that spec's criterion tests; test_spec_coverage.py enforces
agent-os/      product docs, standards (+ index.yml), one spec folder per version
docs/          this file, ai-session/ (the full agent session transcript, a deliverable)
.github/       CI: ruff + pytest + offline eval smoke
render.yaml    Render Blueprint (python runtime, uv sync --frozen --no-dev, /health probe)
```

## Data storage choice

- **History: DuckDB over Parquet snapshots committed to the repo.** Open-Meteo daily history for all hubs,
  2016–2025, is ingested once locally and committed as Parquet. Rationale: the dataset is small (15 hubs × ~3,650
  days), read-only at runtime, and queried analytically (thresholds, group-by year); DuckDB runs in-process with
  no server and reads Parquet directly; a deploy needs no re-ingest, so Render's ephemeral disk is irrelevant and
  the live demo cannot be broken by an upstream outage. Trade-off: history is frozen at ingest time; refreshing
  is a re-run of `agent ingest` and a commit.
- **Live conditions: not stored.** NWS alerts and forecast are fetched per request with a 10-minute in-memory
  cache; they are a "right now" signal shown beside the historical score, never blended into it.
- **Spend ledger: SQLite at runtime** (`DB_PATH`). Transactional (`BEGIN IMMEDIATE`) so concurrent turns cannot
  overspend. On Render's free tier the file is ephemeral and resets on redeploy; provider-side limits are the
  backstop and the README says so.
- **Sessions: in memory** (1 h TTL, LRU 500). A restart forgets conversations; acceptable for an analyst tool
  at this scale and stated in the README.

## Trade-offs and known limits

- Thresholds are plausible operational limits, not calibrated to real outage data (none available).
- Reanalysis data is a point at the hub coordinate, not the facility footprint.
- Ten years is short for rare hazards (hurricanes); the year-to-year band is the honest uncertainty we can show.
- Single process, single region, no auth: scoped for a live demo and a small analyst team.
