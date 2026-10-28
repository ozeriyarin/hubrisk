# References for v4 deploy

## In this repo

- `render.yaml` — Blueprint: python runtime, free plan, `pip install uv && uv sync --frozen --no-dev`,
  `uv run agent serve --port $PORT`, `healthCheckPath: /health`, vendor keys `sync: false`, `ADMIN_TOKEN`
  generated, `DB_PATH=/tmp/agent.db`.
- `.github/workflows/ci.yml` — ruff, pytest, `agent eval --test` (smoke set); green on every push so far.
- `src/app/api/app.py` — `/health` returns `status`, `version`, `models`, `guard`, `data` (hub count, date range).
- `src/app/cli.py` — Typer command style; `compose()`; `serve` reads `PORT` from `Settings`.
- `src/app/llm/models.py::retrying_http_client` — HTTP client with 429/5xx retries, used by `agent verify`.
- `agent-os/standards/deployment.md` — verification pasted into the README with the date.

## Render facts (free tier)

- Auto-deploys on push to the connected branch; Blueprint services are created from `render.yaml`.
- Sleeps after 15 minutes idle; first request after sleep takes 30–60 s.
- Disk is ephemeral: anything under `/tmp` resets on redeploy or restart.
- `PORT` is injected; the service must bind `0.0.0.0:$PORT`.

## Transcript export

- Desktop app session Export: a zip in the Downloads folder with the conversation transcript, subagent
  transcripts and session metadata.
