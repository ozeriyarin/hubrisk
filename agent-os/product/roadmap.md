# Roadmap — HubRisk

~24-hour take-home. Each version is one Agent OS spec under `agent-os/specs/<date>-<slug>/` and one commit series.
Order is fixed: spec → code + tests → ruff → pytest → eval report (when prompts/models change) → README/roadmap → commit.

## Phase 1: MVP (must ship)

1. **v0 platform** — model chain + retries + cross-vendor fallback, guard (Jev → Haiku), budget ledger, FastAPI
   API + chat page, sessions, rate limits, eval runner, offline tests, CI, Render Blueprint. `MODEL_MODE=test`
   keyless run.
2. **v1 hubs and data** — hub registry (`config/hubs.yaml`: 12–15 hubs, lat/lon, region, county FIPS), Open-Meteo
   archive ingest 2016–2025 into Parquet committed to the repo, DuckDB query layer, NOAA NWS client (active alerts,
   7-day forecast) with offline fakes.
3. **v2 disruption KPI** — scoring engine: per-hazard disruption days/year from thresholds, uncertainty band, 5-year
   trend, weighted overall score from versioned YAML; tools: rank hubs (filter by region/hazard), compare hubs,
   hub stats (e.g. % snow days in a year), explain hub score, current conditions.
4. **v3 agent** — prompts, tools wired, `AnswerOut` schema enforced, eval cases per category (in_scope, off_topic,
   injection, false_positive, followup) covering the four sample questions, first committed eval report.
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
