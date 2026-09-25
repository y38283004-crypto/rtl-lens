"""Immutable requests, results, and failure records for analysis engines."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph
from rtl_lens.models.diagnostic import RawDiagnostic
from rtl_lens.models.project import ResolvedProject


class EngineState(StrEnum):
    """Terminal state of one engine invocation."""

    COMPLETED = "completed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class EngineRequest(BaseModel):
    """Inputs shared by all analysis engines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project: ResolvedProject
    timeout_seconds: int = Field(gt=0)


class EngineFailure(BaseModel):
    """Bounded, serializable context for an engine runtime failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    message: str
    required: bool


class EngineRun(BaseModel):
    """The complete result of a single analysis-engine invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine: str
    state: EngineState
    version: str | None = None
    diagnostics: tuple[RawDiagnostic, ...] = ()
    failure: EngineFailure | None = None
    duration_ms: int = Field(default=0, ge=0)
    module_graph: ModuleGraph | None = None
    analysis_warnings: tuple[AnalysisWarning, ...] = ()

    @classmethod
    def unavailable(cls, engine: str, *, required: bool) -> EngineRun:
        """Return a structured result for an engine absent from this environment."""
        return cls(
            engine=engine,
            state=EngineState.UNAVAILABLE,
            failure=EngineFailure(
                kind="unavailable",
                message=f"{engine} is unavailable",
                required=required,
            ),
        )
