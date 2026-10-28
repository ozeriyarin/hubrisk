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

## API

- `GET /health` — version, model chain, guard, and `data` (hubs, date range, rows) when the snapshot is loaded.
- `POST /api/chat` `{"message": "...", "session_id": "optional"}` → the answer plus `status`, `sources`,
  `limitations`, `served_by`, `failed_attempts`, `tools_used`, cost and latency.
- `DELETE /api/sessions/{id}` — forget a conversation.
- `GET /api/stats` — budget cap, month-to-date spend and recent calls (Bearer `ADMIN_TOKEN`).

## Spend limits (both are required)

1. In code: `BUDGET_USD` monthly cap enforced by the SQLite ledger before every paid call, plus a per-turn cost
   limit and request limit, 20 requests per IP per hour and 200 per day.
2. In each provider console: the same monthly cap (Anthropic Console → Limits; OpenAI → Billing limits; Google
   Cloud budget). The code refuses before a call; the provider refuses regardless of the code.

## Assumptions, uncertainty and scoping

Filled in by the hubs, scoring and agent specs (v1–v3). See `agent-os/product/mission.md` for the current
scope statement.

## Deployment

Render Blueprint in `render.yaml`. Filled in with the live URL and verification date by the deploy spec (v4).
