# Standards for v1 hubs and data

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

## python-style


- Python 3.12, `src/app/` layout, one subpackage per concern: `llm` (models, budget), `decide` (guard), `data` (hub registry, weather clients, ingest, DuckDB), `scoring` (KPI engine), `agent` (schema, prompts, tools, service), `api`, `evals`. `cli.py` is the only composition root.
- Pydantic models at every boundary: config, model outputs, API bodies, eval cases, reports. No dicts crossing module lines.
- External systems sit behind a type the tests can fake: a Pydantic AI `Model`, an `httpx2.AsyncBaseTransport`, a `Budget`. Never patch the network.
- Errors are typed (`BudgetExceeded`, `InputRejection`) and surface as a `Turn.status`, never as a silent default.
- Async for anything that awaits a model; sync for pure code. The service is async end to end.
- `ruff check src tests` clean (E, F, I, B, UP). Line length 110.
- Comments: one line, at most 100 characters, only when the intent is not obvious from the code. Module docstrings say *why* the module exists in two or three lines. No essay docstrings; design lives in `docs/DESIGN.md` and the specs.
- Commit messages: `<type>: <what it does>` (`feat`, `fix`, `test`, `docs`, `chore`), one spec per feature commit, tests green before every commit.

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
