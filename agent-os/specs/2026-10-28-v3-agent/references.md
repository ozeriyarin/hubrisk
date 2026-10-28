# References for v3 agent

## In this repo

- `src/app/agent/core.py::build_agent` — `Agent(deps_type=ToolContext, output_type=AnswerOut,
  instructions=..., toolsets=[build_toolset()], retries=1)`; dynamic instructions are registered here.
- `src/app/agent/prompts.py` — the only home of prompt text; refusal strings stay fixed.
- `src/app/agent/tools.py` — the seven tools and their docstrings (the model reads them as tool descriptions).
- `src/app/evals/cases.py` — `EvalCase(id, category, question, prior_turns, expect, must_contain,
  must_not_contain, tools)`; `src/app/evals/runner.py::check` is case-insensitive on `must_contain`.
- `src/app/decide/guard.py::offline_guard_model` — keyword list the smoke questions must trigger.
- `src/app/cli.py::eval_cmd` — `--cases`, `--repeat`, `--tag`, `--out`, `--test`, `--down`, `--note`.

## Pydantic AI

- `@agent.instructions` registers a function `(ctx: RunContext[Deps]) -> str` evaluated per run; the text is
  appended to the static instructions and appears in `ModelRequest.instructions`.

## Facts the eval set asserts (from the committed snapshot, scoring 1.0.0)

- Winter ranking: Minneapolis 42.3, Denver 19.0, Chicago 13.4 expected days/year.
- Hurricane/flood proxy: Houston 23.8 ahead of Miami; Dallas 20.8.
- Dallas overall 21.68, led by rain (12.72), then wind (4.9), heat (3.72).
- Denver 2025: snowfall on 44 of 365 days, 12.1%.
