# References for v7 alerts

- `src/app/data/nws.py` — `NWSClient.alerts/forecast` return `Live[Alert]` / `Live[ForecastPeriod]` with
  `available`, `items`, `reason`; `Alert.event/severity`, `ForecastPeriod.precipitation_chance/short_forecast`.
- `src/app/llm/budget.py` — SQLite usage pattern (`sqlite3.connect(..., isolation_level=None, check_same_thread=False)`).
- `src/app/api/app.py::create_app` — `require_admin(authorization)` for the run endpoint.
- `src/app/cli.py::serve` — where the scheduler attaches; `compose()` builds the alert service.
- `src/app/agent/tools.py::_current` — where `live_risk` is added to `CurrentConditions`.
- NWS CAP severities: Extreme, Severe, Moderate, Minor, Unknown.
