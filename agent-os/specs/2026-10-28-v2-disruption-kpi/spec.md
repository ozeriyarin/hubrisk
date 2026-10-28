# Spec: v2 disruption KPI

## Goal

Turn the daily history into the product's number: **expected disruption days per year, per hub and per hazard**,
with a year-to-year uncertainty band and a trend, and a weighted overall score from versioned thresholds and
weights. Ship the deterministic tools the agent will call. The LLM never produces a number; after this spec every
figure an answer can contain exists as a typed tool result.

## Scope

**In:** `config/scoring.yaml`; `app/scoring` (config, models, pure engine, cached `Engine`); tools `rank_hubs`,
`compare_hubs`, `hub_score`, `hub_year_stats`, `current_conditions`, `list_hubs` registered in the toolset;
`ToolContext.engine`; README assumptions and DESIGN scoring sections.

**Out:** prompts, eval cases, the real eval report (v3); FEMA NRI; calibration against outage records.

## Acceptance criteria

1. `config/scoring.yaml` validates: a version, five hazards each with a `DailyRow` variable, an operator (`>=` or `<=`), a threshold, a weight and a label; groups that reference known hazards only; loading rejects an unknown variable or hazard.
2. `hazard_days(rows, hazard)` counts threshold days per calendar year deterministically on a synthetic series with known exceedances, and a day whose value is None never counts.
3. `HazardScore` uses complete years only and carries per-year counts, mean, min, max, stdev (0 for a single year) and trend = mean(last half) − mean(first half), `None` below four complete years.
4. `HubScore.overall` equals Σ weight × mean, contributions are listed sorted descending, and scoring the same rows twice gives identical output.
5. `Engine.rank(scope, region)` orders hubs by the scope score (overall, one hazard, or a group = sum of its hazards) descending with ties broken by hub id, and a region filter uses the registry.
6. `Engine.compare(a, b, hazards)` reports per-hazard means, bands and differences for both hubs and names the higher hub per hazard.
7. `year_stats(rows, year)` reports days in the year (365/366), days with any snowfall and any precipitation, threshold days per hazard, extremes, and percentages computed from the real day count.
8. Tools never raise: an unknown hub, region, hazard or year returns `NotFound` listing valid values; a missing store returns `Unavailable` with a reason; every result carries `scoring_version` and `data_through`.
9. `rank_hubs`, `compare_hubs`, `hub_score`, `hub_year_stats`, `current_conditions` and `list_hubs` are registered beside `about`, and `current_conditions` returns alerts and forecast with their `available` flags from the NWS client.
10. On the committed snapshot: Minneapolis tops `winter` and at least three Midwest hubs rank above every South hub on it (Denver, in the West, ranks second), Houston or Miami tops `hurricane_flood`, Phoenix tops `heat`, and Denver's 2025 any-snow percentage equals the DuckDB count divided by 365.
11. `agent eval --test` on the committed cases exits 0 with the tools registered.
12. README documents every hazard rule and weight from `scoring.yaml` with the rationale and the heat caveat, and the documented thresholds match the file.

## Design

**KPI.** A disruption day is a day crossing an operational threshold. `config/scoring.yaml` (version 1.0.0):

| hazard | rule | weight | why |
|---|---|---|---|
| snow | `snow_cm >= 5` | 1.0 | heavy snowfall closes yards and roads |
| wind | `gust_kmh >= 70` | 1.0 | damaging gusts stop loading and flights |
| rain | `precip_mm >= 25` | 0.8 | heavy rain, the flood proxy |
| cold | `tmin_c <= -15` | 0.7 | extreme cold: equipment and staffing |
| heat | `tmax_c >= 38` | 0.3 | extreme heat slows work, rarely closes a hub |

Groups: `winter = snow + cold`, `hurricane_flood = rain + wind` (a proxy; the result says so), `heat = heat`.
Thresholds were chosen after measuring the snapshot so each hazard separates hubs; they are stated assumptions,
not calibrated to outage records.

**Per hazard:** complete years only (`Store.years`, ≥ 360 rows); per-year counts; mean (the expected disruption
days per year); min, max, sample stdev (0 with one year); trend = mean(last half of years) − mean(first half),
`None` below four years. **Overall** = Σ weight × mean, contributions sorted descending. Pure functions over
`DailyRow` lists in `app/scoring/engine.py`; `Engine(store, registry, config)` caches `HubScore` per hub.

**Rankings** sort by the scope (overall, a hazard, or a group = sum of its hazards' means) descending, ties by hub
id; a region filter uses `HubRegistry.in_region`. **Comparison** lists per hazard both means, bands, the
difference and the higher hub. **Year stats** give days in the year, any-snow and any-precipitation days,
threshold days, extremes and percentages over the real day count.

**Tools** (`app/agent/tools.py`) are thin: resolve names through the registry, call the engine or NWS client, and
return typed models. They never raise: `NotFound(kind, query, valid)` and `Unavailable(reason)` are return values.
Every result carries `scoring_version` and `data_through`. `current_conditions` returns live NWS alerts and
forecast beside, never inside, the historical score.

## Tasks

1. Save spec documentation.
2. `config/scoring.yaml`, `app/scoring/config.py`, `app/scoring/models.py`.
3. `app/scoring/engine.py` with table-driven tests on synthetic rows.
4. Tools, `ToolContext.engine`, `compose` wiring.
5. `tests/test_v2_disruption_kpi.py`.
6. README assumptions, DESIGN scoring section, roadmap; `ruff`, `pytest`, `agent eval --test --tag ci-smoke`; commit.
