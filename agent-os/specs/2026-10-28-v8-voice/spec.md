# Spec: v8 voice

## Goal

The brief's second bonus: voice in the chat. A microphone button transcribes a question with the browser's Web
Speech API and sends it; answers are read aloud when the question was spoken or a speaker toggle is on. No
dependency, no backend, model or prompt change.

## Scope

**In:** mic button (SpeechRecognition, feature-detected, hidden when unsupported), speaker toggle
(speechSynthesis, persisted best-effort in localStorage), answer-only speech, README and roadmap. **Out:**
server-side speech, new tools, any operator UI.

## Acceptance criteria

1. The page has a microphone button that uses the browser's SpeechRecognition (prefixed or not) with feature detection and is hidden when unsupported; the recognized transcript fills the input and submits the form.
2. The page has a speaker toggle persisted in `localStorage` (best effort), and reads the answer text aloud with `speechSynthesis` when the question was spoken or the toggle is on, cancelling any ongoing speech when a new question is sent; meta, sources and limitations are never spoken.
3. The page loads no external script and contains no slash-command handling; the existing header, favicon, intro and details toggle are unchanged.
4. README's chat page section documents voice (supported browsers, what is spoken) and the roadmap marks v8 shipped.

## Design

`window.SpeechRecognition || window.webkitSpeechRecognition`, `lang = 'en-US'`, one utterance, no interim
results; on result the transcript goes into the input and the form is submitted with `requestSubmit()`; the mic
shows a listening state (`aria-pressed`, class). `speechSynthesis` speaks `answer` only, after a `cancel()`,
when `spoken` (the question came by voice) or the toggle is on; the toggle state is stored under
`hubrisk.readAloud`, wrapped in try/catch. Both buttons carry `aria-label` and `title`.

## Tasks

1. Save spec documentation.
2. Page changes, `tests/test_v8_voice.py`, README, roadmap; ruff; pytest; commit; push.
3. Confirm the live page after the auto-deploy; final transcript re-export and repackage; final commit and push.
