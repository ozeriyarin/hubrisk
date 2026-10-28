"""Read side of the snapshot: one in-process DuckDB connection with a `daily` view over the committed Parquet."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
from pydantic import BaseModel

from app.data.openmeteo import DailyRow
from app.data.snapshot import MANIFEST_FILE, SNAPSHOT_FILE, Manifest

COLS = "hub_id, date, tmax_c, tmin_c, precip_mm, snow_cm, gust_kmh"


class Coverage(BaseModel):
    hub_id: str
    start: date
    end: date
    rows: int


class DataSummary(BaseModel):
    hubs: int
    start: date
    end: date
    rows: int
    fetched_at: str


class Store:
    def __init__(self, snapshot_dir: Path) -> None:
        self.dir = snapshot_dir
        self.manifest = Manifest.model_validate_json((snapshot_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
        self._con = duckdb.connect()
        self._con.execute(f"CREATE VIEW daily AS SELECT * FROM read_parquet('{(snapshot_dir / SNAPSHOT_FILE).as_posix()}')")

    @classmethod
    def open_if_present(cls, snapshot_dir: Path) -> Store | None:
        if (snapshot_dir / SNAPSHOT_FILE).exists() and (snapshot_dir / MANIFEST_FILE).exists():
            return cls(snapshot_dir)
        return None

    def query(self, sql: str, params: list | None = None) -> list[tuple]:
        """Run read-only SQL against the `daily` view on a per-call cursor (connections are not thread-safe)."""
        return self._con.cursor().execute(sql, params or []).fetchall()

    def daily(self, hub_id: str, start: date | None = None, end: date | None = None) -> list[DailyRow]:
        where, params = ["hub_id = ?"], [hub_id]
        if start:
            where.append("date >= ?")
            params.append(start)
        if end:
            where.append("date <= ?")
            params.append(end)
        rows = self.query(f"SELECT {COLS} FROM daily WHERE {' AND '.join(where)} ORDER BY date", params)
        return [DailyRow(**dict(zip(COLS.split(", "), r, strict=True))) for r in rows]

    def coverage(self) -> list[Coverage]:
        rows = self.query("SELECT hub_id, min(date), max(date), count(*) FROM daily GROUP BY hub_id ORDER BY hub_id")
        return [Coverage(hub_id=h, start=s, end=e, rows=n) for h, s, e, n in rows]

    def years(self, hub_id: str, min_days: int = 360) -> list[int]:
        """Calendar years with enough rows to count as complete."""
        rows = self.query(
            "SELECT year(date) AS y, count(*) AS n FROM daily WHERE hub_id = ? GROUP BY y HAVING n >= ? ORDER BY y",
            [hub_id, min_days],
        )
        return [int(y) for y, _ in rows]

    def summary(self) -> DataSummary:
        hubs, start, end, rows = self.query("SELECT count(DISTINCT hub_id), min(date), max(date), count(*) FROM daily")[0]
        return DataSummary(hubs=hubs, start=start, end=end, rows=rows, fetched_at=self.manifest.fetched_at.isoformat())
