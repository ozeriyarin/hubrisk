# References for v1 hubs and data

## In this repo

- `src/app/config.py` — versioned YAML loaders (`load_agent_config`, `load_prices`); `Settings` pattern for the
  two new env fields.
- `src/app/llm/models.py::retrying_http_client` — the httpx2 client with tenacity retries; takes `wrapped=` so
  tests pass `httpx2.MockTransport`. Both data clients are built on it.
- `src/app/cli.py::compose` — the only composition root; v1 adds registry, store and NWS client there.
- `src/app/api/app.py::Health` — extended with `data`.
- `tests/fakes.py`, `tests/conftest.py` — fixture style to follow.

## External APIs

- Open-Meteo archive: `https://archive-api.open-meteo.com/v1/archive?latitude=&longitude=&start_date=&end_date=&daily=...&timezone=`.
  Response: `daily.time[]` plus one array per variable, and `daily_units{}`. No key.
- NOAA NWS: `https://api.weather.gov/points/{lat},{lon}` → `properties.forecast` URL →
  `properties.periods[]`; `https://api.weather.gov/alerts/active?point={lat},{lon}` → `features[].properties`.
  Requires a `User-Agent` header. No key.
- DuckDB Python: `duckdb.connect()`, `read_parquet`, `COPY (...) TO 'file' (FORMAT PARQUET)`.
