# Scoring

- The KPI is **expected disruption days per year, per hub and per hazard**, computed by `app/scoring` from daily
  history. No LLM code path produces, rounds or adjusts a number.
- A disruption day is a day crossing an operational threshold. Thresholds and hazard weights live in
  `config/scoring.yaml` with a `version` string; every score cites that version. Changing it is a versioned commit.
- Hazards: `snow`, `wind`, `rain`, `heat`, `cold`. "Winter" = snow + cold; "hurricane/flood" = rain + wind, stated as
  a proxy in `limitations` unless FEMA NRI data is wired in.
- Every per-hazard figure ships with its uncertainty: per-year counts, mean, min, max, stdev across years, and a
  5-year trend (last five years' mean minus the previous five). Never return a bare mean.
- Overall score = weighted sum of hazard means. Rankings are stable: ties break by hub id. Same input, same output;
  the engine is pure and table-tested.
- Tools return `HazardScore` / `HubScore` Pydantic models, never dicts; the model sees names, numbers and units it
  must quote verbatim.
- Percent-of-days questions use a calendar year with the actual day count (365/366) and say which year was used.
- Live risk ("right now") is a separate signal from NWS alerts and forecast; it is reported next to the historical
  score, never blended into it.
