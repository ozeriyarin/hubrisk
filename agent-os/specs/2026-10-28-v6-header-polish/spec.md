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

## Design

Static title and tagline in the header; the `/health` fetch stays but only drives a short status note
("offline" or a non-ok status). Model chain and version remain on `/health` and inside each answer's details
toggle.

## Tasks

1. Save spec documentation.
2. Header change, `tests/test_v6_header_polish.py`, README, roadmap; ruff; pytest; commit; push.
3. Confirm the live page after the auto-deploy.
