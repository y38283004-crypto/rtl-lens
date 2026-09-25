"""Immutable normalized and engine-native diagnostic models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """Policy severity assigned to a diagnostic."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class BaselineState(StrEnum):
    """Relationship between a finding and its configured baseline."""

    NEW = "new"
    EXISTING = "existing"
    RESOLVED = "resolved"


class SourceLocation(BaseModel):
    """A repository-relative source range."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    end_line: int | None = Field(default=None, ge=1)
    end_column: int | None = Field(default=None, ge=1)


class RawDiagnostic(BaseModel):
    """A diagnostic emitted by one engine before canonicalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine: str
    engine_version: str | None = None
    original_code: str
    severity: Severity
    location: SourceLocation
    message: str
    symbol: str | None = None
    source_snippet: str | None = None


class Finding(BaseModel):
    """A normalized, user-facing finding with all contributing engine diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fingerprint: str
    canonical_rule: str
    severity: Severity
    location: SourceLocation
    title: str
    message: str = ""
    symbol: str | None = None
    source_snippet: str | None = None
    explanation_id: str | None = None
    baseline_state: BaselineState = BaselineState.NEW
    provenance: tuple[RawDiagnostic, ...] = ()
