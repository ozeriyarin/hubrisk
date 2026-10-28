# v6 header polish — Shaping Notes

## Scope

Owner feedback on the deployed chat header: product name plus a tagline instead of version and model chain.

## Decisions

- Title "HubRisk agent"; tagline "Weather disruption risk across the US hub network" (approved by the owner from
  three options).
- Operator detail stays reachable: `/health` and the per-answer details toggle.
- Health still fetched once so an unhealthy service is visible, as a status word only.
- Bonus items renumbered: v7 alerts, v8 voice.

## Context

- **Visuals:** the owner's screenshot of the current header. **References:** `src/app/api/static/index.html`.
- **Product alignment:** mission audience is analysts, not operators.

## Standards Applied

- testing — a criterion test over the page source; `test_api` title check unchanged.
- python-style — no backend change.
