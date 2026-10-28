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
5. Follow-up from owner testing: the sources line is collapsed into the details toggle; limitations stay visible on every answer.

## Design

Follow-up (owner tested v5 live): answers still quoted rule text such as "(flood proxy, >= 25 mm/day)"; the
prompt now sends that to `limitations`, and the sources line joins the technical fields in the toggle.

Static title and tagline in the header; the `/health` fetch stays but only drives a short status note
("offline" or a non-ok status). Model chain and version remain on `/health` and inside each answer's details
toggle.

## Tasks

1. Save spec documentation.
2. Header change, `tests/test_v6_header_polish.py`, README, roadmap; ruff; pytest; commit; push.
3. Confirm the live page after the auto-deploy.
