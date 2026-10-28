"""Deterministic disruption KPI. Pure functions over DailyRow lists; Engine caches per hub over the immutable snapshot."""

from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from app.data.hubs import Hub, HubRegistry
from app.data.openmeteo import DailyRow
from app.data.store import Store
from app.scoring.config import Hazard, ScoringConfig
from app.scoring.models import (
    Comparison,
    HazardComparison,
    HazardScore,
    HubScore,
    Ranking,
    RankingRow,
    YearStats,
)


def hazard_days(rows: Sequence[DailyRow], hazard: Hazard) -> dict[int, int]:
    """Threshold days per calendar year. A missing value never counts."""
    counts: dict[int, int] = defaultdict(int)
    for r in rows:
        if hazard.crosses(getattr(r, hazard.variable)):
            counts[r.date.year] += 1
    return dict(sorted(counts.items()))


def trend(per_year: dict[int, float]) -> float | None:
    """Mean of the last half of years minus the first half; None below four years."""
    years = sorted(per_year)
    if len(years) < 4:
        return None
    half = len(years) // 2
    first = [per_year[y] for y in years[:half]]
    last = [per_year[y] for y in years[-half:]]
    return round(statistics.fmean(last) - statistics.fmean(first), 2)


def score_hazard(name: str, hazard: Hazard, rows: Sequence[DailyRow], years: Sequence[int]) -> HazardScore:
    counts = hazard_days(rows, hazard)
    per_year = {y: counts.get(y, 0) for y in sorted(years)}
    values = list(per_year.values())
    mean = statistics.fmean(values) if values else 0.0
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return HazardScore(
        hazard=name, label=hazard.label, rule=hazard.rule, years=list(per_year), per_year=per_year,
        mean=round(mean, 2), min=min(values, default=0), max=max(values, default=0), stdev=round(stdev, 2),
        trend=trend(per_year), weight=hazard.weight, contribution=round(hazard.weight * mean, 2),
    )


def score_hub(hub: Hub, rows: Sequence[DailyRow], years: Sequence[int], config: ScoringConfig, data_through: date) -> HubScore:
    hazards = {name: score_hazard(name, h, rows, years) for name, h in config.hazards.items()}
    contributions = sorted(((n, s.contribution) for n, s in hazards.items()), key=lambda t: (-t[1], t[0]))
    overall = sum(h.weight * hazards[n].mean for n, h in config.hazards.items())
    return HubScore(
        hub_id=hub.id, name=hub.name, region=hub.region, overall=round(overall, 2), hazards=hazards,
        contributions=contributions, years_used=sorted(years), scoring_version=config.version, data_through=data_through,
    )


def year_stats(hub_id: str, rows: Sequence[DailyRow], year: int, config: ScoringConfig, data_through: date) -> YearStats:
    days_in_year = 366 if calendar.isleap(year) else 365
    in_year = [r for r in rows if r.date.year == year]

    def pct(n: int) -> float:
        return round(100.0 * n / days_in_year, 1)

    def extreme(values: list[float | None], pick) -> float | None:
        present = [v for v in values if v is not None]
        return pick(present) if present else None

    snow_any = sum(1 for r in in_year if (r.snow_cm or 0) > 0)
    precip_any = sum(1 for r in in_year if (r.precip_mm or 0) > 0)
    threshold_days = {n: sum(1 for r in in_year if h.crosses(getattr(r, h.variable))) for n, h in config.hazards.items()}
    return YearStats(
        hub_id=hub_id, year=year, days_in_year=days_in_year, days_with_data=len(in_year),
        snow_days_any=snow_any, snow_days_pct=pct(snow_any), precip_days_any=precip_any, precip_days_pct=pct(precip_any),
        threshold_days=threshold_days, threshold_days_pct={n: pct(v) for n, v in threshold_days.items()},
        max_snow_cm=extreme([r.snow_cm for r in in_year], max), max_gust_kmh=extreme([r.gust_kmh for r in in_year], max),
        max_tmax_c=extreme([r.tmax_c for r in in_year], max), min_tmin_c=extreme([r.tmin_c for r in in_year], min),
        scoring_version=config.version, data_through=data_through,
    )


