"""Acceptance criteria of agent-os/specs/2026-10-28-v8-voice, over the single-file chat page."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT

PAGE = (ROOT / "src" / "app" / "api" / "static" / "index.html").read_text(encoding="utf-8")


def test_criterion_1_mic_button_with_feature_detection():
    assert re.search(r'<button id="mic"[^>]*aria-label="Ask by voice"[^>]*hidden>', PAGE)
    assert "window.SpeechRecognition || window.webkitSpeechRecognition" in PAGE
    assert "if (Recognition) {" in PAGE and "mic.hidden = false;" in PAGE
    assert "q.value = ev.results[0][0].transcript" in PAGE and "requestSubmit()" in PAGE
    assert "rec.lang = 'en-US'" in PAGE and "mic.classList.add('listening')" in PAGE


def test_criterion_2_speaker_toggle_and_answer_only_speech():
    assert re.search(r'<button id="speak"[^>]*aria-label="Read answers aloud"', PAGE)
    assert "localStorage.getItem('hubrisk.readAloud')" in PAGE and "localStorage.setItem('hubrisk.readAloud'" in PAGE
    assert PAGE.count("try { readAloud = localStorage") == 1  # best effort: wrapped in try/catch
    assert "sayAnswer(j.answer);" in PAGE and "sayAnswer(bits" not in PAGE and "sayAnswer(meta" not in PAGE
    assert "const wanted = spoken || readAloud" in PAGE and "new SpeechSynthesisUtterance(text)" in PAGE
    submit = PAGE[PAGE.index("addEventListener('submit'"):]
    assert "speechSynthesis.cancel()" in submit[: submit.index("fetch('/api/chat'")]


def test_criterion_3_no_external_script_and_prior_features_intact(service, budget):
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    page = TestClient(app).get("/").text
    assert "<script src=" not in page and "startsWith('/')" not in page and "slash" not in page.lower()
    assert "HubRisk agent" in page and 'rel="icon"' in page and "createElement('details')" in page
    assert "'Limitations: '" in page and "'Sources: '" in page and "limits and run details" in page


def test_criterion_4_docs_and_roadmap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Voice (bonus)" in readme and "Web Speech API" in readme and "Only the answer is spoken" in readme
    roadmap = (ROOT / "agent-os" / "product" / "roadmap.md").read_text(encoding="utf-8")
    assert "**v8 voice**" in roadmap and "~~v8 voice~~" in roadmap
