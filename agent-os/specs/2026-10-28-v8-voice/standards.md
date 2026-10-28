# Standards for v8 voice

The following standards apply to this work.

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

## python-style


- Python 3.12, `src/app/` layout, one subpackage per concern: `llm` (models, budget), `decide` (guard), `data` (hub registry, weather clients, ingest, DuckDB), `scoring` (KPI engine), `agent` (schema, prompts, tools, service), `api`, `evals`. `cli.py` is the only composition root.
- Pydantic models at every boundary: config, model outputs, API bodies, eval cases, reports. No dicts crossing module lines.
- External systems sit behind a type the tests can fake: a Pydantic AI `Model`, an `httpx2.AsyncBaseTransport`, a `Budget`. Never patch the network.
- Errors are typed (`BudgetExceeded`, `InputRejection`) and surface as a `Turn.status`, never as a silent default.
- Async for anything that awaits a model; sync for pure code. The service is async end to end.
- `ruff check src tests` clean (E, F, I, B, UP). Line length 110.
- Comments: one line, at most 100 characters, only when the intent is not obvious from the code. Module docstrings say *why* the module exists in two or three lines. No essay docstrings; design lives in `docs/DESIGN.md` and the specs.
- Commit messages: `<type>: <what it does>` (`feat`, `fix`, `test`, `docs`, `chore`), one spec per feature commit, tests green before every commit.
