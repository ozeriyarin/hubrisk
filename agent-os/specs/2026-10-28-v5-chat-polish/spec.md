# Spec: v5 chat polish

## Goal

Four small fixes from testing the deployed chat before submission: a favicon, shorter answers, greetings and
capability questions answered in scope without a paid model run, and a quieter meta line that keeps sources and
limitations visible while collapsing the technical fields. No new dependency, no slash commands.

## Scope

**In:** inline SVG favicon; `AnswerOut.answer` cap and a brevity rule; `EvalCase.max_chars` length check;
`intro_reply` short-circuit in `Service.ask`; greeting cases in both eval sets; chat page meta layout;
`agent verify` asks a scored question; new baseline report; docs.

**Out:** anything operator-facing in the chat, new tools, scoring changes.

## Acceptance criteria

1. The chat page declares an inline SVG favicon (`rel="icon"`, `data:image/svg+xml`) and loads no icon file.
2. `AnswerOut.answer` has `max_length` 2000 and `INSTRUCTIONS` contains the brevity rule (lead with the ranking or number; 3–6 sentences; detail only when asked).
3. `EvalCase.max_chars` defaults to 1200 and `check` reports an answer longer than it; the live sample-question cases rely on the default.
4. `intro_reply` returns the intro for greetings and capability questions (`hi`, `Hello!`, `what can you do?`, `What can you help me with`, `help`) and `None` for real questions, including ones that start with a greeting.
5. `Service.ask` answers an intro turn with status `answered`, `guardrail="intro"`, no tool, zero cost and no ledger row; the answer lists the four example questions.
6. Both eval sets contain `greet-hi` and `greet-what-can-you-do` expecting `answered` with "midwest" in the answer; `agent eval --test` exits 0.
7. The page renders limitations outside the toggle and model, tools, cost and latency inside a `<details>` element (sources moved into the toggle by the v6 follow-up); the page contains no slash-command handling.
8. `evals/results/v5-baseline.json` is committed for `PROMPT_VERSION` 1.2.0 with every in_scope case passed and no run over `max_chars`; the README verification record is refreshed after the deploy.

## Design

- **Favicon:** `<link rel="icon" href="data:image/svg+xml,…">` with a cloud over a hub dot in the page colours.
- **Brevity:** `AnswerOut.answer` `max_length` 2000 (hard stop; a validation failure retries once with the
  error). `INSTRUCTIONS` rule: lead with the ranking or the number, 3–6 sentences or a list of at most 5 short
  items, no tables, detail only when asked. `EvalCase.max_chars` (default 1200) checked by `runner.check`.
  `PROMPT_VERSION` 1.2.0.
- **Intro without a model:** `prompts.intro_reply(message)` matches a whole message that is a greeting or a
  capability question (anchored patterns, so "hi, which hub is worst for snow?" still goes to the model) and
  returns a fixed intro: one line on what HubRisk is plus the four example questions. `Service.ask` returns it
  right after the input checks with `guardrail="intro"`, `sources=["intro"]`: no guard, no reservation, no spend.
- **Meta line:** answered turns show `Sources:` and `Limitations:` lines; model, fallback, tools, cost and
  latency sit in a collapsed `<details>`; refusals keep their status text visible.
- **Verify:** `agent verify` asks "Which hub has the most heavy-snow days per year?" so it exercises the model
  and a tool, not the intro.

## Tasks

1. Save spec documentation.
2. Page, schema, prompts, intro short-circuit, eval length check, eval cases, verify question, tests; ruff; pytest; smoke.
3. Live baseline `v5-baseline`; wording fix once if needed.
4. Docs; commit; push; `agent verify` after the auto-deploy; README record; transcript re-export; final commit.
