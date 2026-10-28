# v9 cost — Shaping Notes

## Scope

Prompt caching on the Anthropic prefix, cache visibility in turns and reports, a single-model eval switch, and
two measured reports. Owner question: "can we lower the question cost?"

## Decisions

- Measure first: prefix ~3k tokens per request, 2–5 requests per turn, payloads modest. Caching the prefix is the
  dominant lever and changes nothing about the answers.
- A cheaper first model is tested with the eval set (`--model`), never switched on by assumption; the README
  reports the numbers either way and the owner decides.
- Cache tokens are surfaced end to end (`Turn` → `RunResult` → report) so the saving is auditable, not claimed.
- No prompt change here; the polish round's refusal string is a fixed string.

## Context

- **Visuals:** none. **References:** `app/agent/core.py::build_agent/Service.ask`, `app/evals/{runner,report}.py`,
  `app/cli.py::compose/eval_cmd`, Pydantic AI `AnthropicModelSettings` (`anthropic_cache_*`), `RunUsage.cache_*`.
- **Product alignment:** mission "spend is bounded"; budget standard (cost visible, no silent downgrade).

## Standards Applied

- ai-calls — settings through Pydantic AI; eval report with any model-path change.
- budget — cost stays measured per turn; cache reads priced by genai-prices.
- evals — committed reports, `--model` experiment recorded in notes.
- testing — offline tests on settings wiring and report rendering.
