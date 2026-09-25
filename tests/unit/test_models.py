from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph, TrendSummary
from rtl_lens.models.diagnostic import Finding, Severity, SourceLocation
from rtl_lens.models.engine import EngineRun, EngineState
from rtl_lens.models.project import ResolvedProject
from rtl_lens.models.report import ScanMetadata, ScanReport


def test_resolved_project_rejects_sources_outside_root(tmp_path: Path) -> None:
    """A source outside the resolved project root must never reach an engine."""
    outside = tmp_path.parent / "outside.sv"

    with pytest.raises(ValidationError):
        ResolvedProject(root=tmp_path, sources=(outside,))


def test_scan_report_round_trips_json(tmp_path: Path) -> None:
    """A stable report payload must preserve every supplied domain value."""
    report = ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=".",
            started_at=datetime(2026, 8, 17, tzinfo=UTC),
            duration_ms=12,
            requested_engines=("pyslang",),
            completed_engines=("pyslang",),
            config_digest="0" * 64,
            redacted=False,
        ),
        findings=(
            Finding(
                fingerprint="1" * 64,
                canonical_rule="width-mismatch",
                severity=Severity.ERROR,
                location=SourceLocation(path="top.sv", line=3, column=9),
                title="Assignment width mismatch",
                explanation_id=None,
                provenance=(),
            ),
        ),
    )

    assert ScanReport.model_validate_json(report.model_dump_json()) == report


def test_engine_and_report_round_trip_analysis_artifacts() -> None:
    """Dropping transported analysis artifacts must break the stable report contract."""
    graph = ModuleGraph(nodes=("alu", "top"), edges=(("top", "alu"),))
    warning = AnalysisWarning(kind="module_graph", message="graph extraction failed")
    run = EngineRun(
        engine="pyslang",
        state=EngineState.COMPLETED,
        module_graph=graph,
        analysis_warnings=(warning,),
    )
    report = ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=".",
            started_at=datetime(2026, 8, 17, tzinfo=UTC),
            duration_ms=12,
            requested_engines=("pyslang",),
            completed_engines=("pyslang",),
            config_digest="0" * 64,
            redacted=False,
        ),
        findings=(),
        engine_runs=(run,),
        module_graph=graph,
        trends=TrendSummary(
            new=("a",),
            baseline_configuration_known=True,
            baseline_configured=True,
            comparison_complete=True,
        ),
        analysis_warnings=(warning,),
    )

    assert ScanReport.model_validate_json(report.model_dump_json()) == report


def test_version_1_report_without_analysis_artifacts_uses_empty_defaults() -> None:
    """Version-1.0 JSON emitted before analysis artifacts must remain loadable."""
    legacy_json = """
    {
      "schema_version": "1.0",
      "metadata": {
        "project_root": ".",
        "started_at": "2026-08-17T00:00:00Z",
        "duration_ms": 0,
        "requested_engines": [],
        "completed_engines": [],
        "config_digest": "0000000000000000000000000000000000000000000000000000000000000000",
        "redacted": false,
        "scan_state": "complete",
        "source_count": 0
      },
      "findings": [],
      "engine_runs": [
        {
          "engine": "pyslang",
          "state": "completed",
          "version": "11.0",
          "diagnostics": [],
          "failure": null,
          "duration_ms": 0
        }
      ],
      "resolved_fingerprints": []
    }
    """

    report = ScanReport.model_validate_json(legacy_json)

    assert report.module_graph == ModuleGraph()
    assert report.trends == TrendSummary()
    assert report.analysis_warnings == ()
    assert report.engine_runs[0].module_graph is None
    assert report.engine_runs[0].analysis_warnings == ()
    assert report.trends.baseline_configuration_known is False
    assert report.trends.comparison_complete is False


def test_trend_summary_comparison_state_is_backward_compatible_and_validated() -> None:
    """Legacy payloads stay unknown; known completed comparisons require a baseline."""
    complete = TrendSummary(
        baseline_configuration_known=True,
        baseline_configured=True,
        comparison_complete=True,
    )
    legacy = TrendSummary.model_validate({"baseline_configured": True, "comparison_complete": True})

    assert TrendSummary.model_validate_json(complete.model_dump_json()) == complete
    assert complete.baseline_configuration_known is True
    assert complete.comparison_complete is True
    assert legacy.baseline_configuration_known is False
    assert legacy.comparison_complete is False
    assert TrendSummary.model_validate_json(legacy.model_dump_json()) == legacy
    with pytest.raises(ValidationError, match="requires known baseline configuration"):
        TrendSummary(baseline_configuration_known=True, comparison_complete=True)


def test_engine_unavailable_records_a_serializable_failure() -> None:
    """An unavailable optional engine is reported, rather than raising from orchestration."""
    run = EngineRun.unavailable("verilator", required=False)

    assert run.state is EngineState.UNAVAILABLE
    assert run.failure is not None
    assert run.failure.required is False
    assert run.model_dump(mode="json")["state"] == "unavailable"


def test_domain_models_are_immutable(tmp_path: Path) -> None:
    """Mutating a resolved source list after validation must be rejected."""
    project = ResolvedProject(root=tmp_path, sources=(tmp_path / "top.sv",))

    with pytest.raises(ValidationError):
        project.sources = ()  # type: ignore[misc]
