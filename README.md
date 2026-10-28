# HubRisk — Weather Risk Intelligence Agent

A conversational agent that helps a US logistics company decide which regional distribution hubs are most exposed
to weather disruption. Every number comes from deterministic code over public weather data; the LLM interprets the
question, calls typed tools and explains the result inside an enforced JSON schema.

Design: [docs/DESIGN.md](docs/DESIGN.md). Product docs and specs: [agent-os/](agent-os/). The full AI session
used to build this is exported under `docs/ai-session/`.

## Run it

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run agent chat --test "What can you help me with?"   # offline, no key, no spend
uv run agent serve --test                                # http://localhost:8000
```

With real models, copy `.env.example` to `.env` and set at least one vendor key (`ANTHROPIC_API_KEY` recommended;
`OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `TYPESAFE_API_KEY` optional). A model whose key is
missing is skipped at startup. Then:

```bash
uv run agent serve                       # chat page at /, API at /api/chat, docs at /api/docs
uv run agent eval --repeat 3 --tag latest
uv run agent eval --down anthropic --tag anthropic-outage   # proves cross-vendor fallback
```

Tests and lint (offline, no keys):

```bash
uv run ruff check src tests
uv run pytest -q
```

## Data

- **Hubs:** `config/hubs.yaml`, 15 distribution hubs with coordinates, US Census region, county FIPS and timezone.
- **History:** `data/snapshots/daily.parquet`, daily max/min temperature, precipitation, snowfall and wind-gust
  maximum per hub for 2016-01-01..2025-12-31 from the Open-Meteo archive (ERA5 reanalysis, point data at the hub
  coordinate). Committed to the repo, so a deploy needs no network and no key. `manifest.json` records when it
  was fetched. Refresh with:

```bash
uv run agent ingest
```

- **Live:** NOAA NWS active alerts and 7-day forecast per hub, fetched on demand with a 10-minute cache. NWS
  requires an identifying `User-Agent`; set `NWS_USER_AGENT` to include a contact.

## Chat page

The header reads "HubRisk agent" with the tagline "Weather disruption risk across the US hub network";
version, model chain and guard live on `/health` and in each answer's details toggle.
A greeting or "what can you do?" gets an instant intro with the four example questions, without a model call.
Answers lead with the ranking or the number and stay short (a schema cap and an eval check enforce it). Every
answer shows its limitations; sources, model, tools, cost and latency sit behind a `details` toggle. "Why"
answers lead with the score and the main driver, list only the material hazards, and offer the full breakdown.
Voice (bonus): the microphone button transcribes a question with the browser's Web Speech API (Chrome and Edge;
hidden where unsupported) and sends it; a spoken question gets a spoken answer, and the speaker toggle reads
every answer aloud. Only the answer is spoken, never sources or limitations.

## API

- `GET /health` — version, model chain, guard, and `data` (hubs, date range, rows) when the snapshot is loaded.
- `POST /api/chat` `{"message": "...", "session_id": "optional"}` → the answer plus `status`, `sources`,
  `limitations`, `served_by`, `failed_attempts`, `tools_used`, cost and latency.
- `DELETE /api/sessions/{id}` — forget a conversation.
- `GET /api/stats` — budget cap, month-to-date spend and recent calls (Bearer `ADMIN_TOKEN`).

## Alerts (bonus)

A deterministic **live risk level** per hub (none / watch / warning) comes from NWS active alerts (severity
Severe or Extreme → warning, otherwise watch, hazard matched by event name) plus the 7-day forecast (≥ 70%
chance of snow, storms or heavy rain adds a watch). It is reported beside the historical score, never blended
into it. A scheduled check stores the level and posts a JSON webhook to `ALERT_WEBHOOK_URL` when a hub's level
changes:

```bash
uv run agent alerts-check                       # one pass, prints every hub's level
curl -X POST https://hubrisk.onrender.com/api/alerts/run -H "Authorization: Bearer $ADMIN_TOKEN"   # webhook-triggered
curl https://hubrisk.onrender.com/api/alerts     # current levels
```

Two triggers: the service runs the check every `ALERT_INTERVAL_MIN` minutes (30 on Render), and
`.github/workflows/alerts.yml` calls the run endpoint every 30 minutes when the `ALERTS_URL` and `ALERTS_TOKEN`
secrets are set (this also wakes the free-tier instance). State lives in the ephemeral SQLite file: after a
restart the first check records a baseline and alerts nothing.

## Spend limits (both are required)

1. In code: `BUDGET_USD` monthly cap enforced by the SQLite ledger before every paid call, plus a per-turn cost
   limit and request limit, 20 requests per IP per hour and 200 per day.
2. In each provider console: the same monthly cap (Anthropic Console → Limits; OpenAI → Billing limits; Google
   Cloud budget). The code refuses before a call; the provider refuses regardless of the code.

## Assumptions, uncertainty and scoping

**The KPI.** Expected disruption days per year, per hub and per hazard. A disruption day is a day whose daily
weather crosses an operational threshold. Rules and weights live in `config/scoring.yaml` (version 1.0.0):

