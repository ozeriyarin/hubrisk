# Python style

- Python 3.12, `src/app/` layout, one subpackage per concern: `llm` (models, budget), `decide` (guard), `data` (hub registry, weather clients, ingest, DuckDB), `scoring` (KPI engine), `agent` (schema, prompts, tools, service), `api`, `evals`. `cli.py` is the only composition root.
- Pydantic models at every boundary: config, model outputs, API bodies, eval cases, reports. No dicts crossing module lines.
- External systems sit behind a type the tests can fake: a Pydantic AI `Model`, an `httpx2.AsyncBaseTransport`, a `Budget`. Never patch the network.
- Errors are typed (`BudgetExceeded`, `InputRejection`) and surface as a `Turn.status`, never as a silent default.
- Async for anything that awaits a model; sync for pure code. The service is async end to end.
- `ruff check src tests` clean (E, F, I, B, UP). Line length 110.
- Comments: one line, at most 100 characters, only when the intent is not obvious from the code. Module docstrings say *why* the module exists in two or three lines. No essay docstrings; design lives in `docs/DESIGN.md` and the specs.
- Commit messages: `<type>: <what it does>` (`feat`, `fix`, `test`, `docs`, `chore`), one spec per feature commit, tests green before every commit.
