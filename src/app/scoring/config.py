"""Scoring configuration: thresholds, weights and hazard groups from config/scoring.yaml, versioned."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import CONFIG_DIR
from app.data.openmeteo import DailyRow

SCORING_PATH = CONFIG_DIR / "scoring.yaml"
VARIABLES = {name for name in DailyRow.model_fields if name not in ("hub_id", "date")}


class Hazard(BaseModel):
    variable: str
    op: Literal[">=", "<="]
    threshold: float
    weight: float = Field(ge=0)
    label: str

    @field_validator("variable")
    @classmethod
    def _known_variable(cls, v: str) -> str:
        if v not in VARIABLES:
            raise ValueError(f"unknown variable {v!r}; expected one of {sorted(VARIABLES)}")
        return v

    @property
    def rule(self) -> str:
        return f"{self.variable} {self.op} {self.threshold:g}"

    def crosses(self, value: float | None) -> bool:
        if value is None:
            return False
        return value >= self.threshold if self.op == ">=" else value <= self.threshold


class ScoringConfig(BaseModel):
    version: str
    hazards: dict[str, Hazard] = Field(min_length=1)
    groups: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _groups_reference_hazards(self) -> ScoringConfig:
        for group, members in self.groups.items():
            unknown = [m for m in members if m not in self.hazards]
            if unknown or not members:
                raise ValueError(f"group {group!r} references unknown hazards {unknown} or is empty")
        return self

    def scopes(self) -> list[str]:
        """Everything a ranking can be sorted by: overall, each hazard, each group."""
        return ["overall", *self.hazards, *[g for g in self.groups if g not in self.hazards]]

    def hazards_in(self, scope: str) -> list[str] | None:
        """Hazards a scope sums over; None for an unknown scope."""
        if scope == "overall":
            return list(self.hazards)
        if scope in self.groups:
            return list(self.groups[scope])
        if scope in self.hazards:
            return [scope]
        return None


def load_scoring_config(path: Path = SCORING_PATH) -> ScoringConfig:
    return ScoringConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
