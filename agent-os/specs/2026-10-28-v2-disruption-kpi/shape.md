# v2 disruption KPI — Shaping Notes

## Scope

The scoring engine (disruption days per year per hub and hazard, band, trend, weighted overall) and the six
deterministic tools. No prompts or eval cases.

## Decisions

- Thresholds chosen after measuring the committed snapshot so every hazard discriminates between hubs; weights
  express operational impact; both are versioned in `config/scoring.yaml` and documented in the README as
  assumptions.
- Heat gets a low weight (0.3) and a stated caveat: Phoenix would otherwise dominate every overall ranking.
- Hurricane and flood exposure is a proxy (heavy rain + damaging gusts) until FEMA NRI is wired in; the group
  result says so.
- Complete years only, so a partial year never deflates a mean. Trend is last half minus first half of complete
  years, `None` below four years.
- The engine is pure Python over `DailyRow` lists (table-testable without DuckDB); `Engine` caches per hub.
- Tools never raise. `NotFound` and `Unavailable` are return values, which also keeps the test-mode `TestModel`
  (schema-generated arguments) from breaking the smoke eval.
- Tools are registered now so the offline loop is exercised end to end; v3 writes the prompts and eval cases.

## Context

- **Visuals:** none.
- **References:** `app/data/store.py`, `app/data/hubs.py`, `app/data/nws.py`, `app/agent/tools.py`, `app/config.py`.
- **Product alignment:** mission KPI definition; `agent-os/standards/scoring.md`.

## Standards Applied

- scoring — the subject of this spec.
- python-style — `scoring` package, Pydantic models at the tool boundary.
- testing — table-driven engine tests, criterion tests in `tests/test_v2_disruption_kpi.py`.
- data-sources — tools read through `Store` and `NWSClient`; live failures surface in `limitations`.
- ai-calls — every tool returns a typed model; the model quotes, never computes.
