"""Acceptance criteria of agent-os/specs/2026-10-28-v1-hubs-and-data, one test per criterion, all offline."""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

from app import cli as cli_module
from app.agent.core import Conversation
from app.api.app import create_app
from app.api.sessions import SessionStore
from app.config import ROOT
from app.data.hubs import Hub, HubRegistry
from app.data.ingest import ingest
from app.data.nws import NWSClient
from app.data.openmeteo import DailyRow, OpenMeteoClient, SourceError
from app.data.snapshot import MANIFEST_FILE, SNAPSHOT_FILE, Manifest, write_snapshot
from app.data.store import DataSummary, Store
from app.llm.models import retrying_http_client

FIXTURES = Path(__file__).parent / "fixtures"
DENVER = Hub(
    id="denver", name="Denver", state="CO", region="West", lat=39.7392, lon=-104.9903, county_fips="08031",
    timezone="America/Denver",
)


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def manifest(rows: list[DailyRow], hubs: int = 1, version: str = "1.0.0") -> Manifest:
    return Manifest(
        source="test", fetched_at=datetime.now(UTC), start=min(r.date for r in rows), end=max(r.date for r in rows),
        hubs_version=version, hubs=hubs, rows=len(rows),
    )


def synthetic(hub_id: str, start: date, days: int) -> list[DailyRow]:
    return [
        DailyRow(hub_id=hub_id, date=start + timedelta(days=i), tmax_c=10 + i % 7, tmin_c=-1.0, precip_mm=i % 3,
                 snow_cm=0.5 if i % 10 == 0 else 0.0, gust_kmh=30 + i % 20)
        for i in range(days)
    ]


def client_for(handler) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))


def test_criterion_1_hubs_yaml_validates():
    reg = HubRegistry.load()
    assert reg.version and len(reg.all) >= 12 and len({h.id for h in reg.all}) == len(reg.all)
    assert len(reg.in_region("Midwest")) >= 3
    base = DENVER.model_dump()
    for bad in ({"county_fips": "8031"}, {"region": "Mountain"}, {"timezone": "Mars/Olympus"}, {"lat": 95}):
        with pytest.raises(ValidationError):
            Hub(**{**base, **bad})


def test_criterion_2_registry_lookup_is_case_insensitive():
    reg = HubRegistry.load()
    assert reg.find("miami").id == "miami" and reg.find("Kansas City").id == "kansas-city"
    assert reg.find("KANSAS-CITY").id == "kansas-city" and reg.find("atlantis") is None
    assert {h.id for h in reg.in_region("midwest")} == {"chicago", "minneapolis", "detroit", "columbus", "kansas-city"}
    assert reg.regions() == ["Midwest", "Northeast", "South", "West"]


async def test_criterion_3_openmeteo_request_parse_and_unit_check():
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=fixture("openmeteo_sample.json"))

    rows = await OpenMeteoClient(client_for(handler)).fetch_daily(DENVER, date(2024, 1, 1), date(2024, 1, 4))
    params = seen[0].url.params
    assert params["timezone"] == "America/Denver" and params["start_date"] == "2024-01-01" and params["end_date"] == "2024-01-04"
    assert params["daily"].split(",") == [
        "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "snowfall_sum", "wind_gusts_10m_max",
    ]
    assert len(rows) == 4 and rows[3] == DailyRow(
        hub_id="denver", date=date(2024, 1, 4), tmax_c=1.5, tmin_c=-6.3, precip_mm=0.1, snow_cm=0.07, gust_kmh=16.2
    )
    wrong = fixture("openmeteo_sample.json")
    wrong["daily_units"]["wind_gusts_10m_max"] = "mp/h"
    with pytest.raises(SourceError, match="units"):
        await OpenMeteoClient(client_for(lambda r: httpx2.Response(200, json=wrong))).fetch_daily(DENVER, date(2024, 1, 1), date(2024, 1, 4))


