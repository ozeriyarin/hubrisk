# Spec: v7 alerts

## Goal

The brief's bonus: a scheduled or webhook-triggered alert when a hub's risk changes. The historical score is
frozen with the snapshot; what changes is live risk from NOAA NWS alerts and the forecast. Add a deterministic
live risk level per hub, a scheduled check that records it and posts a webhook when a hub's level changes, an
admin endpoint for webhook-triggered runs, and the level inside the chat tool.

## Scope

**In:** `app/alerts.py` (assess, store, check, notifier, scheduler), `ALERT_WEBHOOK_URL` and
`ALERT_INTERVAL_MIN`, `GET /api/alerts`, `POST /api/alerts/run`, `agent alerts-check`, in-process scheduler in
`serve`, `.github/workflows/alerts.yml`, `current_conditions.live_risk`, docs.

**Out:** changes to the historical KPI, prompts or models (no new baseline); persistent state beyond the
existing SQLite file.

## Acceptance criteria

1. `assess` maps NWS events to hazards and severities to levels (table-driven), ignores non-hazard events, adds at most level 1 from the forecast, lists drivers, and returns `level=None` with a reason when live data is unavailable.
2. `AlertStore` persists the last level, drivers and time per hub in SQLite and returns `None` for a hub never checked.
3. `run_check` records every hub, returns one change per hub whose level differs from the stored one, and records a baseline without changes on the first run.
4. A notifier posts one JSON webhook per change with hub, name, previous, current, drivers and time; a failed post is logged and does not raise; without a webhook URL nothing is posted.
5. `agent alerts-check` runs one pass offline (test mode) and prints every hub with its level; exit 0.
6. `GET /api/alerts` lists the current level per hub; `POST /api/alerts/run` requires the admin token, runs a check and returns the changes.
7. `serve` starts a periodic check when `ALERT_INTERVAL_MIN > 0` and not otherwise; the loop runs with an injectable interval and stops cleanly.
8. `.github/workflows/alerts.yml` runs on a 30-minute schedule, calls the run endpoint with secrets, and skips when they are unset; `render.yaml` sets `ALERT_INTERVAL_MIN` and lists `ALERT_WEBHOOK_URL` as `sync: false`.
9. `current_conditions` includes `live_risk` with level, label and drivers.
10. README "Alerts" section and DESIGN describe the design; roadmap marks v7 shipped.

## Design

- **Level** 0 none, 1 watch, 2 warning. Alert events map to hazards by keyword (cold: cold/freeze/wind chill/
  frost; snow: snow/blizzard/winter/ice/sleet; heat; rain: flood/hurricane/tropical/storm/rain; wind: wind/gale,
  checked in that order so "Wind Chill" is cold and "Winter Storm" is snow). Severity Extreme/Severe → 2,
  Moderate/Minor/unknown → 1. Forecast periods with ≥ 70% precipitation chance and snow/storm/heavy rain text add
  at most level 1. Drivers list every alert and period that fired. Both live sources unavailable → `level=None`.
- **Store** `live_risk` table in the SQLite file next to the ledger. **Check** assesses every hub, diffs against
  the stored level (only integer-to-integer differences count), stores, and posts one webhook per change.
- **Notifier** posts JSON to `ALERT_WEBHOOK_URL` through an injectable `httpx2.AsyncClient`; failures are logged.
- **Scheduler** `Scheduler(job, interval_s)` started on app startup when `ALERT_INTERVAL_MIN > 0`; the GitHub
  Actions cron is the second trigger and wakes a sleeping instance.
- **Tool** `current_conditions` returns `live_risk` next to the raw alerts and forecast.

## Tasks

1. Save spec documentation.
2. `alerts.py`, Settings, tests 1–4.
3. CLI, API, scheduler, workflow, render.yaml, tool field; tests 5–10.
4. Docs; ruff; pytest; smoke; commit; push; post-deploy `GET /api/alerts`.
