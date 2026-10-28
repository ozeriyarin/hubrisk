# Spec: v9 cost

## Goal

Lower the cost of a question without lowering answer quality, and prove it with the eval set. The measured
driver is the static prefix (instructions, tool schemas, data facts) resent on every request of a multi-request
turn; Anthropic prompt caching serves it at a tenth of the price. A cheaper first model is measured, not assumed.

## Scope

**In:** `models.cache` config, cache settings in `build_agent`, cache token fields in `Turn`/`RunResult`/`Report`
and the Markdown report, `agent eval --model`, two committed reports (`v9-baseline`, `v9-haiku`), README cost
section. **Out:** prompt changes, tool payload redesign, chain reorder unless the Haiku experiment passes
every case and the owner chooses it.

## Acceptance criteria

1. `config/agent.yaml` (version 0.3.0) has `models.cache: true`, and `build_agent` applies Anthropic cache settings for instructions, tool definitions and messages when it is on and none when off.
2. `Turn`, `RunResult` and `Report` carry `cache_read_tokens` and `cache_write_tokens`, and the Markdown report prints cache totals and the cached share of input.
3. `agent eval --model <id>` runs the set on a single answer model and records it in the report's models and notes.
4. `evals/results/v9-baseline.json` (Sonnet, cache on) passes every in_scope case, shows cache reads on multi-request turns, and costs at least 25% less than `v6-baseline`.
5. `evals/results/v9-haiku.json` is committed with its pass rate and cost, and the README cost section states per-question cost before and after, the cache share, the Haiku result and the chain decision.

## Design

- `ModelsConfig.cache: bool = True`; `build_agent(model, cache=...)` sets
  `AnthropicModelSettings(anthropic_cache_instructions=True, anthropic_cache_tool_definitions=True,
  anthropic_cache_messages=True)` as the agent's `model_settings`; other vendors ignore prefixed keys. The dynamic
  data facts are stable per process, so the whole prefix caches (minimum cacheable prefix is well under our size).
- `Service.ask` reads `usage.cache_read_tokens` / `usage.cache_write_tokens` into the `Turn`; the runner copies
  them into `RunResult`; `Report` sums them and the renderer prints `cache: read X, write Y (Z% of input)`.
- `compose(only=...)` builds the answer chain from one model id; `agent eval --model` passes it and adds a note.
- Decision rule: Sonnet stays first unless Haiku passes every case; either way the README states the numbers.

## Tasks

1. Save spec documentation.
2. Config, settings, usage fields, `--model`, tests; ruff; pytest; smoke.
3. Live runs: `v9-baseline`, `v9-haiku`.
4. README cost section, roadmap; commit; push; post-deploy verify.
