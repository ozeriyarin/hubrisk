"""Tools the model may call. Every tool is deterministic code over the data; the model only chooses and explains.

Tools never raise: an unknown hub, region, scope or year comes back as `NotFound` with the valid values, and a
missing snapshot as `Unavailable`. Every scored result carries `scoring_version` and `data_through`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from app import __version__
from app.agent.prompts import SCOPE_DESCRIPTION
from app.alerts import LiveRisk, assess
from app.data.hubs import Hub, HubRegistry
from app.data.nws import Alert, ForecastPeriod, Live, NWSClient
from app.data.store import Store
from app.scoring.engine import Engine
from app.scoring.models import Comparison, HubScore, Ranking, YearStats


@dataclass
class ToolContext:
    """Everything tools need. Built once at startup by `cli.compose`, injected per run as `deps`."""

    product_name: str
    hubs: HubRegistry | None = None
    store: Store | None = None  # None when no snapshot is present; historical tools then return Unavailable
    nws: NWSClient | None = None
    engine: Engine | None = None


class About(BaseModel):
    product: str
    version: str
    scope: str


class NotFound(BaseModel):
    kind: str = Field(description="what was not found: hub, region, scope or year")
    query: str
    valid: list[str]
    hint: str


class Unavailable(BaseModel):
    reason: str


class HubSummary(BaseModel):
    id: str
    name: str
    state: str
    region: str


class HubList(BaseModel):
    hubs: list[HubSummary]
    regions: list[str]
    scopes: list[str] = Field(description="what rank_hubs/compare_hubs accept: overall, hazards, groups")
    hazards: dict[str, str] = Field(description="hazard -> threshold rule")
    scoring_version: str | None
    data_through: date | None


class CurrentConditions(BaseModel):
    hub_id: str
    name: str
    alerts: Live[Alert]
    forecast: Live[ForecastPeriod]
    live_risk: LiveRisk | None = Field(default=None, description="deterministic live level: none/watch/warning, with drivers")
    note: str = "live NWS data; reported beside the historical score, never blended into it"


def about(ctx: RunContext[ToolContext]) -> About:
    """What this assistant is and what it covers. Call when the user asks what you can do."""
    return About(product=ctx.deps.product_name, version=__version__, scope=SCOPE_DESCRIPTION)


def _engine(deps: ToolContext) -> Engine | Unavailable:
    if deps.engine is None:
        return Unavailable(reason="historical weather snapshot not loaded; run `agent ingest` to enable scoring")
    return deps.engine


def _hub(deps: ToolContext, query: str) -> Hub | NotFound:
    hub = deps.hubs.find(query) if deps.hubs else None
    if hub is None:
        valid = [h.id for h in deps.hubs.all] if deps.hubs else []
        return NotFound(kind="hub", query=query, valid=valid, hint="use one of the hub ids; call list_hubs for names")
    return hub


def _scope(engine: Engine, scope: str) -> str | NotFound:
    if engine.config.hazards_in(scope) is None:
        return NotFound(kind="scope", query=scope, valid=engine.config.scopes(), hint="overall, a hazard or a hazard group")
    return scope


def _region(deps: ToolContext, region: str | None) -> str | None | NotFound:
    if region is None or not deps.hubs:
        return None
    hubs = deps.hubs.in_region(region)
    if not hubs:
        return NotFound(kind="region", query=region, valid=deps.hubs.regions(), hint="US Census regions")
    return hubs[0].region


def _rank(deps: ToolContext, scope: str = "overall", region: str | None = None, top: int = 10) -> Ranking | NotFound | Unavailable:
    engine = _engine(deps)
    if isinstance(engine, Unavailable):
        return engine
    if isinstance(s := _scope(engine, scope), NotFound):
        return s
    if isinstance(r := _region(deps, region), NotFound):
        return r
    return engine.rank(scope, r, top if 1 <= top <= 50 else 10)


def _compare(deps: ToolContext, hub_a: str, hub_b: str, scope: str = "overall") -> Comparison | NotFound | Unavailable:
    engine = _engine(deps)
    if isinstance(engine, Unavailable):
        return engine
    a, b = _hub(deps, hub_a), _hub(deps, hub_b)
    if isinstance(a, NotFound):
        return a
    if isinstance(b, NotFound):
        return b
    if isinstance(s := _scope(engine, scope), NotFound):
        return s
    return engine.compare(a.id, b.id, s)


def _hub_score(deps: ToolContext, hub: str) -> HubScore | NotFound | Unavailable:
    engine = _engine(deps)
    if isinstance(engine, Unavailable):
        return engine
    h = _hub(deps, hub)
    return h if isinstance(h, NotFound) else engine.score(h.id)


def _year_stats(deps: ToolContext, hub: str, year: int) -> YearStats | NotFound | Unavailable:
    engine = _engine(deps)
    if isinstance(engine, Unavailable):
        return engine
    h = _hub(deps, hub)
    if isinstance(h, NotFound):
        return h
    years = engine.available_years(h.id)
    if year not in years:
        return NotFound(kind="year", query=str(year), valid=[str(y) for y in years], hint="complete years in the snapshot")
    return engine.year_stats(h.id, year)


async def _current(deps: ToolContext, hub: str) -> CurrentConditions | NotFound | Unavailable:
    h = _hub(deps, hub)
    if isinstance(h, NotFound):
        return h
    if deps.nws is None:
        return Unavailable(reason="live weather client not configured")
    alerts, forecast = await deps.nws.alerts(h), await deps.nws.forecast(h)
    return CurrentConditions(hub_id=h.id, name=h.name, alerts=alerts, forecast=forecast, live_risk=assess(h.id, alerts, forecast))


def _list(deps: ToolContext) -> HubList | Unavailable:
    if deps.hubs is None:
        return Unavailable(reason="hub registry not loaded")
    engine = deps.engine
    return HubList(
        hubs=[HubSummary(id=h.id, name=h.name, state=h.state, region=h.region) for h in deps.hubs.all],
        regions=deps.hubs.regions(),
        scopes=engine.config.scopes() if engine else [],
        hazards={n: h.rule for n, h in engine.config.hazards.items()} if engine else {},
        scoring_version=engine.config.version if engine else None,
        data_through=engine.data_through if engine else None,
    )


def rank_hubs(ctx: RunContext[ToolContext], scope: str = "overall", region: str | None = None, top: int = 10) -> Ranking | NotFound | Unavailable:
    """Rank hubs by expected disruption days per year. scope: overall, a hazard (snow, wind, rain, cold, heat) or a group (winter, hurricane_flood); region filters (Midwest, South, West, Northeast)."""
    return _rank(ctx.deps, scope, region, top)


def compare_hubs(ctx: RunContext[ToolContext], hub_a: str, hub_b: str, scope: str = "overall") -> Comparison | NotFound | Unavailable:
    """Compare two hubs hazard by hazard: expected disruption days per year, min/max band, difference, which is higher."""
    return _compare(ctx.deps, hub_a, hub_b, scope)


def hub_score(ctx: RunContext[ToolContext], hub: str) -> HubScore | NotFound | Unavailable:
    """Full score breakdown for one hub: per-hazard disruption days, uncertainty band, trend and contributions (why it is high or low)."""
    return _hub_score(ctx.deps, hub)


def hub_year_stats(ctx: RunContext[ToolContext], hub: str, year: int) -> YearStats | NotFound | Unavailable:
    """Statistics for one hub and calendar year: days with any snowfall/precipitation and their percentage, threshold days, extremes."""
    return _year_stats(ctx.deps, hub, year)


async def current_conditions(ctx: RunContext[ToolContext], hub: str) -> CurrentConditions | NotFound | Unavailable:
    """Live NOAA NWS active alerts and 7-day forecast for a hub (right now), separate from the historical score."""
    return await _current(ctx.deps, hub)


def list_hubs(ctx: RunContext[ToolContext]) -> HubList | Unavailable:
    """All hubs with ids, regions, the accepted ranking scopes and the hazard threshold rules."""
    return _list(ctx.deps)


def build_toolset() -> FunctionToolset[ToolContext]:
    toolset: FunctionToolset[ToolContext] = FunctionToolset()
    for fn in (about, list_hubs, rank_hubs, compare_hubs, hub_score, hub_year_stats, current_conditions):
        toolset.add_function(fn)
    return toolset
