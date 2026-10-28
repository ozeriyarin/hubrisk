# Standards for v9 cost

The following standards apply to this work.

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

---

## budget


- Hard monthly cap `BUDGET_USD`, enforced in code before any paid call by `app/llm/budget.py`: reserve an estimate in one `BEGIN IMMEDIATE` transaction, settle with the real cost after, release on a refusal, keep the estimate charged on a mid-call failure. Over the cap → `budget_exhausted`, never a quiet downgrade.
- Cost per turn comes from Pydantic AI's `RunUsage.cost` (genai-prices). When a model has no price there, `config/prices.yaml` prices it; an unknown model is charged the most expensive row.
- Per-turn ceiling via `UsageLimits(cost_limit, request_limit)`; per-IP and global request limits in the API; conversation memory capped at `max_turns`.
- The provider consoles carry the same cap (Anthropic Console → Limits; OpenAI → Billing limits; Google Cloud budget). The code refuses *before* a call, the provider refuses *regardless* of the code. Both are required and documented in the README.
- `GET /api/stats` shows cap, month-to-date, remaining and the recent ledger so spend is visible without opening a console.

---

## evals


- Unit tests prove the code; evals measure the agent with real models. `evals/cases.yaml` is the set; `agent eval` is the runner; `evals/results/<tag>.{json,md}` is the committed evidence.
- Categories, each with at least three cases once the domain exists: `in_scope` (must answer, named tools must be called, key facts in `must_contain`), `off_topic` and `injection` (must refuse with the right status), `false_positive` (looks suspicious, must answer), `followup` (multi-turn via `prior_turns`).
- `--repeat N` runs each case N times: a case that passes some runs is *flaky* (exit 2), one that fails every run is *failed* (exit 1). A prompt or model change may not merge on exit 1.
- `--down <vendor>` drops a vendor from the chain to prove cross-vendor fallback end to end; the report records the simulated outage and which model served each run.
- Each report records models, guard, config version, cost and latency per run, so two reports can be compared by hand or diffed as JSON.
- Rule: any change to prompts, the chain, the guard threshold or the schemas is committed with the new report and a one-line comparison to the previous one in the commit message.

---

## testing


- pytest, offline only: no network, no keys, no spend. Models are `FunctionModel` scripts or `TestModel` (`tests/fakes.py`); HTTP is `httpx2.MockTransport`; the ledger is a temp SQLite file.
- Every gate has a test that proves it fires *and* one that proves it stays quiet: regex injection vs ordinary words, budget over vs under cap, rate limit over vs under, fallback on error vs no fallback on success.
- Pure transforms get table-driven tests (`pytest.mark.parametrize`).
- The service is tested end to end with fakes: answered, refused by regex, refused by guard, all models down, fallback visible, budget exhausted, memory trimmed.
- Each spec's acceptance criteria map to tests named `test_criterion_<n>_<slug>`; `tests/test_spec_coverage.py` fails when one is missing. A spec in progress lists itself in `UNIMPLEMENTED` there and is removed when its tests land.
- Live tests (real providers) are marked `live` and skipped by default: `uv run pytest -m live` opts in and spends.
- `uv run ruff check src tests` and `uv run pytest` green before every commit; CI runs both plus the offline eval smoke.
