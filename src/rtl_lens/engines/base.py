"""Shared interface implemented by every analysis engine."""

from typing import Protocol, runtime_checkable

from rtl_lens.models.engine import EngineRequest, EngineRun


@runtime_checkable
class AnalysisEngine(Protocol):
    """Behavior required by engine orchestration and contract tests."""

    name: str

    def version(self) -> str:
        """Return the native engine version."""
        ...

    def available(self) -> bool:
        """Return whether the engine can run in the current environment."""
        ...

    def run(self, request: EngineRequest) -> EngineRun:
        """Analyze one resolved project without leaking adapter exceptions."""
        ...
