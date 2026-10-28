# References for v2 disruption KPI

## In this repo

- `src/app/data/store.py` — `Store.daily(hub_id)` rows and `Store.years(hub_id)` complete years feed the engine;
  `Store.manifest.end` is `data_through`.
- `src/app/data/hubs.py` — `HubRegistry.find`, `in_region`, `regions` resolve user wording to data.
- `src/app/data/nws.py` — `NWSClient.alerts/forecast` return `Live` results for `current_conditions`.
- `src/app/agent/tools.py` — `ToolContext`, `build_toolset`, the `about` tool pattern (RunContext, Pydantic result).
- `src/app/config.py` — versioned YAML loader pattern for `config/scoring.yaml`.

## Measured on the snapshot (days per year, 2016–2025 average)

| hub | snow ≥ 5 cm | gust ≥ 70 km/h | rain ≥ 25 mm | tmax ≥ 38 °C | tmin ≤ −15 °C |
|---|---|---|---|---|---|
| minneapolis | 5.2 | 2.3 | 6.0 | 0.0 | 37.1 |
| denver | 4.7 | 3.0 | 1.2 | 0.5 | 14.3 |
| chicago | 3.3 | 6.9 | 6.4 | 0.0 | 10.1 |
| seattle | 1.0 | 8.6 | 5.3 | 0.0 | 0.0 |
| houston | 0.1 | 2.1 | 21.7 | 2.6 | 0.0 |
| miami | 0.0 | 3.1 | 9.4 | 0.0 | 0.0 |
| phoenix | 0.0 | 0.4 | 2.4 | 99.4 | 0.0 |
| dallas | 0.2 | 4.9 | 15.9 | 12.4 | 0.2 |
