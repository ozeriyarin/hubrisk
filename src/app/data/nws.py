"""NOAA NWS client: active alerts and the 7-day forecast per hub. Keyless, needs a User-Agent, cached per hub.

A failed call degrades to `available=False` with a reason; the agent reports it in `limitations` instead of crashing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx2
from pydantic import BaseModel

from app.data.hubs import Hub

log = logging.getLogger(__name__)
NWS_URL = "https://api.weather.gov"


class Alert(BaseModel):
    event: str
    severity: str | None = None
    urgency: str | None = None
    headline: str | None = None
    onset: datetime | None = None
    ends: datetime | None = None
    area: str | None = None


class ForecastPeriod(BaseModel):
    name: str
    start: datetime
    end: datetime
    is_daytime: bool = True
    temperature: int | None = None
    temperature_unit: str | None = None
    wind_speed: str | None = None
    wind_direction: str | None = None
    precipitation_chance: int | None = None
    short_forecast: str = ""


class Live[T](BaseModel):
    available: bool = True
    items: list[T] = []
    fetched_at: datetime | None = None
    reason: str | None = None


class NWSClient:
    def __init__(
        self, http: httpx2.AsyncClient, user_agent: str, *, base_url: str = NWS_URL, cache_ttl_s: float = 600.0,
        failure_ttl_s: float = 60.0, now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.http, self.user_agent, self.base_url = http, user_agent, base_url
        self.cache_ttl_s, self.failure_ttl_s, self._now = cache_ttl_s, failure_ttl_s, now
        self._cache: dict[tuple[str, str], tuple[float, Live[Any]]] = {}

    async def alerts(self, hub: Hub) -> Live[Alert]:
        return await self._cached("alerts", hub, self._fetch_alerts)

    async def forecast(self, hub: Hub) -> Live[ForecastPeriod]:
        return await self._cached("forecast", hub, self._fetch_forecast)

    async def _cached(self, kind: str, hub: Hub, fetch: Callable[[Hub], Awaitable[Live[Any]]]) -> Live[Any]:
        key = (kind, hub.id)
        if hit := self._cache.get(key):
            stored_at, live = hit
            ttl = self.cache_ttl_s if live.available else self.failure_ttl_s
            if self._now() - stored_at < ttl:
                return live
        try:
            live = await fetch(hub)
        except Exception as e:  # noqa: BLE001 - any failure of a live source degrades, never crashes a turn
            log.warning("nws %s for %s unavailable: %r", kind, hub.id, e)
            live = Live(available=False, reason=f"{type(e).__name__}: {e}"[:200])
        self._cache[key] = (self._now(), live)
        return live

    async def _get(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        headers = {"User-Agent": self.user_agent, "Accept": "application/geo+json"}
        r = await self.http.get(url, params=params, headers=headers)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _point(hub: Hub) -> str:
        return f"{hub.lat:.4f},{hub.lon:.4f}"

    async def _fetch_alerts(self, hub: Hub) -> Live[Alert]:
        data = await self._get(f"{self.base_url}/alerts/active", params={"point": self._point(hub)})
        items = []
        for feature in data.get("features") or []:
            p = feature.get("properties") or {}
            items.append(Alert(
                event=p.get("event") or "", severity=p.get("severity"), urgency=p.get("urgency"),
                headline=p.get("headline"), onset=p.get("onset"), ends=p.get("ends"), area=p.get("areaDesc"),
            ))
        return Live(items=items, fetched_at=datetime.now(UTC))

    async def _fetch_forecast(self, hub: Hub) -> Live[ForecastPeriod]:
        points = await self._get(f"{self.base_url}/points/{self._point(hub)}")
        data = await self._get(points["properties"]["forecast"])
        items = [
            ForecastPeriod(
                name=p["name"], start=p["startTime"], end=p["endTime"], is_daytime=p.get("isDaytime", True),
                temperature=p.get("temperature"), temperature_unit=p.get("temperatureUnit"),
                wind_speed=p.get("windSpeed"), wind_direction=p.get("windDirection"),
                precipitation_chance=(p.get("probabilityOfPrecipitation") or {}).get("value"),
                short_forecast=p.get("shortForecast") or "",
            )
            for p in data["properties"]["periods"]
        ]
        return Live(items=items, fetched_at=datetime.now(UTC))
