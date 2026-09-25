"""Immutable project configuration and resolved project models."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rtl_lens.models.diagnostic import Severity


class EngineMode(StrEnum):
    """How an analysis engine participates in a scan."""

    AUTO = "auto"
    REQUIRED = "required"
    DISABLED = "disabled"


class ScanConfig(BaseModel):
    """Configuration that affects project discovery and scan policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_roots: tuple[Path, ...] = (Path("."),)
    include_dirs: tuple[Path, ...] = ()
    defines: tuple[str, ...] = ()
    top_modules: tuple[str, ...] = ()
    timeout: int = Field(default=30, gt=0)
    language: str = "en"
    engine_mode: EngineMode = EngineMode.AUTO
    output_dir: Path = Path(".rtl-lens")
    baseline_path: Path | None = None
    redact_sources: bool = False
    redact_path_prefixes: tuple[Path, ...] = ()
    redact_environment_variables: tuple[str, ...] = ()
    fail_on: Severity = Severity.ERROR
    graph_display_limit: int = Field(default=200, ge=1, le=2000)

    @field_validator("redact_environment_variables")
    @classmethod
    def valid_redaction_environment_names(cls, names: tuple[str, ...]) -> tuple[str, ...]:
        """Accept deterministic shell environment variable names only."""
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in names):
            raise ValueError("redaction environment names must be valid variable names")
        return tuple(sorted(set(names)))


class ProjectConfig(BaseModel):
    """The effective, validated configuration for one RTL Lens project."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scan: ScanConfig = Field(default_factory=ScanConfig)


class ResolvedProject(BaseModel):
    """A project whose source paths have been checked against its root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    root: Path
    sources: tuple[Path, ...]
    include_dirs: tuple[Path, ...] = ()
    defines: tuple[str, ...] = ()
    top_modules: tuple[str, ...] = ()

    @model_validator(mode="after")
    def sources_are_within_root(self) -> ResolvedProject:
        """Reject direct or symlinked source paths outside the project root."""
        resolved_root = self.root.resolve()
        for source in self.sources:
            resolved_source = (
                source.resolve() if source.is_absolute() else (resolved_root / source).resolve()
            )
            if not resolved_source.is_relative_to(resolved_root):
                raise ValueError("source path must resolve beneath the project root")
        return self
