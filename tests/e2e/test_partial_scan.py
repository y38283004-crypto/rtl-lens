"""Public-service partial scan behavior."""

from pathlib import Path

from rtl_lens.engines.pyslang_engine import PySlangEngine
from rtl_lens.engines.verilator_engine import VerilatorEngine
from rtl_lens.models.analysis import ModuleGraph, TrendSummary
from rtl_lens.models.engine import EngineState
from rtl_lens.models.project import EngineMode, ProjectConfig, ResolvedProject, ScanConfig
from rtl_lens.services.scan import ScanService


def test_public_service_returns_partial_for_optional_missing_engine(tmp_path: Path) -> None:
    source = tmp_path / "top.sv"
    source.write_text("module top; endmodule\n", encoding="utf-8")
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))
    pyslang = PySlangEngine()
    unavailable_verilator = VerilatorEngine(executable=tmp_path / "missing-verilator")

    outcome = ScanService((unavailable_verilator, pyslang)).scan(
        project, ProjectConfig(scan=ScanConfig(engine_mode=EngineMode.AUTO))
    )

    assert outcome.exit_code == 0
    assert outcome.report.metadata.scan_state == "partial"
    assert outcome.report.metadata.completed_engines == ("pyslang",)
    assert tuple(run.state for run in outcome.report.engine_runs) == (
        EngineState.COMPLETED,
        EngineState.UNAVAILABLE,
    )
    assert outcome.report.engine_runs[0].version == pyslang.version()
    assert outcome.report.engine_runs[1].failure is not None
    assert outcome.report.engine_runs[1].failure.required is False
    assert outcome.report.module_graph == ModuleGraph(nodes=("top",))
    assert outcome.report.trends == TrendSummary(baseline_configuration_known=True)
    assert outcome.report.analysis_warnings == ()
