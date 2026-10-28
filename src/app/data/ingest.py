"""One-off ingest: every hub's daily history from Open-Meteo into the committed snapshot. Run locally, commit the result."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from pathlib import Path

from app.data.hubs import HubRegistry
from app.data.openmeteo import DailyRow, OpenMeteoClient, SourceError
from app.data.snapshot import Manifest, write_snapshot

log = logging.getLogger(__name__)
SOURCE = "open-meteo archive (ERA5 reanalysis), daily, https://archive-api.open-meteo.com/v1/archive"


async def ingest(
    registry: HubRegistry, client: OpenMeteoClient, start: date, end: date, out_dir: Path, *,
    hub_ids: list[str] | None = None, pause_s: float = 2.0, attempts: int = 5, backoff_s: float = 30.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Manifest:
    hubs = [registry.by_id(h) for h in hub_ids] if hub_ids else registry.all
    rows: list[DailyRow] = []
    for i, hub in enumerate(hubs):
        if i and pause_s:
            await sleep(pause_s)
        got = await _fetch_with_retry(client, hub, start, end, attempts, backoff_s, sleep)
        log.info("ingest %s: %d days", hub.id, len(got))
        rows.extend(got)
    manifest = Manifest(
        source=SOURCE, fetched_at=datetime.now(UTC), start=start, end=end, hubs_version=registry.version,
        hubs=len(hubs), rows=len(rows),
    )
    write_snapshot(rows, manifest, out_dir)
    return manifest


async def _fetch_with_retry(
    client: OpenMeteoClient, hub, start: date, end: date, attempts: int, backoff_s: float,
    sleep: Callable[[float], Awaitable[None]],
) -> list[DailyRow]:
    """The archive rate-limits bursts (429) beyond the transport's short retries; wait longer between tries."""
    for attempt in range(1, attempts + 1):
        try:
            return await client.fetch_daily(hub, start, end)
        except SourceError as e:
            if attempt == attempts:
                raise
            wait = backoff_s * attempt
            log.warning("ingest %s attempt %d failed (%s); retrying in %.0fs", hub.id, attempt, e, wait)
            await sleep(wait)
    raise AssertionError("unreachable")
