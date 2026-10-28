"""Typed results of the scoring engine. Tools return these verbatim; the model quotes them, never recomputes."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class HazardScore(BaseModel):
    hazard: str
    label: str
    rule: str
    years: list[int]
    per_year: dict[int, int]
    mean: float = Field(description="expected disruption days per year")
    min: int
    max: int
    stdev: float
    trend: float | None = Field(description="mean of the last half of years minus the first half; None below 4 years")
    weight: float
    contribution: float = Field(description="weight x mean, the hazard's share of the overall score")


class HubScore(BaseModel):
    hub_id: str
    name: str
    region: str
    overall: float = Field(description="weighted expected disruption days per year")
    hazards: dict[str, HazardScore]
    contributions: list[tuple[str, float]] = Field(description="(hazard, contribution) sorted descending")
    years_used: list[int]
    scoring_version: str
    data_through: date


class RankingRow(BaseModel):
    rank: int
    hub_id: str
    name: str
    region: str
    score: float = Field(description="expected disruption days per year for the scope")
    band: tuple[float, float] = Field(description="(min, max) of the yearly sum across the scope's hazards")
    trend: float | None
    by_hazard: dict[str, float]


class Ranking(BaseModel):
    scope: str
    scope_hazards: list[str]
    region: str | None
    rows: list[RankingRow]
    note: str | None = None
    scoring_version: str
    data_through: date


class HazardComparison(BaseModel):
    hazard: str
    label: str
    a: float
    b: float
    a_band: tuple[int, int]
    b_band: tuple[int, int]
    difference: float = Field(description="a minus b, expected disruption days per year")
    higher: str = Field(description="hub id with the higher exposure, or 'tie'")


class Comparison(BaseModel):
    a: str
    b: str
    hazards: list[HazardComparison]
    overall_a: float
    overall_b: float
    note: str | None = None
    scoring_version: str
    data_through: date


class YearStats(BaseModel):
    hub_id: str
    year: int
    days_in_year: int
    days_with_data: int
    snow_days_any: int = Field(description="days with snowfall > 0")
    snow_days_pct: float
    precip_days_any: int = Field(description="days with precipitation > 0")
    precip_days_pct: float
    threshold_days: dict[str, int]
    threshold_days_pct: dict[str, float]
    max_snow_cm: float | None
    max_gust_kmh: float | None
    max_tmax_c: float | None
    min_tmin_c: float | None
    scoring_version: str
    data_through: date
