# Data sources

- Hubs are data: `config/hubs.yaml` (id, name, lat, lon, region, county FIPS), validated by Pydantic at load. Region
  filters ("Midwest") read this file; the model never decides which hub belongs where.
- History comes from the Open-Meteo archive API (daily: snowfall, precipitation, wind gust max, temp max/min),
  2016–2025, fetched once by `agent ingest` and written to `data/snapshots/daily.parquet`, which is committed. A deploy
  never re-ingests; Render's ephemeral disk is irrelevant.
- Queries over history go through DuckDB in-process, reading the Parquet directly. One `Store` type wraps the
  connection; tests build it from a small fixture Parquet.
- Live conditions come from NOAA NWS (`api.weather.gov`: `/points`, `/alerts/active`, forecast). Every request sends a
  `User-Agent` with a contact as NWS requires. Results are cached per hub for 10 minutes.
- Each external client takes an `httpx2.AsyncBaseTransport`; tests use `MockTransport` with recorded JSON fixtures in
  `tests/fixtures/`. Never patch the network.
- Every snapshot carries `source`, `fetched_at` and the date range; the agent's `sources` field cites them so the
  answer says how old the data is.
- A failed live call degrades, not crashes: the tool returns `available=false` with a reason and the answer's
  `limitations` says live data was unavailable.
