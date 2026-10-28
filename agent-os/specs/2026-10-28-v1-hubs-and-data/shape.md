# v1 hubs and data — Shaping Notes

## Scope

Hub registry, Open-Meteo daily history 2016–2025 as committed Parquet queried by DuckDB, NOAA NWS live client,
`agent ingest`, `ToolContext` handles and `/health` coverage. No scoring, tools or prompts.

## Decisions

- 15 hubs in the four US Census regions; `county_fips` kept for an optional FEMA NRI signal.
- Open-Meteo archive, five daily variables, one request per hub; units verified from the response's
  `daily_units`, not assumed from docs.
- Snapshot written and read with DuckDB only (no pandas/pyarrow); atomic replace; manifest records provenance.
- NWS requires a User-Agent; it comes from `NWS_USER_AGENT` with a default naming the repo. Results cached per
  hub for ten minutes; failures degrade to `available=False` and never raise into the agent.
- Both clients take an `httpx2.AsyncClient` so tests inject `MockTransport` with recorded fixtures.
- A missing snapshot is a warning, not a crash: the app serves, `/health` says `data: null`.
- `Store.years` counts a year complete at ≥ 360 rows so a few missing days do not drop a year.

## Context

- **Visuals:** none.
- **References:** v0 `app/config.py` loaders, `app/llm/models.py::retrying_http_client`, `tests/fakes.py`,
  `cli.compose`, `app/api/app.py::Health`.
- **Product alignment:** mission "regions are data, not guesses" and "now vs history"; tech-stack storage choice.

## Standards Applied

- data-sources — the subject of this spec.
- python-style — new `data` package, Pydantic at every boundary, typed errors.
- secrets-and-config — `NWS_USER_AGENT`, `SNAPSHOT_DIR`; versioned `hubs.yaml`.
- testing — MockTransport fixtures, synthetic Parquet, criterion tests in `tests/test_v1_hubs_and_data.py`.
