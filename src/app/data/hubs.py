"""Hub registry: the hubs the company operates, from config/hubs.yaml. Regions are data, never a model guess."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import CONFIG_DIR

Region = Literal["Midwest", "South", "West", "Northeast"]
HUBS_PATH = CONFIG_DIR / "hubs.yaml"


class Hub(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1)
    state: str = Field(pattern=r"^[A-Z]{2}$")
    region: Region
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    county_fips: str = Field(pattern=r"^\d{5}$")
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _iana(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as e:
            raise ValueError(f"unknown IANA timezone {v!r}") from e
        return v


class HubsFile(BaseModel):
    version: str
    hubs: list[Hub] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> HubsFile:
        ids = [h.id for h in self.hubs]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate hub ids")
        return self


class HubRegistry:
    def __init__(self, version: str, hubs: list[Hub]) -> None:
        self.version = version
        self.all = list(hubs)
        self._by_id = {h.id: h for h in hubs}
        self._by_name = {h.name.casefold(): h for h in hubs}

    @classmethod
    def load(cls, path: Path = HUBS_PATH) -> HubRegistry:
        data = HubsFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        return cls(data.version, data.hubs)

    def by_id(self, hub_id: str) -> Hub:
        return self._by_id[hub_id]

    def find(self, query: str) -> Hub | None:
        """Resolve an id or display name, case-insensitively; None when unknown."""
        q = query.strip().casefold()
        return self._by_id.get(q.replace(" ", "-")) or self._by_name.get(q)

    def in_region(self, region: str) -> list[Hub]:
        r = region.strip().casefold()
        return [h for h in self.all if h.region.casefold() == r]

    def regions(self) -> list[str]:
        return sorted({h.region for h in self.all})
