# Eval report — 2026-10-28T10:51:13+00:00

- models: openai:gpt-5.2 → google-gla:gemini-2.5-flash
- guard: typesafe:jev-latest → anthropic:claude-haiku-5-5
- config version: 0.2.1; prompt version: 1.1.0; repeat: 1
- result: **18/18 cases**, exit code 0, total cost 0.0354 USD

| Category | Cases | Runs |
|---|---|---|
| in_scope | 6/6 | 6/6 |
| off_topic | 3/3 | 3/3 |
| injection | 3/3 | 3/3 |
| false_positive | 3/3 | 3/3 |
| followup | 3/3 | 3/3 |

Served by: gemini-2.5-flash ×12, jev-1.14.0 ×3, regex ×3

## Notes

- simulated outage: anthropic
