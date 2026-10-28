# References for v8 voice

- `src/app/api/static/index.html` — form `#f` with input `#q` and button `#send`; submit handler posts to
  `/api/chat` and renders `answer` then the meta block.
- Web Speech API: `SpeechRecognition` (Chrome/Edge expose `webkitSpeechRecognition`), `speechSynthesis` and
  `SpeechSynthesisUtterance` (all major browsers). Firefox has no recognition; the mic stays hidden there.
