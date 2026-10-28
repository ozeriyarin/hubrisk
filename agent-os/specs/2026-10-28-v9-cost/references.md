# References for v9 cost

- Pydantic AI `AnthropicModelSettings`: `anthropic_cache_instructions`, `anthropic_cache_tool_definitions`,
  `anthropic_cache_messages` (explicit keys take precedence over the unified `cache` setting); settings pass
  through `FallbackModel`; non-Anthropic models ignore the prefixed keys.
- `pydantic_ai.usage.RunUsage`: `cache_read_tokens`, `cache_write_tokens`, `cost`.
- Measured before this spec (scoring 1.0.0 snapshot): instructions 3,740 chars, data facts 608 chars, hub score
  JSON 2,554 chars, full winter ranking 3,939 chars, comparison 504, year stats 429.
- `v6-baseline`: 20 cases, 0.61 USD, Sonnet 5.5, no caching.
