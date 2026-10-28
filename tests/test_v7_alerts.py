"""Acceptance criteria of agent-os/specs/2026-10-28-v7-alerts, all offline."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app import cli as cli_module
from app.agent import tools
from app.agent.tools import ToolContext
from app.alerts import (
    AlertService,
    AlertStore,
    Change,
    LiveRisk,
    Scheduler,
    WebhookNotifier,
    assess,
    run_check,
)
from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT, Settings
from app.data.hubs import HubRegistry
from app.data.nws import Alert, ForecastPeriod, Live, NWSClient

NOW = datetime(2026, 1, 10, 12, tzinfo=UTC)


def live_alerts(*events: tuple[str, str | None]) -> Live[Alert]:
    return Live(items=[Alert(event=e, severity=s) for e, s in events], fetched_at=NOW)


def live_forecast(*periods: tuple[str, int | None]) -> Live[ForecastPeriod]:
    return Live(items=[ForecastPeriod(name=f"p{i}", start=NOW, end=NOW, short_forecast=text, precipitation_chance=chance) for i, (text, chance) in enumerate(periods)], fetched_at=NOW)


@pytest.mark.parametrize("events, forecast, level, driver_hint", [
    ([("Winter Storm Warning", "Severe")], [], 2, "snow"),
    ([("Wind Chill Advisory", "Minor")], [], 1, "cold"),
    ([("High Wind Warning", "Extreme")], [], 2, "wind"),
    ([("Flood Watch", "Moderate")], [], 1, "rain"),
    ([("Excessive Heat Warning", "Severe")], [], 2, "heat"),
    ([("Air Quality Alert", "Severe")], [], 0, None),
    ([], [("Heavy Snow", 80)], 1, "forecast"),
    ([], [("Sunny", 90), ("Snow", 40)], 0, None),
    ([("Dense Fog Advisory", "Minor")], [("Thunderstorms Likely", 75)], 1, "forecast"),
])
def test_criterion_1_assess_levels(events, forecast, level, driver_hint):
    risk = assess("denver", live_alerts(*events), live_forecast(*forecast), now=NOW)
    assert risk.level == level and risk.label in ("none", "watch", "warning") and risk.checked_at == NOW
    if driver_hint:
        assert any(driver_hint in d for d in risk.drivers), risk.drivers
    else:
        assert risk.drivers == []


def test_criterion_1_assess_unavailable():
    down = Live[Alert](available=False, reason="HTTPStatusError: 503")
    risk = assess("denver", down, Live[ForecastPeriod](available=False, reason="x"), now=NOW)
    assert risk.level is None and risk.label == "unavailable" and "503" in risk.reason
    partial = assess("denver", down, live_forecast(("Snow", 90)), now=NOW)
    assert partial.level == 1 and partial.reason == "HTTPStatusError: 503"


def test_criterion_2_store_round_trip(tmp_path: Path):
    store = AlertStore(tmp_path / "alerts" / "state.db")
    assert store.get("denver") is None and store.all() == []
    risk = LiveRisk(hub_id="denver", level=2, label="warning", drivers=["Winter Storm Warning (Severe) -> snow"], checked_at=NOW)
    store.put(risk)
    assert store.get("denver") == risk and store.all() == [risk]
    store.put(risk.model_copy(update={"level": 0, "label": "none", "drivers": []}))
    assert store.get("denver").level == 0 and len(store.all()) == 1


class ScriptedNWS:
    """Stands in for NWSClient: a fixed alert list per hub id, forecast always empty."""

    def __init__(self, by_hub: dict[str, list[tuple[str, str]]]) -> None:
        self.by_hub = by_hub

    async def alerts(self, hub):
        return live_alerts(*self.by_hub.get(hub.id, []))

    async def forecast(self, hub):
        return live_forecast()


async def test_criterion_3_run_check_baseline_then_changes(tmp_path: Path):
    registry, store = HubRegistry.load(), AlertStore(tmp_path / "s.db")
    first = await run_check(registry, ScriptedNWS({"denver": [("Winter Storm Warning", "Severe")]}), store)
    assert first == [] and len(store.all()) == 15 and store.get("denver").level == 2 and store.get("miami").level == 0
    second = await run_check(registry, ScriptedNWS({"miami": [("Hurricane Warning", "Extreme")]}), store)
    assert {c.hub_id: (c.previous, c.current) for c in second} == {"denver": (2, 0), "miami": (0, 2)}
    assert second[0].name and second[0].current_label in ("none", "warning")
    third = await run_check(registry, ScriptedNWS({"miami": [("Hurricane Warning", "Extreme")]}), store)
    assert third == []
    forced = await run_check(registry, ScriptedNWS({"miami": [("Hurricane Warning", "Extreme")]}), store, force=True)
    assert len(forced) == 15 and {c.previous_label for c in forced} <= {"none", "warning"}
    fresh = await run_check(registry, ScriptedNWS({}), AlertStore(tmp_path / "fresh.db"), force=True)
    assert len(fresh) == 15 and all(c.previous is None and c.previous_label == "unknown" for c in fresh)


async def test_criterion_4_webhook_notifier():
    posted: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        posted.append(request)
        return httpx2.Response(200 if request.url.path == "/good" else 500)

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    change = Change(hub_id="denver", name="Denver", previous=0, current=2, previous_label="none", current_label="warning", drivers=["x"], checked_at=NOW)
    good = WebhookNotifier("https://h.test/good", http)
    assert await good.send(change) is True and good.sent == [change]
    import json

    body = json.loads(posted[0].content)
    assert body["hub_id"] == "denver" and body["previous"] == 0 and body["current"] == 2 and body["drivers"] == ["x"] and "checked_at" in body
    bad = WebhookNotifier("https://h.test/bad", http)
    assert await bad.send(change) is False and bad.sent == []
    none = WebhookNotifier(None, http)
    assert await none.send(change) is False and len(posted) == 2


def test_criterion_5_alerts_check_cli(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ledger.db"))
    result = CliRunner().invoke(cli_module.cli, ["alerts-check", "--test"])
    assert result.exit_code == 0, result.output
    assert result.output.count("unavailable") == 15 and "0 change(s)" in result.output


def nws_on(handler) -> NWSClient:
    return NWSClient(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), "ua")


def warning_everywhere(request: httpx2.Request) -> httpx2.Response:
    if request.url.path.startswith("/points/"):
        return httpx2.Response(200, json={"properties": {"forecast": "https://api.weather.gov/gridpoints/X/1,1/forecast"}})
    if request.url.path.endswith("/forecast"):
        return httpx2.Response(200, json={"properties": {"periods": []}})
    return httpx2.Response(200, json={"features": [{"properties": {"event": "Winter Storm Warning", "severity": "Severe"}}]})


def test_criterion_6_alert_endpoints(service, budget, tmp_path: Path):
    alerts = AlertService(HubRegistry.load(), nws_on(warning_everywhere), AlertStore(tmp_path / "a.db"), WebhookNotifier(None))
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g", admin_token="secret", alerts=alerts)
    c = TestClient(app)
    assert c.get("/api/alerts").json() == []
    assert c.post("/api/alerts/run").status_code == 401
    r = c.post("/api/alerts/run", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200 and r.json() == []  # baseline run
    current = c.get("/api/alerts").json()
    assert len(current) == 15 and all(row["label"] == "warning" for row in current)


async def test_criterion_7_scheduler_runs_and_stops():
    runs = []

    async def job():
        runs.append(1)

    s = Scheduler(job, interval_s=0.01)
    s.start()
    await asyncio.sleep(0.08)
    await s.stop()
    count = len(runs)
    assert count >= 3 and s.runs == count
    await asyncio.sleep(0.03)
    assert len(runs) == count
    web = FastAPI()
    alerts = AlertService(HubRegistry.load(), nws_on(warning_everywhere), AlertStore(":memory:"), WebhookNotifier(None))
    scheduler = cli_module.attach_scheduler(web, alerts, 60)
    assert isinstance(scheduler, Scheduler)
    with TestClient(web):  # startup runs the first check immediately through the lifespan hook
        for _ in range(50):
            if scheduler.runs:
                break
            await asyncio.sleep(0.02)
    assert scheduler.runs >= 1 and len(alerts.current()) == 15
    assert Settings(_env_file=None).alert_interval_min == 0


def test_criterion_8_workflow_and_render():
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "alerts.yml").read_text(encoding="utf-8"))
    assert wf[True]["schedule"][0]["cron"] == "*/30 * * * *"
    run = wf["jobs"]["check"]["steps"][0]["run"]
    assert "/api/alerts/run" in run and "skipping" in run and "ALERTS_TOKEN" in run
    env = {e["key"]: e for e in yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))["services"][0]["envVars"]}
    assert env["ALERT_INTERVAL_MIN"]["value"] == "30" and env["ALERT_WEBHOOK_URL"].get("sync") is False


async def test_criterion_9_current_conditions_has_live_risk():
    deps = ToolContext(product_name="t", hubs=HubRegistry.load(), nws=nws_on(warning_everywhere))
    cur = await tools._current(deps, "denver")
    assert cur.live_risk.level == 2 and cur.live_risk.label == "warning" and "Winter Storm Warning" in cur.live_risk.drivers[0]


def test_criterion_10_docs_and_roadmap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Alerts" in readme and "agent alerts-check" in readme and "/api/alerts/run" in readme and "ALERT_WEBHOOK_URL" in readme
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "## Alerts" in design and "never blended" in design
    roadmap = (ROOT / "agent-os" / "product" / "roadmap.md").read_text(encoding="utf-8")
    assert "**v7 alerts**" in roadmap and "~~v7 alerts~~" in roadmap