async def test_criterion_4_openmeteo_nulls_kept_and_http_errors_typed():
    payload = fixture("openmeteo_sample.json")
    payload["daily"]["snowfall_sum"][1] = None
    rows = await OpenMeteoClient(client_for(lambda r: httpx2.Response(200, json=payload))).fetch_daily(DENVER, date(2024, 1, 1), date(2024, 1, 4))
    assert len(rows) == 4 and rows[1].snow_cm is None and rows[1].tmax_c == 6.9
    calls: list[int] = []

    def down(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(503, json={"error": True})

    http = retrying_http_client(attempts=2, timeout_s=5, max_wait_s=0, wrapped=httpx2.MockTransport(down))
    with pytest.raises(SourceError, match="open-meteo denver"):
        await OpenMeteoClient(http).fetch_daily(DENVER, date(2024, 1, 1), date(2024, 1, 4))
    assert len(calls) == 2


def test_criterion_5_snapshot_round_trip(tmp_path: Path):
    rows = synthetic("b", date(2020, 1, 1), 3) + synthetic("a", date(2020, 1, 1), 3)
    rows[0], rows[1] = rows[1], rows[0]
    m = manifest(rows, hubs=2)
    write_snapshot(rows, m, tmp_path)
    assert (tmp_path / SNAPSHOT_FILE).exists() and (tmp_path / MANIFEST_FILE).exists()
    store = Store(tmp_path)
    assert store.manifest == m
    assert store.daily("a") == sorted((r for r in rows if r.hub_id == "a"), key=lambda r: r.date)
    assert store.daily("b") == sorted((r for r in rows if r.hub_id == "b"), key=lambda r: r.date)


def test_criterion_6_store_queries(tmp_path: Path):
    rows = synthetic("a", date(2020, 1, 1), 366 + 100)
    write_snapshot(rows, manifest(rows), tmp_path)
    store = Store(tmp_path)
    window = store.daily("a", date(2020, 3, 1), date(2020, 3, 10))
    assert [r.date for r in window] == [date(2020, 3, 1) + timedelta(days=i) for i in range(10)]
    cov = store.coverage()
    assert cov[0].hub_id == "a" and cov[0].start == date(2020, 1, 1) and cov[0].end == date(2021, 4, 10) and cov[0].rows == 466
    assert store.years("a") == [2020]
    assert store.summary() == DataSummary(hubs=1, start=date(2020, 1, 1), end=date(2021, 4, 10), rows=466, fetched_at=store.manifest.fetched_at.isoformat())


class FakeOpenMeteo:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def fetch_daily(self, hub: Hub, start: date, end: date) -> list[DailyRow]:
        self.calls.append(hub.id)
        return synthetic(hub.id, start, (end - start).days + 1)


async def test_criterion_7_ingest_writes_one_snapshot_and_replaces(tmp_path: Path):
    reg, fake = HubRegistry.load(), FakeOpenMeteo()
    m = await ingest(reg, fake, date(2024, 1, 1), date(2024, 1, 10), tmp_path, hub_ids=["denver", "miami"], pause_s=0)
    assert fake.calls == ["denver", "miami"] and m.hubs == 2 and m.rows == 20 and m.hubs_version == reg.version
    assert {c.hub_id for c in Store(tmp_path).coverage()} == {"denver", "miami"}
    await ingest(reg, fake, date(2024, 1, 1), date(2024, 1, 10), tmp_path, hub_ids=["denver"], pause_s=0)
    assert [c.hub_id for c in Store(tmp_path).coverage()] == ["denver"]
    m = await ingest(reg, fake, date(2024, 1, 1), date(2024, 1, 2), tmp_path, pause_s=0)
    assert m.hubs == len(reg.all)
    assert CliRunner().invoke(cli_module.cli, ["ingest", "--help"]).exit_code == 0


def nws_handler(seen: list[httpx2.Request]):
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        path = request.url.path
        if path.startswith("/points/"):
            return httpx2.Response(200, json=fixture("nws_points.json"))
        if path.endswith("/forecast"):
            return httpx2.Response(200, json=fixture("nws_forecast.json"))
        if path == "/alerts/active":
            return httpx2.Response(200, json=fixture("nws_alerts.json"))
        return httpx2.Response(404, json={"title": "Not Found"})

    return handler


async def test_criterion_8_nws_forecast_alerts_and_user_agent():
    seen: list[httpx2.Request] = []
    nws = NWSClient(client_for(nws_handler(seen)), "hubrisk-test (test@example.com)")
    forecast = await nws.forecast(DENVER)
    assert forecast.available and len(forecast.items) == 3 and forecast.items[0].name == "Overnight"
    assert forecast.items[0].temperature_unit == "F" and forecast.items[0].precipitation_chance == 0
    assert [r.url.path for r in seen] == ["/points/39.7392,-104.9903", "/gridpoints/BOU/63,62/forecast"]
    alerts = await nws.alerts(DENVER)
    assert alerts.available and alerts.items[0].event == "Winter Storm Warning" and alerts.items[0].severity == "Severe"
    assert seen[-1].url.params["point"] == "39.7392,-104.9903"
    assert all(r.headers["user-agent"] == "hubrisk-test (test@example.com)" for r in seen)


async def test_criterion_9_nws_cache_and_degradation():
    seen: list[httpx2.Request] = []
    clock = [0.0]
    nws = NWSClient(client_for(nws_handler(seen)), "ua", cache_ttl_s=600, now=lambda: clock[0])
    await nws.alerts(DENVER)
    await nws.alerts(DENVER)
    assert len(seen) == 1
    clock[0] = 601.0
    await nws.alerts(DENVER)
    assert len(seen) == 2
    broken = NWSClient(client_for(lambda r: httpx2.Response(503, json={})), "ua")
    live = await broken.forecast(DENVER)
    assert live.available is False and live.items == [] and "503" in (live.reason or "")


async def test_criterion_10_compose_wires_data_and_survives_a_missing_snapshot(tmp_path: Path, monkeypatch, caplog):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ledger.db"))
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "missing"))
    caplog.set_level(logging.WARNING)
    app = cli_module.compose(model_mode="test")
    deps = app.service.deps
    assert deps.store is None and app.store is None and deps.nws is not None and deps.hubs.find("miami")
    assert any("snapshot" in r.getMessage() for r in caplog.records)
    assert (await app.service.ask(Conversation(max_turns=3), "What can you help me with?")).status == "answered"
    rows = synthetic("denver", date(2020, 1, 1), 5)
    write_snapshot(rows, manifest(rows), tmp_path / "present")
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "present"))
    assert cli_module.compose(model_mode="test").service.deps.store is not None


