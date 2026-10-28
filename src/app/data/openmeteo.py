"""Open-Meteo archive client: daily history per hub, no key. Units are checked against the response, not assumed."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx2
from pydantic import BaseModel

from app.data.hubs import Hub

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "snowfall_sum", "wind_gusts_10m_max")
EXPECTED_UNITS = {
    "temperature_2m_max": "°C", "temperature_2m_min": "°C", "precipitation_sum": "mm", "snowfall_sum": "cm",
    "wind_gusts_10m_max": "km/h",
}
COLUMNS = {
    "temperature_2m_max": "tmax_c", "temperature_2m_min": "tmin_c", "precipitation_sum": "precip_mm",
    "snowfall_sum": "snow_cm", "wind_gusts_10m_max": "gust_kmh",
}


class SourceError(RuntimeError):
    """An external data source answered with something we must not silently use."""


class DailyRow(BaseModel):
    hub_id: str
    date: date
    tmax_c: float | None = None
    tmin_c: float | None = None
    precip_mm: float | None = None
    snow_cm: float | None = None
    gust_kmh: float | None = None


def parse_daily(hub_id: str, payload: dict[str, Any]) -> list[DailyRow]:
    units = payload.get("daily_units") or {}
    wrong = {k: units.get(k) for k, v in EXPECTED_UNITS.items() if units.get(k) != v}
    if wrong:
        raise SourceError(f"open-meteo {hub_id}: unexpected units {wrong}, expected {EXPECTED_UNITS}")
    daily = payload.get("daily") or {}
    days = daily.get("time") or []
    return [
        DailyRow(hub_id=hub_id, date=date.fromisoformat(day), **{COLUMNS[v]: daily[v][i] for v in DAILY_VARS})
        for i, day in enumerate(days)
    ]


class OpenMeteoClient:
    def __init__(self, http: httpx2.AsyncClient, base_url: str = ARCHIVE_URL) -> None:
        self.http, self.base_url = http, base_url

    async def fetch_daily(self, hub: Hub, start: date, end: date) -> list[DailyRow]:
        params = {
            "latitude": hub.lat, "longitude": hub.lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
            "daily": ",".join(DAILY_VARS), "timezone": hub.timezone,
        }
        try:
            r = await self.http.get(self.base_url, params=params)
            r.raise_for_status()
            payload = r.json()
        except (httpx2.HTTPError, ValueError) as e:
            raise SourceError(f"open-meteo {hub.id}: {e}") from e
        return parse_daily(hub.id, payload)
