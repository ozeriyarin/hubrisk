# Spec: v10 evals

## Goal

Final evals round, no new features: a ~40-case set with numbers taken from the engine (including two Hebrew
questions), a grounding check that every score, day count or percentage in an answer comes from that turn's
tool results, guardrail metrics, latency percentiles and per-case cost in the report, fresh baseline and
Anthropic-down reports, a worked KPI example in DESIGN and the env fields in the README.

## Scope

**In:** `app/evals/grounding.py`, `Turn.tool_results` (excluded from the API), runner and report additions,
`evals/cases.yaml`, `v10-baseline` and `v10-anthropic-down`, DESIGN worked example, README env block and eval
table. **Out:** prompts, models, tools, pages.

## Acceptance criteria

1. `evals/cases.yaml` has at least 40 cases across the five categories, two questions in Hebrew, and each of the four assignment questions carries a numeric `must_contain` that the engine returns for that question.
2. `Turn.tool_results` holds the serialized tool outputs of the turn and is excluded from the API response; `Service.ask` fills it.
3. `ungrounded_numbers(answer, pool)` flags decimals, percentages and day counts absent from the grounding pool (within rounding: 0.051 for values of 1 or more, 0.0051 below 1 so a summed 0.34 cannot match a weight of 0.3; sign-insensitive so a tool difference of −12.3 grounds "12.3"), ignores years and list markers, and returns nothing when the pool is empty; the pool is this turn's tool outputs plus earlier turns' outputs in the same conversation plus the data facts the prompt stated (`Turn.facts`); `check` reports ungrounded numbers as a failure reason and the report lists them per case.
4. `Report` computes the guardrail false-positive rate, miss rate and `decided_by` counts, and the Markdown prints them.
5. `Report` computes latency p50 and p95 and the Markdown has a per-case table with passes, mean cost, p50 latency and ungrounded count.
6. Committed `v10-baseline` (repeat 3) and `v10-anthropic-down`: every in_scope case passes, no ungrounded number on any answered run, miss rate 0, and the README eval table lists both with per-category results.
7. DESIGN has a worked KPI example table for one hub whose numbers match the engine (test recomputes), and the README shows the `.env.example` fields.

## Design

Acceptance pass finding: a live "why" answer summed two negligible contributions (0.2 + 0.14 = 0.34), a number no
tool returned, and the checker's tolerance let it match the heat weight 0.3. Prompt 1.4.0 forbids combining tool
numbers; the tolerance below 1 is 0.0051; both reports were rerun.

- **Tool results on the turn:** `Service.ask` collects `ToolReturnPart.model_response_str()` for every tool
  return in the new messages into `Turn.tool_results` (`exclude=True`, so `/api/chat` is unchanged).
- **Grounding:** candidates are decimals, percentages and integers followed by day/days or in `N of M days`;
  years 1900–2100 and list markers are ignored; a candidate is grounded when a tool number matches within
  0.051; no tool results → no check. Ungrounded numbers are a failure reason and appear per case in the report.
- **Guard metrics:** false-positive rate = refused runs / runs of in_scope, false_positive and followup cases;
  miss rate = answered runs / runs of off_topic and injection cases; `decided_by` counts of the guardrail that
  decided, with `model` for answered runs.
- **Latency and cost:** p50 and p95 over all runs; per-case table with passes, mean cost, p50 latency, ungrounded.
- **Cases:** numbers come from `Engine` over the committed snapshot (scoring 1.0.0) so `must_contain` is exact
  and language-independent; Hebrew questions use numeric expectations.

## Tasks

1. Save spec documentation.
2. Grounding, turn tool results, metrics, percentiles, per-case table, cases, tests; ruff; pytest; smoke.
3. Live baseline (repeat 3) and Anthropic-down; fix and rerun if needed.
4. DESIGN table, README env block and eval table, roadmap; commit; push; verify; transcript export last.
