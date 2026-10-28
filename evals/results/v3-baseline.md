# Eval report — 2026-10-28T10:44:46+00:00

- models: anthropic:claude-sonnet-5-5 → anthropic:claude-haiku-5-5 → openai:gpt-5.2 → google-gla:gemini-2.5-flash
- guard: typesafe:jev-latest → anthropic:claude-haiku-5-5
- config version: 0.2.1; prompt version: 1.1.0; repeat: 2
- result: **18/18 cases**, exit code 0, total cost 0.7694 USD

| Category | Cases | Runs |
|---|---|---|
| in_scope | 6/6 | 12/12 |
| off_topic | 3/3 | 6/6 |
| injection | 3/3 | 6/6 |
| false_positive | 3/3 | 6/6 |
| followup | 3/3 | 6/6 |

Served by: claude-sonnet-5-5 ×24, jev-1.14.0 ×6, regex ×6
