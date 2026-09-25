"""Immutable deterministic models used by analysis summaries."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ModuleGraph(BaseModel):
    """A canonical directed graph of module instantiations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    unresolved: tuple[str, ...] = ()

    @model_validator(mode="after")
    def is_canonical(self) -> ModuleGraph:
        """Require canonical tuples so consumers receive stable JSON."""
        if self.nodes != tuple(sorted(set(self.nodes))):
            raise ValueError("nodes must be sorted and unique")
        node_set = set(self.nodes)
        if self.edges != tuple(sorted(set(self.edges))):
            raise ValueError("edges must be sorted and unique")
        if self.unresolved != tuple(sorted(set(self.unresolved))):
            raise ValueError("unresolved must be sorted and unique")
        if any(parent not in node_set or child not in node_set for parent, child in self.edges):
            raise ValueError("edge endpoints must be present in nodes")
        if any(name not in node_set for name in self.unresolved):
            raise ValueError("unresolved names must be present in nodes")
        return self


class AnalysisWarning(BaseModel):
    """A bounded warning emitted while deriving report-only analysis data."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    kind: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class TrendSummary(BaseModel):
    """Canonical baseline-state partitions for current and resolved findings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    new: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    resolved: tuple[str, ...] = ()
    baseline_configured: bool = False
    baseline_configuration_known: bool = False
    comparison_complete: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_unknown_legacy_comparison(cls, data: Any) -> Any:
        """Discard old completeness claims that predate known configuration status."""
        if (
            isinstance(data, dict)
            and data.get("comparison_complete") is True
            and not data.get("baseline_configuration_known", False)
        ):
            return {**data, "comparison_complete": False}
        return data

    @model_validator(mode="after")
    def is_canonical(self) -> TrendSummary:
        """Require sorted disjoint partitions with no duplicate fingerprints."""
        partitions = (self.new, self.unchanged, self.resolved)
        if any(partition != tuple(sorted(set(partition))) for partition in partitions):
            raise ValueError("trend partitions must be sorted and unique")
        combined = self.new + self.unchanged + self.resolved
        if len(set(combined)) != len(combined):
            raise ValueError("a fingerprint may appear in only one trend partition")
        if self.comparison_complete and not (
            self.baseline_configuration_known and self.baseline_configured
        ):
            raise ValueError(
                "a complete comparison requires known baseline configuration "
                "and a configured baseline"
            )
        return self
