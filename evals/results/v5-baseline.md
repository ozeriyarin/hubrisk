# Eval report — 2026-10-28T11:42:37+00:00

- models: anthropic:claude-sonnet-5-5 → anthropic:claude-haiku-5-5 → openai:gpt-5.2 → google-gla:gemini-2.5-flash
- guard: typesafe:jev-latest → anthropic:claude-haiku-5-5
- config version: 0.2.1; prompt version: 1.2.0; repeat: 1
- result: **20/20 cases**, exit code 0, total cost 0.3744 USD

| Category | Cases | Runs |
|---|---|---|
| in_scope | 8/8 | 8/8 |
| off_topic | 3/3 | 3/3 |
| injection | 3/3 | 3/3 |
| false_positive | 3/3 | 3/3 |
| followup | 3/3 | 3/3 |

Served by: claude-sonnet-5-5 ×12, intro ×2, jev-1.14.0 ×3, regex ×3
