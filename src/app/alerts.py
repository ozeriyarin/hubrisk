"""Live risk alerts: a deterministic level per hub from NWS alerts and the forecast, stored, diffed on a schedule,
and posted as a webhook when it changes. Reported beside the historical KPI, never blended into it."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx2
from pydantic import BaseModel

from app.data.hubs import HubRegistry
from app.data.nws import Alert, ForecastPeriod, Live, NWSClient

log = logging.getLogger(__name__)

LEVEL_LABELS = {0: "none", 1: "watch", 2: "warning"}
SEVERITY_LEVEL = {"extreme": 2, "severe": 2, "moderate": 1, "minor": 1}
# Order matters: "Wind Chill Warning" is cold, "Winter Storm Warning" is snow.
HAZARD_EVENTS = (
    ("cold", re.compile(r"cold|freez|wind chill|frost", re.IGNORECASE)),
    ("snow", re.compile(r"snow|blizzard|winter|ice|sleet", re.IGNORECASE)),
    ("heat", re.compile(r"heat", re.IGNORECASE)),
    ("rain", re.compile(r"flood|hurricane|tropical|storm|rain", re.IGNORECASE)),
    ("wind", re.compile(r"wind|gale", re.IGNORECASE)),
)
FORECAST_WORDS = re.compile(r"snow|blizzard|thunderstorm|storm|heavy rain|ice|sleet", re.IGNORECASE)


class LiveRisk(BaseModel):
    hub_id: str
    level: int | None
    label: str
    drivers: list[str]
    checked_at: datetime
    reason: str | None = None


class Change(BaseModel):
    hub_id: str
    name: str
    previous: int | None
    current: int | None
    previous_label: str
    current_label: str
    drivers: list[str]
    checked_at: datetime


def hazard_for(event: str) -> str | None:
    for hazard, pattern in HAZARD_EVENTS:
        if pattern.search(event):
            return hazard
    return None


def assess(hub_id: str, alerts: Live[Alert], forecast: Live[ForecastPeriod], now: datetime | None = None) -> LiveRisk:
    """Level 0 none, 1 watch, 2 warning. Alerts set the level by severity; the forecast adds at most level 1."""
    checked = now or datetime.now(UTC)
    if not alerts.available and not forecast.available:
        reason = alerts.reason or forecast.reason or "live data unavailable"
        return LiveRisk(hub_id=hub_id, level=None, label="unavailable", drivers=[], checked_at=checked, reason=reason)
    level, drivers = 0, []
    if alerts.available:
        for a in alerts.items:
            hazard = hazard_for(a.event)
            if hazard is None:
                continue
            level = max(level, SEVERITY_LEVEL.get((a.severity or "").lower(), 1))
            drivers.append(f"{a.event} ({a.severity or 'unknown severity'}) -> {hazard}")
    if forecast.available:
        for p in forecast.items:
            if (p.precipitation_chance or 0) >= 70 and FORECAST_WORDS.search(p.short_forecast):
                level = max(level, 1)
                drivers.append(f"forecast {p.name}: {p.short_forecast} ({p.precipitation_chance}%)")
    reason = None if alerts.available and forecast.available else (alerts.reason or forecast.reason)
    return LiveRisk(hub_id=hub_id, level=level, label=LEVEL_LABELS[level], drivers=drivers, checked_at=checked, reason=reason)


class AlertStore:
    """Last known live risk per hub, in the same SQLite file as the spend ledger."""

    def __init__(self, db_path: Path | str) -> None:
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS live_risk (hub_id TEXT PRIMARY KEY, level INTEGER, label TEXT NOT NULL, "
            "drivers TEXT NOT NULL, checked_at TEXT NOT NULL, reason TEXT)"
        )

    def get(self, hub_id: str) -> LiveRisk | None:
        row = self._conn.execute("SELECT hub_id, level, label, drivers, checked_at, reason FROM live_risk WHERE hub_id = ?", (hub_id,)).fetchone()
        return self._row(row) if row else None

    def put(self, risk: LiveRisk) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO live_risk VALUES (?, ?, ?, ?, ?, ?)",
            (risk.hub_id, risk.level, risk.label, json.dumps(risk.drivers), risk.checked_at.isoformat(), risk.reason),
        )

    def all(self) -> list[LiveRisk]:
        rows = self._conn.execute("SELECT hub_id, level, label, drivers, checked_at, reason FROM live_risk ORDER BY hub_id").fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(row: tuple) -> LiveRisk:
        hub_id, level, label, drivers, checked_at, reason = row
        return LiveRisk(hub_id=hub_id, level=level, label=label, drivers=json.loads(drivers), checked_at=datetime.fromisoformat(checked_at), reason=reason)


class WebhookNotifier:
    """POSTs one JSON document per change. No URL: log only. Failure: log, never raise."""

    def __init__(self, url: str | None, http: httpx2.AsyncClient | None = None) -> None:
        self.url, self.http = url, http
        self.sent: list[Change] = []

    async def send(self, change: Change) -> bool:
        if not self.url:
            log.info("alert (no webhook configured): %s %s -> %s", change.hub_id, change.previous_label, change.current_label)
            return False
        try:
            http = self.http or httpx2.AsyncClient(timeout=20)
            r = await http.post(self.url, json=json.loads(change.model_dump_json()))
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001 - a dead webhook must not stop the check
            log.warning("alert webhook failed for %s: %r", change.hub_id, e)
            return False
        self.sent.append(change)
        return True


async def run_check(registry: HubRegistry, nws: NWSClient, store: AlertStore, notifier: WebhookNotifier | None = None) -> list[Change]:
    """Assess every hub, store, and report hubs whose level changed since the last stored check."""
    changes: list[Change] = []
    for hub in registry.all:
        risk = assess(hub.id, await nws.alerts(hub), await nws.forecast(hub))
        previous = store.get(hub.id)
        store.put(risk)
        if previous is None or previous.level is None or risk.level is None or previous.level == risk.level:
            continue
        change = Change(
            hub_id=hub.id, name=hub.name, previous=previous.level, current=risk.level, previous_label=previous.label,
            current_label=risk.label, drivers=risk.drivers, checked_at=risk.checked_at,
        )
        changes.append(change)
        log.info("live risk changed: %s %s -> %s", hub.id, change.previous_label, change.current_label)
        if notifier:
            await notifier.send(change)
    return changes


@dataclass
class AlertService:
    registry: HubRegistry
    nws: NWSClient
    store: AlertStore
    notifier: WebhookNotifier

    async def run(self) -> list[Change]:
        return await run_check(self.registry, self.nws, self.store, self.notifier)

    def current(self) -> list[LiveRisk]:
        return self.store.all()


class Scheduler:
    """Runs `job` every `interval_s` seconds in the event loop until stopped."""

    def __init__(self, job: Callable[[], Awaitable[object]], interval_s: float) -> None:
        self.job, self.interval_s, self.runs = job, interval_s, 0
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.job()
                self.runs += 1
            except Exception as e:  # noqa: BLE001 - one failed pass must not kill the schedule
                log.warning("scheduled check failed: %r", e)
            await asyncio.sleep(self.interval_s)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