| hazard | rule | weight | rationale |
|---|---|---|---|
| snow | `snow_cm >= 5` | 1 | heavy snowfall closes yards and roads |
| wind | `gust_kmh >= 70` | 1 | damaging gusts stop loading and flights |
| rain | `precip_mm >= 25` | 0.8 | heavy rain; the flood proxy |
| cold | `tmin_c <= -15` | 0.7 | extreme cold: equipment and staffing |
| heat | `tmax_c >= 38` | 0.3 | extreme heat slows work but rarely closes a hub (Phoenix would otherwise dominate) |

Overall score = Σ weight × expected days. Groups: **winter** = snow + cold; **hurricane_flood** = rain + wind, a
proxy until a hurricane or flood dataset is wired in (every answer says so); **heat** = heat.

**Assumptions.** Thresholds were chosen after measuring the 2016–2025 snapshot so each hazard separates hubs;
they are plausible operational limits, not calibrated to the company's outage records (none available). Weather
is ERA5 reanalysis at the hub coordinate, not the facility footprint. Only complete years (≥ 360 days) count.

**Uncertainty.** Every per-hazard figure ships with per-year counts, min, max and standard deviation across
years, and a trend (mean of the last half of years minus the first half). Ten years is short for rare hazards;
the band is the honest uncertainty we can show. "Right now" risk comes from NWS alerts and forecast and is
reported beside the historical score, never blended into it.

**Scoping.** 15 hubs, five hazards from daily data, no sub-daily events, no multi-user auth, in-memory sessions.
The LLM never produces a number: every figure comes from a tool, and answers carry `sources` and `limitations`.

## Evals

`evals/cases.yaml` holds 20 live cases in five categories (in_scope with the four sample questions, off_topic,
injection, false_positive, followup). `evals/smoke.yaml` is the offline set CI runs. Reports are committed under
`evals/results/`; a prompt change bumps `PROMPT_VERSION` and ships with a fresh baseline.

| report | what | result |
|---|---|---|
| `v3-baseline` | all 18 cases, 2 repeats, Sonnet 5.5 with Jev guard | 18/18 passed, exit 0, 0.77 USD |
| `v5-baseline` | 20 cases (v3 set + two greetings), brevity check on, prompt 1.2.0 | 20/20 passed, exit 0, 0.37 USD |
| `v6-baseline` | 20 cases, "why" format rules + word caps, prompt 1.3.0, config 0.2.2 | 20/20 passed, exit 0, 0.61 USD |
| `v3-anthropic-down` | same cases with `--down anthropic` (outage simulation) | 18/18 passed, exit 0, 0.04 USD; OpenAI answered 429 and every run fell over to Gemini 2.5 Flash |

Sample answers from the baseline (abridged), every number from a tool:

- *Which hubs in the Midwest are most exposed to winter disruption?* Minneapolis 42.3 expected days per year
  (band 24–70, trend +2.2; cold 37.1, snow 5.2), then Chicago 13.4, Detroit 9.6, Kansas City 6.8, Columbus 6.2.
- *Compare Miami and Houston in terms of hurricane and flood exposure.* A proxy from heavy-rain and gust days:
  Houston 20.3 vs Miami 10.6; Houston leads on heavy rain (21.7 vs 9.4 days), Miami slightly on gusts (3.1 vs 2.1).
- *What percentage of days in Denver last year had snowfall?* 12.1% of 2025 (44 of 365 days); only 1 day reached
  the 5 cm threshold. Follow-up "and the year before?" gives 13.7% (50 of 366).
- *Why is the Dallas hub's weather disruption risk high?* 21.68 weighted days per year, 4th of 15; heavy rain
  contributes 12.72, wind 4.9, heat 3.72; band 6.6–31.9, trend +7.8.
- *How exposed is our Boston hub?* Boston is not a hub; the agent lists the 15 hubs and offers Newark as the
  nearest reference instead of inventing a score.

## Deployment

Live at **https://hubrisk.onrender.com** (Render, free tier, Frankfurt). Deployed from `render.yaml` as a Blueprint; every push to
main that passes CI auto-deploys.

Verification record (re-run any time with `uv run agent verify https://hubrisk.onrender.com`; it checks
`/health` and asks "Which hub has the most heavy-snow days per year?" so the model path is exercised):

```
Verified 2026-10-28 at https://hubrisk.onrender.com
- /health: status ok, version 0.1.0, models anthropic:claude-sonnet-5-5 -> anthropic:claude-haiku-5-5 -> openai:gpt-5.2 -> google-gla:gemini-2.5-flash, guard typesafe:jev-latest -> anthropic:claude-haiku-5-5, data 15 hubs 2016-01-01..2025-12-31
- /api/chat: status answered, served by claude-sonnet-5-5, tools ['rank_hubs', 'about'], 25960 ms, 0.1080 USD
```

- `GET /health` lists the model chain, the guard and the loaded snapshot; `POST /api/chat` answers one turn.
- Free tier: the service sleeps after 15 min idle, so the first request takes a 30–60 s cold start. The disk is
  ephemeral: the spend ledger (`DB_PATH=/tmp/agent.db`) resets on redeploy, which is why the provider-side limits
  below are required.
- Spend limits in place: `BUDGET_USD=5` enforced in code (ledger + per-turn cap), and monthly caps set in the
  Anthropic Console (Limits), Google Cloud (budget) and OpenAI (Billing limits) on 2026-10-28.
- Secrets live only in Render's environment (`sync: false` in the Blueprint); nothing is in the repo.
- To redeploy: push to main. To roll back: redeploy a previous commit from the Render dashboard.
