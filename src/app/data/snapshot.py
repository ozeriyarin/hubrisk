"""Parquet snapshot of the daily history plus a manifest with provenance. DuckDB writes it; no pandas or pyarrow."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import duckdb
from pydantic import BaseModel

from app.data.openmeteo import DailyRow

SNAPSHOT_FILE = "daily.parquet"
MANIFEST_FILE = "manifest.json"
SCHEMA = "hub_id VARCHAR, date DATE, tmax_c DOUBLE, tmin_c DOUBLE, precip_mm DOUBLE, snow_cm DOUBLE, gust_kmh DOUBLE"


class Manifest(BaseModel):
    source: str
    fetched_at: datetime
    start: date
    end: date
    hubs_version: str
    hubs: int
    rows: int


def write_snapshot(rows: list[DailyRow], manifest: Manifest, out_dir: Path) -> None:
    """Write daily.parquet and manifest.json, replacing any previous snapshot atomically."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE daily ({SCHEMA})")
    if rows:
        con.executemany(
            "INSERT INTO daily VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(r.hub_id, r.date, r.tmax_c, r.tmin_c, r.precip_mm, r.snow_cm, r.gust_kmh) for r in rows],
        )
    tmp = out_dir / (SNAPSHOT_FILE + ".tmp")
    con.execute(f"COPY (SELECT * FROM daily ORDER BY hub_id, date) TO '{tmp.as_posix()}' (FORMAT PARQUET)")
    con.close()
    os.replace(tmp, out_dir / SNAPSHOT_FILE)
    (out_dir / MANIFEST_FILE).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
