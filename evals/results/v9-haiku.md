# Eval report — 2026-10-28T12:51:54+00:00

- models: anthropic:claude-haiku-5-5
- guard: typesafe:jev-latest → anthropic:claude-haiku-5-5
- config version: 0.3.0; prompt version: 1.3.0; repeat: 1
- result: **20/20 cases**, exit code 0, total cost 0.0072 USD

| Category | Cases | Runs |
|---|---|---|
| in_scope | 8/8 | 8/8 |
| off_topic | 3/3 | 3/3 |
| injection | 3/3 | 3/3 |
| false_positive | 3/3 | 3/3 |
| followup | 3/3 | 3/3 |

Served by: claude-haiku-5-5 ×12, intro ×2, jev-1.14.0 ×3, regex ×3

cache: read 60184 tokens, write 14503, 45% of input served from cache

## Notes

- single model: anthropic:claude-haiku-5-5
