# Standards for v2 disruption KPI

The following standards apply to this work.

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

## testing


- pytest, offline only: no network, no keys, no spend. Models are `FunctionModel` scripts or `TestModel` (`tests/fakes.py`); HTTP is `httpx2.MockTransport`; the ledger is a temp SQLite file.
- Every gate has a test that proves it fires *and* one that proves it stays quiet: regex injection vs ordinary words, budget over vs under cap, rate limit over vs under, fallback on error vs no fallback on success.
- Pure transforms get table-driven tests (`pytest.mark.parametrize`).
- The service is tested end to end with fakes: answered, refused by regex, refused by guard, all models down, fallback visible, budget exhausted, memory trimmed.
- Each spec's acceptance criteria map to tests named `test_criterion_<n>_<slug>`; `tests/test_spec_coverage.py` fails when one is missing. A spec in progress lists itself in `UNIMPLEMENTED` there and is removed when its tests land.
- Live tests (real providers) are marked `live` and skipped by default: `uv run pytest -m live` opts in and spends.
- `uv run ruff check src tests` and `uv run pytest` green before every commit; CI runs both plus the offline eval smoke.

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

## ai-calls


- Every model call goes through Pydantic AI (`Agent` with `output_type`). Never import a vendor SDK outside `app/llm/models.py`.
- The answer model is a chain, in `config/agent.yaml` order: same vendor's cheaper model first, then another vendor. `build_chain` drops entries whose key is missing and logs them; with no key at all it fails at startup.
- Three retry layers, each with one job: the httpx transport retries 429/5xx/network per model with Retry-After or exponential backoff (`retry_attempts`, `retry_max_wait_s`); vendor SDK retries are off (`max_retries=0`); `FallbackModel` moves to the next model on `ModelAPIError` or a truncated reply. A timeout counts as a failed attempt and moves on.
- Output is always typed: `AnswerOut` for answers, `Screening` for the guard. A reply that fails validation is retried once with the error, then the turn fails loudly.
- The model never invents facts: every number or name comes from a tool result; `sources` names the tools used; `limitations` says what the data cannot tell.
- `Turn` records which model answered (`served_by`), which failed before it (`failed_attempts`), tokens, cost and latency. The API returns them; evals aggregate them.
- Prompts live in `app/agent/prompts.py` only. Any change to a prompt, the chain, `Screening`, `AnswerOut` or the guard threshold is committed together with a fresh `agent eval` report under `evals/results/`.
- Per-turn ceilings: `UsageLimits(request_limit, cost_limit)` from `config/agent.yaml`; a runaway tool loop stops with `cannot_answer`, not an exception.
