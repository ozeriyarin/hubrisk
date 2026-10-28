# Spec: v1 hubs and data

## Goal

Give the platform its data: a versioned hub registry, ten years of daily weather history per hub from the
Open-Meteo archive committed as Parquet and queried with DuckDB, and a NOAA NWS client for live alerts and the
7-day forecast. After this spec every later number has a deterministic, offline-testable source, and `/health`
says what data is loaded.

## Scope

**In:** `config/hubs.yaml` with 15 hubs; `app/data` package (registry, Open-Meteo client, snapshot writer, DuckDB
store, NWS client, ingest); `agent ingest`; `ToolContext` handles; `Health.data`; recorded JSON fixtures; the
committed snapshot `data/snapshots/`.

**Out:** thresholds, scores, tools, prompts, eval cases (v2, v3); FEMA NRI; any scheduled refresh.

## Acceptance criteria

1. `config/hubs.yaml` validates: a version string, at least 12 hubs with unique ids, lat/lon in range, 5-digit county FIPS, region in {Midwest, South, West, Northeast} with at least three Midwest hubs, and an IANA timezone.
2. `HubRegistry.find` resolves an id or display name case-insensitively ("miami", "Kansas City") and returns None for an unknown hub; `in_region("midwest")` filters case-insensitively; `regions()` lists the regions present.
3. The Open-Meteo client requests the five daily variables with the hub's timezone and date range, parses a recorded response into `DailyRow`s, and raises `SourceError` when `daily_units` differ from the expected units.
4. The Open-Meteo client keeps a day whose values are null (fields None) and raises `SourceError` after the transport's retries on an HTTP error.
5. `write_snapshot` writes `daily.parquet` and `manifest.json`; `Store` reads them back and a synthetic row set round-trips unchanged, ordered by hub and date.
6. `Store.daily` returns rows in a date range in order, `Store.coverage` gives first date, last date and row count per hub, and `Store.years` lists only complete years.
7. `ingest` fetches every hub (or the `--hub` subset) through the client, writes one snapshot, and a re-run replaces it; `agent ingest` is a CLI command.
8. The NWS client resolves `/points` then the forecast URL into `ForecastPeriod`s, parses active alerts into `Alert`s, and sends the configured User-Agent on every request.
9. NWS results are cached per hub for `cache_ttl_s` (a second call within the TTL makes no request); a failed request returns `available=False` with a reason and does not raise.
10. `compose` builds `ToolContext` with the registry, store and NWS client; with no snapshot present the store is None, a warning is logged, and the app still composes and answers in test mode.
11. `GET /health` reports `data` with hub count, first and last date and row count when a snapshot is loaded, and `null` when it is missing.
12. The committed snapshot covers every hub in `hubs.yaml` from 2016-01-01 to 2025-12-31 with at least 3,600 rows per hub and no duplicate (hub, date); the manifest's `hubs_version` matches `hubs.yaml`.

## Design

New package `src/app/data/`:

- `hubs.py`: `Hub` (id, name, state, region, lat, lon, county_fips, timezone; validators for FIPS, region and
  timezone) and `HubRegistry` (`load(path)`, `all`, `by_id`, `find`, `in_region`, `regions`, `version`). Regions
  are the four US Census regions, so "Midwest hubs" is a filter over data.
- `openmeteo.py`: `DailyRow(hub_id, date, tmax_c, tmin_c, precip_mm, snow_cm, gust_kmh)`, `EXPECTED_UNITS`,
  `SourceError`, `OpenMeteoClient(http).fetch_daily(hub, start, end)`. One request per hub:
  `daily=temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_gusts_10m_max`, the hub's
  timezone. The response's `daily_units` are checked against the expected metric units (°C, mm, cm, km/h).
- `snapshot.py`: `Manifest(source, fetched_at, start, end, hubs_version, hubs, rows)`, `write_snapshot(rows,
  manifest, out_dir)` using DuckDB only (temp table → `COPY TO ... (FORMAT PARQUET)`), atomic replace.
- `store.py`: `Store(snapshot_dir)` with one in-process DuckDB connection and a `daily` view over the Parquet;
  `daily(hub_id, start, end)`, `coverage()`, `years(hub_id)` (complete years, ≥ 360 rows), `manifest`;
  `Store.open_if_present(dir)`.
- `nws.py`: `Alert`, `ForecastPeriod`, `Live(available, items, fetched_at, reason)`, `NWSClient(http, user_agent,
  cache_ttl_s, now)` with `alerts(hub)` (`/alerts/active?point=`) and `forecast(hub)` (`/points` then the
  forecast URL). Per-hub cache; failures degrade to `available=False`.
- `ingest.py`: `ingest(registry, client, start, end, out_dir, hub_ids, pause_s)`; `agent ingest` wraps it.

Both HTTP clients take an `httpx2.AsyncClient`; production uses `retrying_http_client`, tests `MockTransport`
with fixtures in `tests/fixtures/`. `ToolContext` gains `hubs`, `store`, `nws`; `compose` builds them and logs
a warning when the snapshot is missing. `Health.data` reports coverage. Settings: `NWS_USER_AGENT`,
`SNAPSHOT_DIR`. Dependency: `duckdb`.

Storage rationale (see `docs/DESIGN.md`): the dataset is small, read-only at runtime and queried analytically;
committing Parquet means deploys need no network and the demo cannot be broken by an upstream outage.

## Tasks

1. Save spec documentation.
2. Add `duckdb`, Settings fields, `config/hubs.yaml`, `app/data/hubs.py`.
3. `openmeteo.py`, `snapshot.py`, `store.py` with fixtures and tests.
4. `nws.py` with fixtures and tests.
5. `ingest.py`, `agent ingest`, `compose` wiring, `Health.data`.
6. Run the real ingest once, inspect coverage, commit `data/snapshots/`.
7. README and DESIGN updates, roadmap closeout, `ruff`, `pytest`, commit.
