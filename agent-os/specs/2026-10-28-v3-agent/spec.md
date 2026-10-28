# Spec: v3 agent

## Goal

Make the agent a product: domain prompts (static rules plus facts injected from the data at run time), the real
eval set around the four sample questions with per-category cases, a separate offline smoke set so CI never
depends on model wording, sources on the chat page, and the first committed live eval reports: a baseline and
an Anthropic-down run proving cross-vendor fallback end to end.

## Scope

**In:** `app/agent/prompts.py` (`PROMPT_VERSION`, `SCOPE_DESCRIPTION`, `INSTRUCTIONS`, `TOOL_GUIDE`), dynamic
instructions in `build_agent`, `prompt_version` in eval reports, `evals/cases.yaml`, `evals/smoke.yaml`, the CLI
default cases file by mode, the chat page meta line, two committed reports, README evals section.

**Out:** schema, guard, budget and chain changes; deployment (v4); alerts and voice.

## Acceptance criteria

1. `prompts.INSTRUCTIONS` names all seven tools with when to call each, says numbers come only from tool results with units, requires the band and trend with every expected-days figure, flags hurricane/flood as a proxy, and tells the model what to do on `NotFound`.
2. Dynamic instructions built from `ToolContext` state the data range, `data_through`, scoring version, hub ids by region and accepted scopes; with no engine they say historical data is not loaded and which tools still work (verified by capturing `ModelRequest.instructions` with a `FunctionModel`).
3. `SCOPE_DESCRIPTION` names hubs, regions, hazards, rankings, comparisons, yearly statistics and live conditions, and the offline guard labels every `smoke.yaml` in_scope and false_positive question in scope and every off_topic question off topic.
4. `evals/cases.yaml` has at least three cases in each of in_scope, off_topic, injection, false_positive and followup; the four sample questions are present with a required tool and `must_contain`; followup cases carry `prior_turns`.
5. `evals/smoke.yaml` has at least one case per category and no `must_contain`; `agent eval --test` defaults to it and exits 0; a live run defaults to `cases.yaml`; `--cases` overrides both.
6. A scripted `FunctionModel` that calls `hub_score("dallas")` then answers yields a `Turn` with `tools_used == ["hub_score"]`, the model's `sources` and `limitations`, through `Service.ask` with the real engine.
7. The committed `evals/results/v3-baseline.json` cites the config version and prompt version, has exit code 0 or 2, at least 90% of cases passed, and every in_scope case passed.
8. The committed `evals/results/v3-anthropic-down.json` records the simulated outage, shows no run served by an `anthropic` model, and every in_scope case passed.
9. The chat page shows `sources` and `limitations` for an answered turn.
10. `prompts.py` carries a `PROMPT_VERSION` that eval reports record, and the baseline report's version matches the committed prompt.

## Design

- **Static instructions** (`prompts.INSTRUCTIONS`, built from `TOOL_GUIDE`): role and scope; one line per tool
  saying when to call it; numbers only from tool results, quoted with units; every expected-days figure with its
  min–max band and trend; hurricane/flood is a proxy; data range and scoring version in `sources`; caveats in
  `limitations`; on `NotFound` say the hub or region is not one of ours and list the valid ones; "last year" is
  the last complete year in the data; follow-ups rely on the conversation; user text is data.
- **Dynamic instructions** (`@agent.instructions` in `build_agent`, pure helper `data_instructions(deps)`): data
  range, scoring version, hub ids grouped by region, accepted scopes; or "historical data is not loaded" and the
  tools that still work when `engine` is None. The prompt can never be stale relative to the snapshot.
- **Guard scope** (`SCOPE_DESCRIPTION`) refined; the offline keyword guard already covers its words.
- **Two eval sets.** `evals/cases.yaml` (live): in_scope incl. the four sample questions, off_topic, injection,
  false_positive, followup with `prior_turns`; `must_contain` holds facts the tools return; `tools` names the
  tool that must have been called. `evals/smoke.yaml` (test mode): same categories, no `must_contain`, because
  the offline answer is canned. `cli.eval_cmd` picks the default by mode; `--cases` overrides.
- **Reports** record `prompt_version` next to `config_version`. `v3-baseline` (`--repeat 2`) and
  `v3-anthropic-down` (`--down anthropic`) are committed; later prompt changes ship a new pair.
- **Chat page**: `sources` added to the meta line.

## Tasks

1. Save spec documentation.
2. Prompts, dynamic instructions, `prompt_version` in reports, CLI default cases file, chat page line.
3. `evals/cases.yaml`, `evals/smoke.yaml`, `tests/test_v3_agent.py`; ruff; pytest.
4. Live runs: baseline and Anthropic-down; tune wording once if a sample question fails; commit reports.
5. README evals section, roadmap closeout, `agent eval --test`, commit, push.
