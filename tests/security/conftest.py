"""Hostile-but-valid immutable report fixtures for security tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph
from rtl_lens.models.diagnostic import Finding, RawDiagnostic, Severity, SourceLocation
from rtl_lens.models.engine import EngineFailure, EngineRun, EngineState
from rtl_lens.models.report import ScanMetadata, ScanReport

HOME = Path(r"C:\Users\Alice")
PROJECT = r"C:\Users\Alice\chip-project"
CONFIGURED_PREFIX = Path(r"D:\lab\private")
SECRET = "TOKEN-ABC-123"
UNMARKED = "UNMARKED-VALUE-456"
HOSTILE = '<img id="owned" src=x onerror="window.__owned=1">'


@pytest.fixture
def hostile_report() -> ScanReport:
    """Return one report with sensitive canaries in every untrusted text family."""
    location = SourceLocation(
        path=rf"{PROJECT}\rtl\{SECRET}.sv",
        line=3,
        column=5,
    )
    raw = RawDiagnostic(
        engine="verilator",
        engine_version=rf"5.040 from {HOME}",
        original_code=f"WIDTH-{SECRET}",
        severity=Severity.ERROR,
        location=location,
        message=rf"{HOSTILE} {HOME} {CONFIGURED_PREFIX} {SECRET} {UNMARKED}",
        symbol=rf"{CONFIGURED_PREFIX}\secret_symbol",
        source_snippet=f"assign leaked = {SECRET};",
    )
    finding = Finding(
        fingerprint="a" * 64,
        canonical_rule="width-mismatch",
        severity=Severity.ERROR,
        location=location,
        title=f"Sensitive title {SECRET}",
        message=raw.message,
        symbol=raw.symbol,
        source_snippet=raw.source_snippet,
        provenance=(raw,),
    )
    graph_nodes = tuple(sorted((f"child-{SECRET}", rf"top-{CONFIGURED_PREFIX}")))
    graph = ModuleGraph(
        nodes=graph_nodes,
        edges=((graph_nodes[0], graph_nodes[1]),),
        unresolved=(graph_nodes[1],),
    )
    completed = EngineRun(
        engine="verilator",
        state=EngineState.COMPLETED,
        version=rf"5.040 installed under {HOME}",
        diagnostics=(raw,),
        module_graph=graph,
        analysis_warnings=(
            AnalysisWarning(kind="graph-warning", message=f"warning contains {SECRET}"),
        ),
    )
    failed = EngineRun(
        engine="pyslang",
        state=EngineState.FAILED,
        failure=EngineFailure(
            kind="runtime_failure",
            message=rf"failed below {CONFIGURED_PREFIX} with {SECRET}",
            required=True,
        ),
    )
    return ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=PROJECT,
            started_at=datetime(2026, 8, 30, tzinfo=UTC),
            duration_ms=7,
            requested_engines=("pyslang", "verilator"),
            completed_engines=("verilator",),
            config_digest="b" * 64,
            redacted=False,
            source_count=1,
        ),
        findings=(finding,),
        engine_runs=(failed, completed),
        module_graph=graph,
        analysis_warnings=(
            AnalysisWarning(
                kind="report-warning",
                message=rf"report warning from {HOME} contains {SECRET}",
            ),
        ),
    )
