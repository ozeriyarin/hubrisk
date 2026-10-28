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

## Phase 1: MVP (must ship)

1. ~~v0 platform~~ shipped.
2. ~~v1 hubs and data~~ shipped.
3. ~~v2 disruption KPI~~ shipped.
4. ~~v3 agent~~ shipped.
5. **v4 deploy** — Render live, `/health` and chat verified from the public URL, provider-side spend limits set,
   README (run instructions, assumptions, uncertainty, scoping, live URL + verification date), `docs/DESIGN.md`
   (architecture, repository structure, data storage choice), session transcript exported to `docs/ai-session/`.

## Phase 2: Post-launch (bonus, only if time remains)

6. **v5 alerts** — scheduled job recomputes current-risk score per hub from NWS alerts/forecast and fires a webhook
   when a hub's score crosses a band.
7. **v6 voice** — browser speech-to-text and text-to-speech in the chat page.
8. **FEMA NRI** — county-level hurricane/flood risk as a secondary signal in the KPI.

## Out of scope

Multi-user auth, persistent sessions, streaming replies, mobile client, calibration against real outage data.
