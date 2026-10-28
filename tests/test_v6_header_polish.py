"""Acceptance criteria of agent-os/specs/2026-10-28-v6-header-polish."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT

TAGLINE = "Weather disruption risk across the US hub network"


def header_of(page: str) -> str:
    return re.search(r"<header>(.*?)</header>", page, re.DOTALL).group(1)


def test_criterion_1_header_shows_name_and_tagline(service, budget):
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    page = TestClient(app).get("/").text
    header = header_of(page)
    assert "HubRisk agent" in header and TAGLINE in header
    assert "models" not in header and "guard" not in header and "version" not in header
    status_line = next(line for line in page.splitlines() if "getElementById('status').textContent" in line)
    assert "h.models" not in status_line and "h.version" not in status_line and "h.guard" not in status_line


def test_criterion_2_unhealthy_state_is_visible_without_models():
    page = (ROOT / "src" / "app" / "api" / "static" / "index.html").read_text(encoding="utf-8")
    status_line = next(line for line in page.splitlines() if "getElementById('status').textContent" in line)
    assert "h.status === 'ok'" in status_line and "'status: ' + h.status" in status_line


def test_criterion_3_docs_and_roadmap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "HubRisk agent" in readme and TAGLINE in readme
    roadmap = (ROOT / "agent-os" / "product" / "roadmap.md").read_text(encoding="utf-8")
    assert "**v6 header polish**" in roadmap and "**v7 alerts**" in roadmap and "**v8 voice**" in roadmap
