"""Behavior tests for deterministic scan orchestration and policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph, TrendSummary
from rtl_lens.models.diagnostic import RawDiagnostic, Severity, SourceLocation
from rtl_lens.models.engine import EngineRequest, EngineRun, EngineState
from rtl_lens.models.project import EngineMode, ProjectConfig, ResolvedProject, ScanConfig
from rtl_lens.services import scan as scan_module
from rtl_lens.services.scan import ScanService


@dataclass(frozen=True)
class FakeEngine:
    """Protocol-faithful engine double with a fixed terminal result."""

    name: str
    result: EngineRun
    is_available: bool = True

    def version(self) -> str:
        return self.result.version or "test"

    def available(self) -> bool:
        return self.is_available

    def run(self, request: EngineRequest) -> EngineRun:
        del request
        return self.result


def test_automatic_mode_allows_missing_verilator(tmp_path: Path) -> None:
    project = ResolvedProject(root=tmp_path, sources=())
    graph = ModuleGraph(nodes=("top",))
    pyslang = FakeEngine(
        name="pyslang",
        result=EngineRun(
            engine="pyslang",
            state=EngineState.COMPLETED,
            version="11.0",
            module_graph=graph,
        ),
    )
    verilator = FakeEngine(
        name="verilator",
        result=EngineRun.unavailable("verilator", required=False),
        is_available=False,
    )
    config = ProjectConfig(scan=ScanConfig(engine_mode=EngineMode.AUTO))

    outcome = ScanService(engines=(pyslang, verilator)).scan(project, config)

    assert outcome.exit_code == 0
    assert outcome.report.metadata.requested_engines == ("pyslang", "verilator")
    assert outcome.report.metadata.completed_engines == ("pyslang",)
    assert outcome.report.metadata.scan_state == "partial"
    assert tuple(run.state for run in outcome.report.engine_runs) == (
        EngineState.COMPLETED,
        EngineState.UNAVAILABLE,
    )
    assert outcome.report.module_graph == graph


def test_configured_warning_threshold_is_evaluated_by_scan_service(tmp_path: Path) -> None:
    warning = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=1, column=1),
        message="unused",
    )
    engine = FakeEngine(
        name="pyslang",
        result=EngineRun(
            engine="pyslang",
            state=EngineState.COMPLETED,
            diagnostics=(warning,),
        ),
    )
    config = ProjectConfig(scan=ScanConfig(fail_on=Severity.WARNING))

    outcome = ScanService((engine,)).scan(
        ResolvedProject(root=tmp_path, sources=(Path("top.sv"),)), config
    )

    assert outcome.exit_code == 1


def test_required_verilator_unavailability_blocks_requested_completeness(
    tmp_path: Path,
) -> None:
    project = ResolvedProject(root=tmp_path, sources=())
    graph = ModuleGraph(nodes=("top",))
    pyslang = FakeEngine(
        name="pyslang",
        result=EngineRun(
            engine="pyslang",
            state=EngineState.COMPLETED,
            module_graph=graph,
        ),
    )
    verilator = FakeEngine(
        name="verilator",
        result=EngineRun.unavailable("verilator", required=False),
        is_available=False,
    )
    config = ProjectConfig(scan=ScanConfig(engine_mode=EngineMode.REQUIRED))

    outcome = ScanService(engines=(pyslang, verilator)).scan(project, config)

    assert outcome.exit_code == 2
    assert outcome.report.metadata.scan_state == "failed"
    assert outcome.report.engine_runs[1].failure is not None
    assert outcome.report.engine_runs[1].failure.required is True
    assert outcome.report.module_graph == graph


def test_required_failed_run_without_failure_metadata_is_normalized(
    tmp_path: Path,
) -> None:
    project = ResolvedProject(root=tmp_path, sources=())
    pyslang = FakeEngine(
        name="pyslang",
        result=EngineRun(engine="pyslang", state=EngineState.FAILED),
    )

    outcome = ScanService((pyslang,)).scan(project, ProjectConfig())

    assert outcome.exit_code == 2
    assert outcome.report.metadata.scan_state == "failed"
    run = outcome.report.engine_runs[0]
    assert run.failure is not None
    assert run.failure.kind == "engine_failure"
    assert run.failure.message == "pyslang returned failed without failure metadata"
    assert run.failure.required is True


def test_synthesized_failure_message_is_bounded_for_long_engine_name(
    tmp_path: Path,
) -> None:
    long_name = "x" * 600
    engine = FakeEngine(
        name=long_name,
        result=EngineRun(engine=long_name, state=EngineState.FAILED),
    )

    outcome = ScanService((engine,)).scan(
        ResolvedProject(root=tmp_path, sources=()), ProjectConfig()
    )

    run = outcome.report.engine_runs[0]
    assert outcome.exit_code == 2
    assert run.failure is not None
    assert run.failure.message == "x" * 500
    assert run.failure.required is True


def test_completed_engine_findings_are_merged_enriched_and_block_when_new(
    tmp_path: Path,
) -> None:
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    location = SourceLocation(path="top.sv", line=4, column=7)
    pyslang_diagnostic = RawDiagnostic(
        engine="pyslang",
        engine_version="11.0",
        original_code="constant-conversion",
        severity=Severity.ERROR,
        location=location,
        message="implicit conversion changes width",
    )
    verilator_diagnostic = RawDiagnostic(
        engine="verilator",
        engine_version="5.0",
        original_code="WIDTH",
        severity=Severity.WARNING,
        location=location,
        message="operator width does not match",
    )
    service = ScanService(
        engines=(
            FakeEngine(
                name="verilator",
                result=EngineRun(
                    engine="verilator",
                    state=EngineState.COMPLETED,
                    diagnostics=(verilator_diagnostic,),
                ),
            ),
            FakeEngine(
                name="pyslang",
                result=EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(pyslang_diagnostic,),
                ),
            ),
        )
    )

    outcome = service.scan(project, ProjectConfig())

    assert outcome.exit_code == 1
    assert outcome.report.metadata.scan_state == "complete"
    assert len(outcome.report.findings) == 1
    finding = outcome.report.findings[0]
    assert finding.canonical_rule == "width-mismatch"
    assert finding.severity is Severity.ERROR
    assert finding.explanation_id == "width-mismatch"
    assert tuple(native.engine for native in finding.provenance) == (
        "pyslang",
        "verilator",
    )
    assert all(run.state is EngineState.COMPLETED for run in outcome.report.engine_runs)


def test_scan_selects_only_completed_pyslang_graph_and_sorts_warnings(
    tmp_path: Path,
) -> None:
    """Verilator artifacts must not replace the canonical PySlang graph or warning order."""
    pyslang_graph = ModuleGraph(nodes=("alu", "top"), edges=(("top", "alu"),))
    verilator_graph = ModuleGraph(nodes=("wrong",))
    pyslang_warnings = (
        AnalysisWarning(kind="zeta", message="last within pyslang"),
        AnalysisWarning(kind="alpha", message="first within pyslang"),
    )
    verilator_warning = AnalysisWarning(kind="beta", message="from verilator")
    pyslang = FakeEngine(
        "pyslang",
        EngineRun(
            engine="pyslang",
            state=EngineState.COMPLETED,
            module_graph=pyslang_graph,
            analysis_warnings=pyslang_warnings,
        ),
    )
    verilator = FakeEngine(
        "verilator",
        EngineRun(
            engine="verilator",
            state=EngineState.COMPLETED,
            module_graph=verilator_graph,
            analysis_warnings=(verilator_warning,),
        ),
    )

    outcome = ScanService((verilator, pyslang)).scan(
        ResolvedProject(root=tmp_path, sources=()), ProjectConfig()
    )

    assert outcome.report.module_graph == pyslang_graph
    assert outcome.report.analysis_warnings == (
        pyslang_warnings[1],
        pyslang_warnings[0],
        verilator_warning,
    )


def test_graph_warning_retains_findings_completeness_and_exit_policy(
    tmp_path: Path,
) -> None:
    """Report-only graph degradation must not alter diagnostic scan semantics."""
    warning = AnalysisWarning(kind="module_graph", message="graph extraction failed")
    diagnostic = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=1, column=1),
        message="unused",
    )
    pyslang = FakeEngine(
        "pyslang",
        EngineRun(
            engine="pyslang",
            state=EngineState.COMPLETED,
            diagnostics=(diagnostic,),
            analysis_warnings=(warning,),
        ),
    )

    outcome = ScanService((pyslang,)).scan(
        ResolvedProject(root=tmp_path, sources=(Path("top.sv"),)),
        ProjectConfig(),
    )

    assert outcome.exit_code == 0
    assert outcome.report.metadata.scan_state == "complete"
    assert len(outcome.report.findings) == 1
    assert outcome.report.analysis_warnings == (warning,)
    assert outcome.report.module_graph == ModuleGraph()
    assert outcome.report.trends == TrendSummary(
        new=(outcome.report.findings[0].fingerprint,),
        baseline_configuration_known=True,
        baseline_configured=False,
    )
    assert outcome.report.trends.comparison_complete is False


def test_disabled_verilator_is_not_requested_or_run(tmp_path: Path) -> None:
    class DisabledEngine(FakeEngine):
        def available(self) -> bool:
            raise AssertionError("disabled engine must not be inspected")

    project = ResolvedProject(root=tmp_path, sources=())
    pyslang = FakeEngine("pyslang", EngineRun(engine="pyslang", state="completed"))
    verilator = DisabledEngine("verilator", EngineRun(engine="verilator", state="completed"))
    config = ProjectConfig(scan=ScanConfig(engine_mode=EngineMode.DISABLED))

    outcome = ScanService((verilator, pyslang)).scan(project, config)

    assert outcome.exit_code == 0
    assert outcome.report.metadata.requested_engines == ("pyslang",)


def test_malformed_baseline_returns_three_without_running_engines(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text("not json", encoding="utf-8")

    class UncalledEngine(FakeEngine):
        def available(self) -> bool:
            raise AssertionError("invalid baseline must stop before engines")

    config = ProjectConfig(scan=ScanConfig(baseline_path=tmp_path / "baseline.json"))
    project = ResolvedProject(root=tmp_path, sources=())
    engine = UncalledEngine("pyslang", EngineRun(engine="pyslang", state="completed"))

    outcome = ScanService((engine,)).scan(project, config)

    assert outcome.exit_code == 3
    assert outcome.report.metadata.scan_state == "failed"
    assert outcome.report.engine_runs == ()
    assert outcome.report.module_graph == ModuleGraph()
    assert outcome.report.trends == TrendSummary(
        baseline_configuration_known=True,
        baseline_configured=True,
    )
    assert outcome.report.trends.comparison_complete is False
    assert outcome.report.analysis_warnings == ()


def test_unsupported_language_stops_before_clean_engine(tmp_path: Path) -> None:
    class UncalledEngine(FakeEngine):
        def available(self) -> bool:
            raise AssertionError("unsupported language must stop before engines")

    project = ResolvedProject(root=tmp_path, sources=())
    clean = UncalledEngine(
        "pyslang",
        EngineRun(engine="pyslang", state=EngineState.COMPLETED),
    )
    config = ProjectConfig(scan=ScanConfig(language="fr"))

    outcome = ScanService((clean,)).scan(project, config)

    assert outcome.exit_code == 3
    assert outcome.report.metadata.scan_state == "failed"
    assert outcome.report.findings == ()
    assert outcome.report.engine_runs == ()
    assert outcome.report.module_graph == ModuleGraph()
    assert outcome.report.trends == TrendSummary(baseline_configuration_known=True)
    assert outcome.report.analysis_warnings == ()


def test_unsupported_language_stops_before_baseline_and_engines(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    class UncalledEngine(FakeEngine):
        def available(self) -> bool:
            raise AssertionError("unsupported language must stop before engines")

    def fail_if_baseline_is_loaded(project: ResolvedProject, config: ProjectConfig) -> None:
        del project, config
        raise AssertionError("unsupported language must stop before baseline loading")

    monkeypatch.setattr(scan_module, "_load_baseline", fail_if_baseline_is_loaded)
    project = ResolvedProject(root=tmp_path, sources=())
    engine = UncalledEngine(
        "pyslang",
        EngineRun(engine="pyslang", state=EngineState.COMPLETED),
    )
    config = ProjectConfig(scan=ScanConfig(language="fr", baseline_path=tmp_path / "baseline.json"))

    outcome = ScanService((engine,)).scan(project, config)

    assert outcome.exit_code == 3
    assert outcome.report.metadata.scan_state == "failed"
    assert outcome.report.findings == ()
    assert outcome.report.engine_runs == ()


def test_unsupported_language_outprioritizes_required_failure_and_new_error(
    tmp_path: Path,
) -> None:
    diagnostic = RawDiagnostic(
        engine="verilator",
        original_code="WIDTH",
        severity=Severity.ERROR,
        location=SourceLocation(path="top.sv", line=1, column=1),
        message="width differs",
    )

    class UncalledEngine(FakeEngine):
        def available(self) -> bool:
            raise AssertionError("configuration exit 3 must stop before engines")

    required_failure = UncalledEngine(
        "pyslang",
        EngineRun(engine="pyslang", state=EngineState.FAILED),
    )
    new_error = UncalledEngine(
        "verilator",
        EngineRun(
            engine="verilator",
            state=EngineState.COMPLETED,
            diagnostics=(diagnostic,),
        ),
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    config = ProjectConfig(scan=ScanConfig(language="fr", engine_mode=EngineMode.REQUIRED))

    outcome = ScanService((new_error, required_failure)).scan(project, config)

    assert outcome.exit_code == 3
    assert outcome.report.metadata.scan_state == "failed"
    assert outcome.report.metadata.requested_engines == ("pyslang", "verilator")
    assert outcome.report.engine_runs == ()
    assert outcome.report.findings == ()


def test_baseline_marks_same_error_existing_and_nonblocking(tmp_path: Path) -> None:
    location = SourceLocation(path="top.sv", line=2, column=3)
    diagnostic = RawDiagnostic(
        engine="verilator",
        original_code="WIDTH",
        severity=Severity.ERROR,
        location=location,
        message="width differs",
    )
    removed = RawDiagnostic(
        engine="verilator",
        original_code="UNUSEDSIGNAL",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=8, column=2),
        message="signal is unused",
    )
    baseline_engine = FakeEngine(
        "verilator",
        EngineRun(engine="verilator", state="completed", diagnostics=(diagnostic, removed)),
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    first = ScanService((baseline_engine,)).scan(project, ProjectConfig())
    baseline = tmp_path / "baseline.json"
    baseline.write_text(first.report.model_dump_json(), encoding="utf-8")
    config = ProjectConfig(scan=ScanConfig(baseline_path=tmp_path / "baseline.json"))

    current_engine = FakeEngine(
        "verilator",
        EngineRun(engine="verilator", state="completed", diagnostics=(diagnostic,)),
    )
    second = ScanService((current_engine,)).scan(project, config)

    assert second.exit_code == 0
    assert second.report.findings[0].baseline_state == "existing"
    assert second.report.resolved_fingerprints == (first.report.findings[1].fingerprint,)
    assert second.report.trends == TrendSummary(
        unchanged=(second.report.findings[0].fingerprint,),
        resolved=(first.report.findings[1].fingerprint,),
        baseline_configuration_known=True,
        baseline_configured=True,
        comparison_complete=True,
    )


@pytest.mark.parametrize(
    ("engine_mode", "expected_state", "expected_exit"),
    (
        (EngineMode.AUTO, "partial", 0),
        (EngineMode.REQUIRED, "failed", 2),
    ),
    ids=("optional-missing", "required-failed"),
)
def test_incomplete_current_engine_coverage_withholds_absence_based_resolution(
    engine_mode: EngineMode,
    expected_state: str,
    expected_exit: int,
    tmp_path: Path,
) -> None:
    existing = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=2, column=1),
        message="existing",
    )
    removed = existing.model_copy(
        update={
            "original_code": "undeclared-identifier",
            "location": SourceLocation(path="top.sv", line=8, column=1),
            "message": "removed",
        }
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    baseline = ScanService(
        (
            FakeEngine(
                "pyslang",
                EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(existing, removed),
                ),
            ),
            FakeEngine(
                "verilator",
                EngineRun(engine="verilator", state=EngineState.COMPLETED),
            ),
        )
    ).scan(project, ProjectConfig())
    (tmp_path / "baseline.json").write_text(baseline.report.model_dump_json(), encoding="utf-8")
    current = ScanService(
        (
            FakeEngine(
                "pyslang",
                EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(existing,),
                ),
            ),
            FakeEngine(
                "verilator",
                EngineRun.unavailable("verilator", required=False),
                is_available=False,
            ),
        )
    ).scan(
        project,
        ProjectConfig(
            scan=ScanConfig(
                baseline_path=tmp_path / "baseline.json",
                engine_mode=engine_mode,
            )
        ),
    )

    assert current.exit_code == expected_exit
    assert current.report.metadata.scan_state == expected_state
    assert current.report.findings[0].baseline_state == "existing"
    assert current.report.resolved_fingerprints == ()
    assert current.report.trends.resolved == ()
    assert current.report.trends.comparison_complete is False


def test_changed_engine_set_withholds_absence_based_resolution(tmp_path: Path) -> None:
    existing = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=2, column=1),
        message="existing",
    )
    removed = existing.model_copy(
        update={
            "original_code": "undeclared-identifier",
            "location": SourceLocation(path="top.sv", line=8, column=1),
            "message": "removed",
        }
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    baseline = ScanService(
        (
            FakeEngine(
                "pyslang",
                EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(existing, removed),
                ),
            ),
        )
    ).scan(project, ProjectConfig())
    (tmp_path / "baseline.json").write_text(baseline.report.model_dump_json(), encoding="utf-8")
    current = ScanService(
        (
            FakeEngine(
                "pyslang",
                EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(existing,),
                ),
            ),
            FakeEngine(
                "verilator",
                EngineRun(engine="verilator", state=EngineState.COMPLETED),
            ),
        )
    ).scan(
        project,
        ProjectConfig(scan=ScanConfig(baseline_path=tmp_path / "baseline.json")),
    )

    assert current.report.metadata.scan_state == "complete"
    assert current.report.findings[0].baseline_state == "existing"
    assert current.report.resolved_fingerprints == ()
    assert current.report.trends.resolved == ()
    assert current.report.trends.comparison_complete is False


def test_incomplete_baseline_engine_coverage_withholds_absence_based_resolution(
    tmp_path: Path,
) -> None:
    existing = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=2, column=1),
        message="existing",
    )
    removed = existing.model_copy(
        update={
            "original_code": "undeclared-identifier",
            "location": SourceLocation(path="top.sv", line=8, column=1),
            "message": "removed",
        }
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    baseline = ScanService(
        (
            FakeEngine(
                "pyslang",
                EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(existing, removed),
                ),
            ),
            FakeEngine(
                "verilator",
                EngineRun.unavailable("verilator", required=False),
                is_available=False,
            ),
        )
    ).scan(project, ProjectConfig())
    assert baseline.report.metadata.scan_state == "partial"
    (tmp_path / "baseline.json").write_text(baseline.report.model_dump_json(), encoding="utf-8")
    current = ScanService(
        (
            FakeEngine(
                "pyslang",
                EngineRun(
                    engine="pyslang",
                    state=EngineState.COMPLETED,
                    diagnostics=(existing,),
                ),
            ),
            FakeEngine(
                "verilator",
                EngineRun(engine="verilator", state=EngineState.COMPLETED),
            ),
        )
    ).scan(
        project,
        ProjectConfig(scan=ScanConfig(baseline_path=tmp_path / "baseline.json")),
    )

    assert current.report.metadata.scan_state == "complete"
    assert current.report.findings[0].baseline_state == "existing"
    assert current.report.resolved_fingerprints == ()
    assert current.report.trends.resolved == ()
    assert current.report.trends.comparison_complete is False


def test_unexpected_engine_exception_is_contained_and_later_engine_runs(tmp_path: Path) -> None:
    class BrokenEngine(FakeEngine):
        def run(self, request: EngineRequest) -> EngineRun:
            del request
            raise RuntimeError("adapter exploded")

    broken = BrokenEngine("pyslang", EngineRun(engine="pyslang", state="completed"))
    later = FakeEngine("verilator", EngineRun(engine="verilator", state="completed"))
    project = ResolvedProject(root=tmp_path, sources=())

    outcome = ScanService((later, broken)).scan(project, ProjectConfig())

    assert outcome.exit_code == 2
    assert tuple(run.state for run in outcome.report.engine_runs) == (
        EngineState.FAILED,
        EngineState.COMPLETED,
    )
    assert outcome.report.engine_runs[0].failure is not None


def test_required_failure_outprioritizes_new_error(tmp_path: Path) -> None:
    diagnostic = RawDiagnostic(
        engine="verilator",
        original_code="WIDTH",
        severity=Severity.ERROR,
        location=SourceLocation(path="top.sv", line=1, column=1),
        message="width differs",
    )
    required_failure = FakeEngine(
        "pyslang",
        EngineRun(
            engine="pyslang",
            state=EngineState.FAILED,
            module_graph=ModuleGraph(nodes=("stale",)),
        ),
    )
    blocking = FakeEngine(
        "verilator",
        EngineRun(
            engine="verilator",
            state=EngineState.COMPLETED,
            diagnostics=(diagnostic,),
        ),
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))

    outcome = ScanService((blocking, required_failure)).scan(project, ProjectConfig())

    assert outcome.exit_code == 2
    assert outcome.report.metadata.scan_state == "failed"
    assert len(outcome.report.findings) == 1
    assert outcome.report.findings[0].severity is Severity.ERROR
    assert outcome.report.module_graph == ModuleGraph()


def test_redaction_and_injected_clock_are_reflected(tmp_path: Path) -> None:
    times = iter(
        (
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(milliseconds=125),
        )
    )
    diagnostic = RawDiagnostic(
        engine="verilator",
        original_code="WIDTH",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=1, column=1),
        message="width differs",
        source_snippet="secret source",
    )
    engine = FakeEngine(
        "verilator",
        EngineRun(engine="verilator", state="completed", diagnostics=(diagnostic,)),
    )
    config = ProjectConfig(scan=ScanConfig(redact_sources=True))

    outcome = ScanService((engine,), clock=lambda: next(times)).scan(
        ResolvedProject(root=tmp_path, sources=(Path("top.sv"),)), config
    )

    assert outcome.report.metadata.duration_ms == 125
    assert outcome.report.findings[0].source_snippet is None
    assert outcome.report.findings[0].provenance[0].source_snippet is None