def test_criterion_11_health_reports_data_coverage(service, budget):
    summary = DataSummary(hubs=15, start=date(2016, 1, 1), end=date(2025, 12, 31), rows=54_800, fetched_at="2026-10-28T00:00:00+00:00")
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g", data=summary)
    body = TestClient(app).get("/health").json()
    assert body["data"]["hubs"] == 15 and body["data"]["end"] == "2025-12-31" and body["data"]["rows"] == 54_800
    app = create_app(service, SessionStore(max_turns=5, ttl_s=60), budget, model_names=["fake"], guard_name="g")
    assert TestClient(app).get("/health").json()["data"] is None


def test_criterion_12_committed_snapshot_covers_every_hub():
    store = Store(ROOT / "data" / "snapshots")
    reg = HubRegistry.load()
    cov = {c.hub_id: c for c in store.coverage()}
    assert set(cov) == {h.id for h in reg.all}
    for c in cov.values():
        assert c.start <= date(2016, 1, 1) and c.end >= date(2025, 12, 31) and c.rows >= 3600, c
    (total, distinct), = store.query("SELECT count(*), count(DISTINCT (hub_id, date)) FROM daily")
    assert total == distinct
    assert store.manifest.hubs_version == reg.version and store.manifest.hubs == len(reg.all)
