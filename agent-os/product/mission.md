# Product Mission — HubRisk

## Problem

A US logistics company runs regional distribution hubs. Severe weather shuts hubs down, delays shipments and
costs money. Each year the company funds resilience upgrades for only a handful of hubs, so analysts must decide
which hubs are most exposed to weather disruption. Today that judgement is manual: pulling weather history per
site, eyeballing it, and arguing about what "exposed" means. The result is inconsistent, hard to explain and hard
to repeat next year.

## Target Users

Risk and operations analysts at the logistics company who prioritise the annual resilience budget, and the
managers they report to. They ask questions in plain language ("which Midwest hubs are most exposed to winter
disruption?", "compare Miami and Houston on hurricane and flood", "why is Dallas high?") and need an answer they
can defend: a number, how it was computed, and how sure we are.

## Solution

A conversational agent over a **deterministic disruption KPI**:

- **KPI: expected disruption days per year, per hub and per hazard.** Daily weather history (2016–2025) is
  thresholded with operational limits (snowfall, wind gust, heavy precipitation, extreme heat, extreme cold). Each
  hazard yields disruption days per year with a year-to-year uncertainty band (min/max, stdev) and a 5-year trend.
  The overall score is a weighted sum with weights in a versioned YAML, so a ranking is reproducible and auditable.
- **The LLM never produces a number.** It interprets the question, calls typed tools and explains the result.
  Every figure comes from code over the data; the LLM-to-code contract is an enforced Pydantic schema (`AnswerOut`:
  status, answer, sources, limitations).
- **Regions are data, not guesses.** Hubs carry region and county FIPS in `config/hubs.yaml`; "Midwest hubs" is a
  filter.
- **Now vs history.** Open-Meteo archive gives the climatology; NOAA NWS alerts and 7-day forecast answer "why is X
  high right now" and power the score-change alert.
- **Production-shaped platform:** model chain with cross-vendor fallback, typed guardrail, spend budget, rate
  limits, eval runner with a pass/fail gate, offline tests, CI, Render deploy.
- **Spec-driven.** One Agent OS spec per version; every acceptance criterion maps to a named test.

## Scope & Assumptions

**In scope:** 12–15 named US hubs; five weather hazards from daily history; hurricane/flood exposure approximated by
heavy-rain and gust days (FEMA NRI county data as a secondary signal only if time allows); ranking, comparison,
single-hub stats and "why" explanations; conversational follow-ups within a session; a small eval set; a chat page
over a JSON API; Render deployment.

**Out of scope:** real operational outage records (none available, so thresholds are stated assumptions); sub-daily
weather; hubs outside the registry; multi-user auth; persistent sessions; streaming.

**Assumptions and uncertainty:** thresholds are plausible operational limits, not calibrated to the company's
outages; Open-Meteo reanalysis is point data at the hub coordinate, not the facility footprint; year-to-year
variance is the honest uncertainty we can show; a 10-year window is short for rare hazards (hurricanes), and the
answer must say so. Every answer carries `limitations`.