class Engine:
    """Scores over the snapshot. Pure inputs, cached per hub; the snapshot never changes while the process runs."""

    def __init__(self, store: Store, registry: HubRegistry, config: ScoringConfig) -> None:
        self.store, self.registry, self.config = store, registry, config
        self._scores: dict[str, HubScore] = {}
        self.hubs_with_data = {c.hub_id for c in store.coverage()}

    @property
    def data_through(self) -> date:
        return self.store.manifest.end

    def score(self, hub_id: str) -> HubScore:
        if hub_id not in self._scores:
            hub = self.registry.by_id(hub_id)
            self._scores[hub_id] = score_hub(hub, self.store.daily(hub_id), self.store.years(hub_id), self.config, self.data_through)
        return self._scores[hub_id]

    def available_years(self, hub_id: str) -> list[int]:
        return self.score(hub_id).years_used

    def _scope_row(self, hs: HubScore, scope: str, hazards: list[str]) -> tuple[float, tuple[float, float], float | None, dict[str, float]]:
        weighted = scope == "overall"
        weight = {h: (self.config.hazards[h].weight if weighted else 1.0) for h in hazards}
        yearly = {y: sum(weight[h] * hs.hazards[h].per_year[y] for h in hazards) for y in hs.years_used}
        score = sum(weight[h] * hs.hazards[h].mean for h in hazards)
        band = (round(min(yearly.values(), default=0.0), 2), round(max(yearly.values(), default=0.0), 2))
        return round(score, 2), band, trend(yearly), {h: hs.hazards[h].mean for h in hazards}

    def rank(self, scope: str = "overall", region: str | None = None, top: int | None = None) -> Ranking:
        hazards = self.config.hazards_in(scope)
        if hazards is None:
            raise KeyError(scope)
        hubs = [h for h in (self.registry.in_region(region) if region else self.registry.all) if h.id in self.hubs_with_data]
        scored = []
        for hub in hubs:
            score, band, tr, by_hazard = self._scope_row(self.score(hub.id), scope, hazards)
            scored.append((score, hub, band, tr, by_hazard))
        scored.sort(key=lambda t: (-t[0], t[1].id))
        rows = [
            RankingRow(rank=i + 1, hub_id=hub.id, name=hub.name, region=hub.region, score=score, band=band, trend=tr, by_hazard=bh)
            for i, (score, hub, band, tr, bh) in enumerate(scored[:top] if top else scored)
        ]
        note = "hurricane/flood exposure is a proxy: heavy-rain and damaging-gust days" if scope == "hurricane_flood" else None
        return Ranking(
            scope=scope, scope_hazards=hazards, region=hubs[0].region if region and hubs else region, rows=rows, note=note,
            scoring_version=self.config.version, data_through=self.data_through,
        )

    def compare(self, a: str, b: str, scope: str = "overall") -> Comparison:
        hazards = self.config.hazards_in(scope)
        if hazards is None:
            raise KeyError(scope)
        sa, sb = self.score(a), self.score(b)
        rows = []
        for h in hazards:
            ha, hb = sa.hazards[h], sb.hazards[h]
            diff = round(ha.mean - hb.mean, 2)
            rows.append(HazardComparison(
                hazard=h, label=ha.label, a=ha.mean, b=hb.mean, a_band=(ha.min, ha.max), b_band=(hb.min, hb.max),
                difference=diff, higher=a if diff > 0 else b if diff < 0 else "tie",
            ))
        note = "hurricane/flood exposure is a proxy: heavy-rain and damaging-gust days" if scope == "hurricane_flood" else None
        return Comparison(
            a=a, b=b, hazards=rows, overall_a=sa.overall, overall_b=sb.overall, note=note,
            scoring_version=self.config.version, data_through=self.data_through,
        )

    def year_stats(self, hub_id: str, year: int) -> YearStats:
        return year_stats(hub_id, self.store.daily(hub_id), year, self.config, self.data_through)
