# v4 deploy — Shaping Notes

## Scope

Render live, a repeatable `agent verify` command, README and DESIGN deployment sections, the committed session
transcript, roadmap closeout. No runtime, prompt or model changes.

## Decisions

- The Blueprint is created from the Render dashboard by the owner (needs the Render login); secrets are set
  there as `sync: false` env vars; the agent verifies from the public URL afterwards.
- `agent verify` is the verification record: one command, dated output pasted into the README, re-runnable
  before the interview.
- Free tier is enough for a demo; the README states the sleep/cold-start and ephemeral-ledger facts rather than
  hiding them. Provider-side spend limits are the backstop and are recorded with the date the owner set them.
- `Budget` creates the parent directory of `DB_PATH` so a Render path change cannot crash startup.
- The transcript is exported with the desktop app's own Export, unpacked as-is, with two documented
  redactions (reference repository name, owner email) and an API-key scan, and re-exported as the final step of the last version shipped so it is complete.

## Context

- **Visuals:** none.
- **References:** `render.yaml`, `.github/workflows/ci.yml`, `app/api/app.py::/health`, `app/cli.py`,
  `app/llm/models.py::retrying_http_client`, `agent-os/standards/deployment.md`.
- **Product alignment:** brief: "deploying it to a URL is preferred", "the full session with the AI agent …
  mandatory"; roadmap item 5.

## Standards Applied

- deployment — Blueprint, probe, secrets, free-tier facts in the README, verification pasted with the date.
- secrets-and-config — secrets only as env vars; `NWS_USER_AGENT` is a plain value.
- testing — offline tests for the verify command and the config; live checks recorded, not mocked.
- python-style — pure `check_health` / `check_chat` helpers.
