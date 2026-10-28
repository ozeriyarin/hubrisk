# References for v0 platform

## Base scaffold

- **Location:** the pre-kickoff platform scaffold (50 test functions, 55 collected, all green); lifted verbatim
  into this repo under this spec.
- **Relevance:** it is the implementation; this spec names its behaviour as acceptance criteria and fixes the
  problems found while shaping.
- **Key modules:** `app/llm/models.py` (`retrying_http_client`, `build_model`, `build_chain`, `served_by`,
  `failed_attempts`), `app/llm/budget.py` (`Budget.reserve/settle/release`, `estimate_cost`),
  `app/decide/guard.py` (`check_input`, `Screening`, `build_guard_model`, `Guard.screen`),
  `app/agent/core.py` (`Service.ask`, `Conversation`), `app/api/app.py` (`create_app`), `app/api/ratelimit.py`,
  `app/api/sessions.py`, `app/evals/{cases,runner,report}.py`, `app/cli.py` (`compose`).
- **Test fakes to reuse:** `tests/fakes.py` (`answer_model`, `screening_model`, `failing_model`, `text_model`),
  `tests/conftest.py` (`config`, `prices`, `budget`, `service`).

## Pydantic AI 2.x notes

- `FallbackModel(fallback_on=[ModelAPIError, predicate])`; all models down raises `FallbackExceptionGroup`.
- HTTP client is `httpx2`; `AsyncHTTPX2TenacityTransport` from `pydantic_ai.retries`.
- `TestModel` and `FunctionModel` from `pydantic_ai.models.test` / `pydantic_ai.models.function`.
