"""Shared behavioral contract for every analysis-engine adapter."""

from pathlib import Path
from typing import cast

import pytest

from rtl_lens.engines.base import AnalysisEngine
from rtl_lens.engines.pyslang_engine import PySlangEngine
from rtl_lens.engines.verilator_engine import VerilatorEngine
from rtl_lens.models.engine import EngineRequest, EngineState
from rtl_lens.models.project import ResolvedProject

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "projects" / "pyslang_error"
FAKE_VERILATOR = Path(__file__).parents[1] / "fixtures" / "bin" / "fake_verilator.py"


@pytest.fixture(
    params=(PySlangEngine(), VerilatorEngine(FAKE_VERILATOR)),
    ids=lambda engine: engine.name,
)
def engine(request: pytest.FixtureRequest) -> AnalysisEngine:
    """Return each real adapter that must satisfy the shared contract."""
    return cast(AnalysisEngine, request.param)


def test_engine_exposes_identity_and_availability(engine: AnalysisEngine) -> None:
    """Removing any protocol member must make a real adapter fail the common boundary."""
    assert isinstance(engine, AnalysisEngine)
    assert engine.name
    assert engine.available() is True
    assert engine.version()


def test_engine_returns_completed_structured_run(engine: AnalysisEngine) -> None:
    """A source diagnostic is a completed run, never an adapter failure."""
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = engine.run(EngineRequest(project=project, timeout_seconds=10))

    assert result.engine == engine.name
    assert result.version == engine.version()
    assert result.state is EngineState.COMPLETED
    assert result.failure is None
    assert result.diagnostics
    assert all(diagnostic.engine == engine.name for diagnostic in result.diagnostics)
    assert all(
        not Path(diagnostic.location.path).is_absolute() for diagnostic in result.diagnostics
    )


def test_engine_bounds_adapter_exceptions_as_failed_runs(
    engine: AnalysisEngine, tmp_path: Path
) -> None:
    """An in-root missing source must not leak its Python exception past the adapter."""
    project = ResolvedProject(root=tmp_path, sources=(Path("missing.sv"),))

    result = engine.run(EngineRequest(project=project, timeout_seconds=10))

    assert result.engine == engine.name
    assert result.state is EngineState.FAILED
    assert result.diagnostics == ()
    assert result.failure is not None
    assert result.failure.kind == "FileNotFoundError"
    assert 0 < len(result.failure.message) <= 500
    assert result.failure.required is True
