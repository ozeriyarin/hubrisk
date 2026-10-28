# Spec: v6 header polish

## Goal

Replace the chat header's operator detail (version, model chain, guard) with the product name and an approved
tagline, so the first thing an analyst reads is what the tool is for.

## Scope

**In:** header markup and the health display in `index.html`; README chat-page note; roadmap renumbering
(alerts → v7, voice → v8). **Out:** everything else.

## Acceptance criteria

1. The chat page header shows "HubRisk agent" and the tagline "Weather disruption risk across the US hub network", and does not render the model chain, guard or version in the header.
2. The page still shows a visible unhealthy state when `/health` is not `ok`, without listing models.
3. README's chat page section mentions the header, and the roadmap lists v6 header polish as shipped with alerts as v7 and voice as v8.
4. Follow-up from owner testing: `INSTRUCTIONS` forbids restating thresholds or definitions in the answer (they belong in `limitations`), gives bands and trends only when asked, and formats "why" answers as one sentence with the score and main driver, only the material hazards with mean days and weighted contribution, one sentence for negligible hazards, an offer of the breakdown, under 100 words; the trend fields carry a unit (`trend_unit`); `EvalCase` has `max_words` and the two "why" cases are capped; `max_chars` defaults to 1000; `PROMPT_VERSION` is 1.3.0 and a new baseline `v6-baseline` is committed with every in_scope case passed and no run over its caps.
5. Follow-up from owner testing: the sources line is collapsed into the details toggle; limitations stay visible on every answer. (Superseded by round 2, criterion 8: sources visible, limitations in the toggle.)
6. Round 2: the input placeholder rotates on page load among the four assignment questions, prefixed "e.g.".
7. Round 2: `REFUSAL_OFF_TOPIC` is a fixed string that names the scope (weather disruption risk for the US distribution hubs, ranking and comparing hubs, hazard statistics per hub and year, current alerts and forecast) and gives one example question.
8. Round 2: limitations are inside the details toggle, sources stay visible by default, and the toggle label reads "limits and run details".
9. Round 2: a one-sentence footer under the input says scores are estimates from public weather data and the hazard thresholds are assumptions, so verify before investment decisions.
10. Round 2: the mic and speaker buttons use inline SVG line icons of the same size and stroke; no emoji glyphs.
11. Round 2: the README evals section lists every committed report with cases passed per category, cost and the models that served, and states that the Anthropic-down run proves fallback.
12. Round 2: the page has no sticky header and no theme toggle; it follows the system colour scheme.
13. Round 3 (phone test): sending a message scrolls the page to the new bubble, and the page scrolls again once the answer and its meta are rendered; the last bubble keeps clear of the sticky input bar.
14. Round 3 (phone test): the input bar fits the viewport on a phone: the input can shrink (`min-width:0`), the buttons never grow or wrap, and narrow screens use tighter button padding.

## Design

Round 2 (owner tested v6/v7/v8 live): placeholder rotation, informative refusal, limitations into the toggle
with sources visible, footer disclaimer, line icons, eval results in the README, no sticky header or theme toggle.

Follow-up (owner tested v5 live): answers still quoted rule text such as "(flood proxy, >= 25 mm/day)"; the
prompt now sends that to `limitations`, and the sources line joins the technical fields in the toggle.

Static title and tagline in the header; the `/health` fetch stays but only drives a short status note
("offline" or a non-ok status). Model chain and version remain on `/health` and inside each answer's details
toggle.

## Tasks

1. Save spec documentation.
2. Header change, `tests/test_v6_header_polish.py`, README, roadmap; ruff; pytest; commit; push.
3. Confirm the live page after the auto-deploy.
