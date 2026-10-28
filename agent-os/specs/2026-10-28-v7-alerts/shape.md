# v7 alerts — Shaping Notes

## Scope

Live risk level per hub from NWS, stored and diffed on a schedule, webhook on change, admin trigger endpoint,
level in the chat tool.

## Decisions

- "Risk score changes" is read as live risk: the historical KPI only changes with a new snapshot, the live level
  changes daily. The two stay separate, as the scoring standard requires.
- Levels are a small ordinal (none/watch/warning) derived from NWS severity, not a new number the model could
  confuse with the KPI.
- State lives in the existing SQLite file; a restart records a baseline and alerts nothing, which is the honest
  behaviour on an ephemeral disk.
- Two triggers, both free: the in-process loop and a GitHub Actions cron that also wakes the free instance.
- Webhook failures never raise; without a URL the check still runs and logs.
- No prompt change: the tool result gains a field, the model already explains tool results.

## Context

- **Visuals:** none. **References:** `app/data/nws.py` (`Live`, `Alert`, `ForecastPeriod`), `app/llm/budget.py`
  (SQLite pattern), `app/api/app.py::require_admin`, `app/cli.py::serve`.
- **Product alignment:** mission "now vs history"; brief bonus item.

## Standards Applied

- data-sources — NWS results degrade, never crash; cache respected.
- scoring — live risk reported beside, never blended into, the historical score.
- secrets-and-config — `ALERT_WEBHOOK_URL` secret, `ALERT_INTERVAL_MIN` plain.
- testing — table-driven assess, MockTransport webhook, scheduler with a tiny interval.
- deployment — render.yaml and the scheduled workflow.
