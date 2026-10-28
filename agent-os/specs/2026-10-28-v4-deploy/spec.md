# Spec: v4 deploy

## Goal

Ship the agent: Render live from the Blueprint, verified from the public URL with a repeatable command, README and
DESIGN deployment sections with the free-tier facts and both spend limits, and the mandatory deliverable: the full
AI session transcript committed under `docs/ai-session/`.

## Scope

**In:** `agent verify URL`; `Budget` parent-directory creation; `render.yaml` `NWS_USER_AGENT`; README
"Deployment"; DESIGN "Deployment"; `docs/ai-session/` with an index; roadmap closeout.

**Out:** runtime changes, prompts, models (no eval report needed); alerts and voice (v5, v6).

## Acceptance criteria

1. `render.yaml` builds with `uv sync --frozen --no-dev`, starts `agent serve --port $PORT`, probes `/health`, lists every vendor key as `sync: false`, generates `ADMIN_TOKEN`, sets `BUDGET_USD`, `DB_PATH` and `NWS_USER_AGENT`, and pins a Python 3.12 version.
2. `agent serve` binds the port from `$PORT` when no `--port` is given, and `Budget` creates a missing parent directory for `DB_PATH`.
3. `agent verify URL` calls `GET /health` and `POST /api/chat`, passes when health is `ok` with 15 hubs and a non-test model and the chat is `answered`, prints the date, the model that served and the latency, and exits 1 with a reason otherwise (offline test with `MockTransport`).
4. `GET /health` on the live service reports `data.hubs == 15` and a non-test model chain (verified live, recorded in the README; the offline test asserts the README record exists with a URL and an ISO date).
5. README "Deployment" names the live URL, the verification date and command output, the free-tier facts, and both spend limits with where each is set; the offline test checks these strings are present.
6. `docs/DESIGN.md` has a Deployment section covering build, start, env vars, health probe, ephemeral disk and what production would change.
7. `docs/ai-session/` contains the exported conversation transcript (at least one transcript file larger than 100 KB) and an index `README.md` that explains provenance and the single redaction.
8. CI workflow runs ruff, pytest and the offline eval smoke on push (unchanged), and the roadmap marks v4 shipped.

## Design

- **Deploy from the Blueprint, no runtime change.** The committed Parquet means the service needs no network or
  key at startup; `/health` proves the snapshot loaded (`data.hubs == 15`). Render auto-deploys on push to main.
- **`agent verify URL`** (`app/cli.py`): `GET /health` then `POST /api/chat` with "What can you help me with?"
  through `retrying_http_client` (5xx retries cover a cold start), pure `check_health(payload)` and
  `check_chat(payload)` helpers, a Markdown record with the date for the README, exit 0/1.
- **`Budget`** creates `DB_PATH`'s parent directory, so any path Render gives it works.
- **`render.yaml`** gains `NWS_USER_AGENT` (public repo URL as contact, not a secret).
- **README "Deployment"**: live URL, verification record, free-tier facts (15 min idle sleep, 30–60 s cold
  start, ephemeral disk so the ledger resets on redeploy), both spend limits and where they are set, redeploy =
  push to main.
- **DESIGN "Deployment"**: build/start, env, probe, why free tier suffices for a demo, what production changes.
- **Transcript**: the desktop app's Export of this session (zip in Downloads) unpacked into `docs/ai-session/`
  with an index `README.md`; one redaction (a third-party reference repository named in the kickoff handoff),
  noted in the index. Re-exported as the last step of the final version shipped.

## Tasks

1. Save spec documentation.
2. `agent verify`, `Budget` parent dir, `render.yaml`, DESIGN section, criterion tests 1–3, 6, 8; commit; push.
3. Owner creates the Render Blueprint and sets secrets and provider-side limits; sends the URL.
4. `agent verify <url>` live; README deployment section; criterion tests 4–5.
5. Transcript export into `docs/ai-session/`; criterion test 7.
6. Roadmap closeout; ruff; pytest; commit; push; re-verify after the auto-deploy.
