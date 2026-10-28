# Roadmap — HubRisk

~24-hour take-home. Each version is one Agent OS spec under `agent-os/specs/<date>-<slug>/` and one commit series.
Order is fixed: spec → code + tests → ruff → pytest → eval report (when prompts/models change) → README/roadmap → commit.

## Shipped

- **v0 platform** (2026-10-28, spec `agent-os/specs/2026-10-28-v0-platform`): model chain + retries +
  cross-vendor fallback, guard (Jev → Haiku, keyword double offline), budget ledger, FastAPI API + chat page,
  sessions, rate limits, eval runner, 77 offline tests incl. 20 criterion tests, CI, Render Blueprint.

- **v1 hubs and data** (2026-10-28, spec `agent-os/specs/2026-10-28-v1-hubs-and-data`): 15-hub registry,
  Open-Meteo 2016–2025 daily history committed as Parquet (54,795 rows), DuckDB store, NWS alerts/forecast client
  with cache and degradation, `agent ingest`, `/health` data coverage, 12 criterion tests.

- **v2 disruption KPI** (2026-10-28, spec `agent-os/specs/2026-10-28-v2-disruption-kpi`): versioned thresholds and
  weights, pure scoring engine (days/year per hazard, band, trend, weighted overall), six deterministic tools that
  never raise, 12 criterion tests.

- **v3 agent** (2026-10-28, spec `agent-os/specs/2026-10-28-v3-agent`): domain prompts with dynamic data facts,
  guard context for follow-ups, live eval set (18 cases, 5 categories) + offline smoke set, baseline report 18/18,
  Anthropic-down fallback report, transport HTTP errors now fall over instead of crashing.

- **v4 deploy** (2026-10-28, spec `agent-os/specs/2026-10-28-v4-deploy`): live at https://hubrisk.onrender.com
  (Render Blueprint, free tier), `agent verify` record in the README, provider-side limits set 2026-10-28,
  DESIGN deployment section, full session transcript under `docs/ai-session/`.

- **v5 chat polish** (2026-10-28, spec `agent-os/specs/2026-10-28-v5-chat-polish`): favicon, brevity rule +
  schema cap + eval length check, free intro for greetings, sources/limitations visible with technical fields
  behind a toggle, baseline `v5-baseline`.

- **v6 header polish** (2026-10-28, spec `agent-os/specs/2026-10-28-v6-header-polish`): header shows
  "HubRisk agent" and the tagline instead of version and model chain; follow-up from live testing: "why" answer
  format and word caps (prompt 1.3.0, baseline `v6-baseline`); round 2: rotating example placeholder,
  informative refusal, limitations in the toggle with sources visible, footer disclaimer, line icons.

- **v7 alerts** (2026-10-28, spec `agent-os/specs/2026-10-28-v7-alerts`): live risk level per hub from NWS,
  scheduled check + webhook on change, `agent alerts-check`, `/api/alerts`, GitHub Actions cron trigger.

- **v8 voice** (2026-10-28, spec `agent-os/specs/2026-10-28-v8-voice`): browser speech-to-text mic button and
  spoken answers (speaker toggle), Web Speech API only.

- **v9 cost** (2026-10-28, spec `agent-os/specs/2026-10-28-v9-cost`): Anthropic prompt caching of the static
  prefix, cache tokens in turns and reports, `agent eval --model` experiments, measured baseline and Haiku run.

## Phase 1: MVP (must ship)

1. ~~v0 platform~~ shipped.
2. ~~v1 hubs and data~~ shipped.
3. ~~v2 disruption KPI~~ shipped.
4. ~~v3 agent~~ shipped.
5. ~~v4 deploy~~ shipped.

## Phase 2: Post-launch (bonus, only if time remains)

6. ~~v7 alerts~~ shipped.
7. ~~v8 voice~~ shipped.
8. **FEMA NRI** — county-level hurricane/flood risk as a secondary signal in the KPI.

## Out of scope

Multi-user auth, persistent sessions, streaming replies, mobile client, calibration against real outage data.
