# Standards for v7 alerts

The following standards apply to this work.

---

## data-sources


- Hubs are data: `config/hubs.yaml` (id, name, lat, lon, region, county FIPS), validated by Pydantic at load. Region
  filters ("Midwest") read this file; the model never decides which hub belongs where.
- History comes from the Open-Meteo archive API (daily: snowfall, precipitation, wind gust max, temp max/min),
  2016–2025, fetched once by `agent ingest` and written to `data/snapshots/daily.parquet`, which is committed. A deploy
  never re-ingests; Render's ephemeral disk is irrelevant.
- Queries over history go through DuckDB in-process, reading the Parquet directly. One `Store` type wraps the
  connection; tests build it from a small fixture Parquet.
- Live conditions come from NOAA NWS (`api.weather.gov`: `/points`, `/alerts/active`, forecast). Every request sends a
  `User-Agent` with a contact as NWS requires. Results are cached per hub for 10 minutes.
- Each external client takes an `httpx2.AsyncBaseTransport`; tests use `MockTransport` with recorded JSON fixtures in
  `tests/fixtures/`. Never patch the network.
- Every snapshot carries `source`, `fetched_at` and the date range; the agent's `sources` field cites them so the
  answer says how old the data is.
- A failed live call degrades, not crashes: the tool returns `available=false` with a reason and the answer's
  `limitations` says live data was unavailable.

---

## scoring


- The KPI is **expected disruption days per year, per hub and per hazard**, computed by `app/scoring` from daily
  history. No LLM code path produces, rounds or adjusts a number.
- A disruption day is a day crossing an operational threshold. Thresholds and hazard weights live in
  `config/scoring.yaml` with a `version` string; every score cites that version. Changing it is a versioned commit.
- Hazards: `snow`, `wind`, `rain`, `heat`, `cold`. "Winter" = snow + cold; "hurricane/flood" = rain + wind, stated as
  a proxy in `limitations` unless FEMA NRI data is wired in.
- Every per-hazard figure ships with its uncertainty: per-year counts, mean, min, max, stdev across years, and a
  5-year trend (last five years' mean minus the previous five). Never return a bare mean.
- Overall score = weighted sum of hazard means. Rankings are stable: ties break by hub id. Same input, same output;
  the engine is pure and table-tested.
- Tools return `HazardScore` / `HubScore` Pydantic models, never dicts; the model sees names, numbers and units it
  must quote verbatim.
- Percent-of-days questions use a calendar year with the actual day count (365/366) and say which year was used.
- Live risk ("right now") is a separate signal from NWS alerts and forecast; it is reported next to the historical
  score, never blended into it.

---

## secrets-and-config


- Secrets come only from environment variables via `app.config.Settings` (pydantic-settings, `.env` for local dev). Names are listed in `.env.example`; values are never committed, printed or logged.
- Non-secret runtime configuration is `config/agent.yaml` (models, limits) and `config/prices.yaml`, validated by Pydantic at load. Both carry a version string that eval reports cite.
- A missing vendor key removes that vendor's models from the chain with a log line. A chain with no usable model fails at startup with the list of keys to set.
- `MODEL_MODE=test` runs the whole app offline on Pydantic AI's `TestModel`: no key, no spend, canned answers. CI and the demo use it.
- `ADMIN_TOKEN` guards `/api/stats` when set; leave it empty only on localhost.
- The database path (`DB_PATH`) is a file; on Render's free tier it is ephemeral and the README says so.

---

## testing


- pytest, offline only: no network, no keys, no spend. Models are `FunctionModel` scripts or `TestModel` (`tests/fakes.py`); HTTP is `httpx2.MockTransport`; the ledger is a temp SQLite file.
- Every gate has a test that proves it fires *and* one that proves it stays quiet: regex injection vs ordinary words, budget over vs under cap, rate limit over vs under, fallback on error vs no fallback on success.
- Pure transforms get table-driven tests (`pytest.mark.parametrize`).
- The service is tested end to end with fakes: answered, refused by regex, refused by guard, all models down, fallback visible, budget exhausted, memory trimmed.
- Each spec's acceptance criteria map to tests named `test_criterion_<n>_<slug>`; `tests/test_spec_coverage.py` fails when one is missing. A spec in progress lists itself in `UNIMPLEMENTED` there and is removed when its tests land.
- Live tests (real providers) are marked `live` and skipped by default: `uv run pytest -m live` opts in and spends.
- `uv run ruff check src tests` and `uv run pytest` green before every commit; CI runs both plus the offline eval smoke.

---

## deployment


- Target: Render web service from `render.yaml` (Blueprint), python runtime, free plan. Build `pip install uv && uv sync --frozen --no-dev`, start `uv run agent serve --port $PORT`, health check `/health`.
- Secrets are `sync: false` env vars set in the Render dashboard; `ADMIN_TOKEN` is generated by Render. `BUDGET_USD` and `DB_PATH` are plain values.
- Free-tier facts stated in the README: 15 min idle → sleep, 30–60 s cold start; disk is ephemeral so the ledger resets on redeploy; provider-side limits are therefore mandatory.
- CI (`.github/workflows/ci.yml`) runs ruff, offline tests and the offline eval smoke on every push; it never holds a key.
- A deploy is verified by `GET /health` (models and guard listed) and one `POST /api/chat` from the live URL, pasted into the README's deployment section with the date.
