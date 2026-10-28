"""Acceptance criteria of agent-os/specs/2026-10-28-v2-disruption-kpi, one test per criterion, all offline."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx2
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from app import cli as cli_module
from app.agent import tools
from app.agent.tools import NotFound, ToolContext, Unavailable, build_toolset
from app.config import ROOT
from app.data.hubs import HubRegistry
from app.data.nws import NWSClient
from app.data.openmeteo import DailyRow
from app.data.snapshot import Manifest, write_snapshot
from app.data.store import Store
from app.scoring.config import Hazard, ScoringConfig, load_scoring_config
from app.scoring.engine import Engine, hazard_days, score_hazard, score_hub, year_stats

SNOW = Hazard(variable="snow_cm", op=">=", threshold=5, weight=1.0, label="snow")
COLD = Hazard(variable="tmin_c", op="<=", threshold=-15, weight=0.5, label="cold")
CFG = ScoringConfig(version="t", hazards={"snow": SNOW, "cold": COLD}, groups={"winter": ["snow", "cold"]})
THROUGH = date(2025, 12, 31)


def rows_for(hub_id: str, years: dict[int, int], snow_every: int = 1) -> list[DailyRow]:
    """One row per day; the first `n` days of each year cross the snow threshold, days 1..3 cross cold."""
    out = []
    for year, n in years.items():
        d = date(year, 1, 1)
        i = 0
        while d.year == year:
            out.append(DailyRow(hub_id=hub_id, date=d, tmax_c=20.0, tmin_c=-20.0 if i < 3 else 0.0,
                                precip_mm=1.0 if i % 2 else 0.0, snow_cm=6.0 if i < n else 0.0, gust_kmh=40.0))
            d += timedelta(days=1)
            i += 1
    return out


def snapshot(tmp_path: Path, rows: list[DailyRow], hubs: int) -> Store:
    m = Manifest(source="t", fetched_at=datetime.now(UTC), start=min(r.date for r in rows), end=THROUGH, hubs_version="1.0.0", hubs=hubs, rows=len(rows))
    write_snapshot(rows, m, tmp_path)
    return Store(tmp_path)


def deps_with(engine: Engine | None, nws: NWSClient | None = None) -> ToolContext:
    return ToolContext(product_name="t", hubs=HubRegistry.load(), store=engine.store if engine else None, nws=nws, engine=engine)


def test_criterion_1_scoring_yaml_validates():
    cfg = load_scoring_config()
    assert cfg.version and set(cfg.hazards) == {"snow", "wind", "rain", "cold", "heat"}
    assert cfg.groups["winter"] == ["snow", "cold"] and cfg.hazards_in("hurricane_flood") == ["rain", "wind"]
    assert cfg.hazards_in("overall") == list(cfg.hazards) and cfg.hazards_in("nope") is None
    with pytest.raises(ValidationError, match="unknown variable"):
        Hazard(variable="humidity", op=">=", threshold=1, weight=1, label="x")
    with pytest.raises(ValidationError, match="unknown hazards"):
        ScoringConfig(version="t", hazards={"snow": SNOW}, groups={"g": ["snow", "lava"]})


def test_criterion_2_hazard_days_counts_per_year_and_ignores_none():
    rows = rows_for("a", {2020: 4, 2021: 0, 2022: 7})
    rows[0] = rows[0].model_copy(update={"snow_cm": None})
    assert hazard_days(rows, SNOW) == {2020: 3, 2022: 7}
    assert hazard_days(rows, COLD) == {2020: 3, 2021: 3, 2022: 3}


def test_criterion_3_hazard_score_band_and_trend():
    years = {2016 + i: i for i in range(10)}
    hs = score_hazard("snow", SNOW, rows_for("a", years), list(years))
    assert hs.mean == 4.5 and hs.min == 0 and hs.max == 9 and hs.stdev == pytest.approx(3.03, abs=0.01)
    assert hs.trend == 5.0 and hs.per_year[2025] == 9 and hs.years == list(range(2016, 2026))
    partial = score_hazard("snow", SNOW, rows_for("a", {2020: 4, 2021: 9, 2022: 2}), [2020, 2021])
    assert partial.years == [2020, 2021] and partial.per_year == {2020: 4, 2021: 9} and partial.trend is None
    single = score_hazard("snow", SNOW, rows_for("a", {2020: 4}), [2020])
    assert single.stdev == 0.0 and single.min == single.max == 4


def test_criterion_4_overall_is_weighted_sum_and_deterministic():
    hub = HubRegistry.load().by_id("denver")
    rows = rows_for("denver", {2020: 4, 2021: 6, 2022: 8, 2023: 2})
    a = score_hub(hub, rows, [2020, 2021, 2022, 2023], CFG, THROUGH)
    b = score_hub(hub, rows, [2020, 2021, 2022, 2023], CFG, THROUGH)
    assert a == b
    assert a.overall == pytest.approx(1.0 * 5.0 + 0.5 * 3.0)
    assert a.contributions == [("snow", 5.0), ("cold", 1.5)] and a.scoring_version == "t" and a.data_through == THROUGH


def test_criterion_5_rank_orders_ties_and_filters_region(tmp_path: Path):
    years = [2020, 2021, 2022, 2023]
    rows = rows_for("chicago", dict.fromkeys(years, 5)) + rows_for("detroit", dict.fromkeys(years, 5)) + rows_for("miami", dict.fromkeys(years, 9))
    engine = Engine(snapshot(tmp_path, rows, 3), HubRegistry.load(), CFG)
    ranking = engine.rank("snow")
    assert [r.hub_id for r in ranking.rows] == ["miami", "chicago", "detroit"] and ranking.rows[0].rank == 1
    assert ranking.rows[0].score == 9.0 and ranking.rows[0].band == (9.0, 9.0)
    winter = engine.rank("winter", region="midwest")
    assert [r.hub_id for r in winter.rows] == ["chicago", "detroit"] and winter.region == "Midwest"
    assert winter.rows[0].score == 8.0 and winter.rows[0].by_hazard == {"snow": 5.0, "cold": 3.0}
    assert engine.rank("overall").rows[0].score == pytest.approx(9.0 + 1.5)
    assert len(engine.rank("overall", top=2).rows) == 2
    with pytest.raises(KeyError):
        engine.rank("lava")


def test_criterion_6_compare_reports_per_hazard(tmp_path: Path):
    years = [2020, 2021, 2022, 2023]
    rows = rows_for("chicago", dict.fromkeys(years, 5)) + rows_for("miami", {2020: 1, 2021: 3, 2022: 1, 2023: 3})
    engine = Engine(snapshot(tmp_path, rows, 2), HubRegistry.load(), CFG)
    cmp = engine.compare("chicago", "miami", "winter")
    snow = cmp.hazards[0]
    assert snow.hazard == "snow" and snow.a == 5.0 and snow.b == 2.0 and snow.difference == 3.0 and snow.higher == "chicago"
    assert snow.a_band == (5, 5) and snow.b_band == (1, 3)
    assert cmp.hazards[1].higher == "tie" and cmp.overall_a > cmp.overall_b


def test_criterion_7_year_stats_use_real_day_count():
    rows = rows_for("a", {2020: 10, 2021: 2})
    ys = year_stats("a", rows, 2020, CFG, THROUGH)
    assert ys.days_in_year == 366 and ys.days_with_data == 366
    assert ys.snow_days_any == 10 and ys.snow_days_pct == round(100 * 10 / 366, 1)
    assert ys.precip_days_any == 183 and ys.threshold_days == {"snow": 10, "cold": 3}
    assert ys.max_snow_cm == 6.0 and ys.min_tmin_c == -20.0 and ys.max_gust_kmh == 40.0
    assert year_stats("a", rows, 2021, CFG, THROUGH).days_in_year == 365


def test_criterion_8_tools_never_raise(tmp_path: Path):
    none = deps_with(None)
    assert isinstance(tools._rank(none), Unavailable) and isinstance(tools._hub_score(none, "denver"), Unavailable)
    rows = rows_for("denver", {2020: 1, 2021: 1, 2022: 1, 2023: 1})
    engine = Engine(snapshot(tmp_path, rows, 1), HubRegistry.load(), CFG)
    deps = deps_with(engine)
    nf = tools._hub_score(deps, "atlantis")
    assert isinstance(nf, NotFound) and nf.kind == "hub" and "denver" in nf.valid
    assert tools._rank(deps, scope="lava").kind == "scope" and tools._rank(deps, region="mars").kind == "region"
    assert tools._year_stats(deps, "denver", 1999).kind == "year" and tools._year_stats(deps, "denver", 1999).valid == ["2020", "2021", "2022", "2023"]
    assert isinstance(tools._compare(deps, "denver", "nowhere"), NotFound)
    score = tools._hub_score(deps, "Denver")
    assert score.scoring_version == "t" and score.data_through == THROUGH
    assert tools._rank(deps, top=0).rows and tools._year_stats(deps, "denver", 2021).year == 2021


def nws_handler(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    if path.startswith("/points/"):
        return httpx2.Response(200, json={"properties": {"forecast": "https://api.weather.gov/gridpoints/X/1,1/forecast"}})
    if path.endswith("/forecast"):
        return httpx2.Response(200, json={"properties": {"periods": [{"name": "Tonight", "startTime": "2026-01-01T18:00:00-07:00", "endTime": "2026-01-02T06:00:00-07:00", "shortForecast": "Snow"}]}})
    return httpx2.Response(200, json={"features": [{"properties": {"event": "Winter Storm Warning"}}]})


async def test_criterion_9_tools_registered_and_current_conditions(tmp_path: Path):
    names = set(build_toolset().tools)
    assert {"about", "list_hubs", "rank_hubs", "compare_hubs", "hub_score", "hub_year_stats", "current_conditions"} <= names
    nws = NWSClient(httpx2.AsyncClient(transport=httpx2.MockTransport(nws_handler)), "ua")
    deps = deps_with(None, nws)
    cur = await tools._current(deps, "Denver")
    assert cur.alerts.available and cur.alerts.items[0].event == "Winter Storm Warning"
    assert cur.forecast.available and cur.forecast.items[0].short_forecast == "Snow"
    broken = NWSClient(httpx2.AsyncClient(transport=httpx2.MockTransport(lambda r: httpx2.Response(503))), "ua")
    cur = await tools._current(deps_with(None, broken), "denver")
    assert cur.alerts.available is False and cur.forecast.available is False
    assert isinstance(await tools._current(deps_with(None, None), "denver"), Unavailable)
    listing = tools._list(deps)
    assert len(listing.hubs) == 15 and listing.regions == ["Midwest", "Northeast", "South", "West"]
    ctx = SimpleNamespace(deps=deps)
    assert tools.list_hubs(ctx) == listing and tools.about(ctx).product == "t"


def test_criterion_10_real_snapshot_sanity():
    store = Store(ROOT / "data" / "snapshots")
    engine = Engine(store, HubRegistry.load(), load_scoring_config())
    winter = engine.rank("winter")
    assert winter.rows[0].hub_id == "minneapolis"
    first_south = min(r.rank for r in winter.rows if r.region == "South")
    assert sum(1 for r in winter.rows if r.region == "Midwest" and r.rank < first_south) >= 3, winter.rows
    assert engine.rank("hurricane_flood").rows[0].hub_id in {"houston", "miami"}
    assert engine.rank("heat").rows[0].hub_id == "phoenix"
    ys = engine.year_stats("denver", 2025)
    (count,), = store.query("SELECT count(*) FROM daily WHERE hub_id = 'denver' AND year(date) = 2025 AND snow_cm > 0")
    assert ys.snow_days_any == count and ys.snow_days_pct == round(100 * count / 365, 1)
    dallas = engine.score("dallas")
    assert dallas.contributions[0][0] in {"rain", "heat"} and dallas.years_used == list(range(2016, 2026))


def test_criterion_11_eval_smoke_passes_with_tools(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "ledger.db"))
    result = CliRunner().invoke(cli_module.cli, ["eval", "--test", "--tag", "smoke", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_criterion_12_readme_documents_the_rules():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cfg = load_scoring_config()
    for name, hazard in cfg.hazards.items():
        assert f"`{hazard.rule}`" in readme, f"README lacks the rule for {name}"
        assert f"{hazard.weight:g}" in readme
    assert "proxy" in readme and cfg.version in readme
