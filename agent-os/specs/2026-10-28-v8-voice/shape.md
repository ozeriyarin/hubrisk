# v8 voice — Shaping Notes

## Scope

Browser-only voice input and output in the chat page.

## Decisions

- Web Speech API only: no dependency, no key, no server round trip for audio; unsupported browsers see the
  text-only page unchanged because the mic button is hidden by feature detection.
- Voice in implies voice out: a spoken question gets a spoken answer; a toggle makes every answer spoken.
- Only the answer text is spoken; sources, limitations and the technical line stay visual.
- Speech is cancelled when a new question is sent so answers never overlap.
- No model or prompt change, so no new baseline; no live spend.

## Context

- **Visuals:** none. **References:** `src/app/api/static/index.html` (form, submit handler, meta rendering).
- **Product alignment:** brief: "chat interface (voice is a bonus)".

## Standards Applied

- testing — criterion tests over the page source.
- python-style — not applicable beyond the test file; the page stays a single file.
