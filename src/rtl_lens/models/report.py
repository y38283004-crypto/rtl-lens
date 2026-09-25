"""Immutable, versioned scan-report models consumed by all renderers."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph, TrendSummary
from rtl_lens.models.diagnostic import Finding
from rtl_lens.models.engine import EngineRun


class ScanState(StrEnum):
    """Completeness of the overall scan."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class ScanMetadata(BaseModel):
    """Stable metadata describing when and how a report was produced."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_root: str
    started_at: datetime
    duration_ms: int = Field(ge=0)
    requested_engines: tuple[str, ...]
    completed_engines: tuple[str, ...]
    config_digest: str
    redacted: bool
    scan_state: ScanState = ScanState.COMPLETE
    source_count: int = Field(default=0, ge=0)


class ScanReport(BaseModel):
    """Versioned report contract shared by JSON, terminal, HTML, and CI renderers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    metadata: ScanMetadata
    findings: tuple[Finding, ...]
    engine_runs: tuple[EngineRun, ...] = ()
    resolved_fingerprints: tuple[str, ...] = ()
    module_graph: ModuleGraph = Field(default_factory=ModuleGraph)
    trends: TrendSummary = Field(default_factory=TrendSummary)
    analysis_warnings: tuple[AnalysisWarning, ...] = ()
