"""Behavior tests for accessible terminal report output."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from rtl_lens.models.diagnostic import BaselineState
from rtl_lens.models.report import ScanReport
from rtl_lens.renderers.terminal import render_terminal

FIXTURE = Path(__file__).parents[1] / "fixtures" / "reports" / "width-report.json"


def _sample_report() -> ScanReport:
    return ScanReport.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("color_system", [None, "standard"])
def test_terminal_marks_partial_scan_and_summarizes_counts(
    color_system: str | None,
) -> None:
    console = Console(record=True, width=120, color_system=color_system, force_terminal=True)

    render_terminal(_sample_report(), console)
    output = console.export_text(styles=False)

    assert "RTL Lens scan report" in output
    assert "PARTIAL" in output
    assert "2 findings" in output
    assert "2 new" in output
    assert "1 error" in output
    assert "1 warning" in output
    assert "pyslang" in output
    assert "verilator" in output
    assert "score" not in output.lower()


def test_terminal_shows_new_unknown_diagnostics_and_engine_failures_as_plain_text() -> None:
    console = Console(record=True, width=120, color_system=None)

    render_terminal(_sample_report(), console)
    output = console.export_text(styles=False)

    assert "NEW" in output
    assert "ERROR" in output
    assert "WARNING" in output
    assert "width-mismatch" in output
    assert "unknown:pyslang:MYSTERY" in output
    assert "MYSTERY" in output
    assert "rtl/[top].sv:7:2" in output
    assert "raw [link=https://example.invalid]message[/link] is preserved" in output
    assert "UNAVAILABLE" in output
    assert "verilator [bold]boom[/bold] is unavailable" in output
    assert "unexplained" in output.lower()
    assert "score" not in output.lower()


def test_terminal_shows_existing_unexplained_diagnostics_when_there_are_no_new_findings() -> None:
    report = _sample_report()
    existing = tuple(
        finding.model_copy(update={"baseline_state": BaselineState.EXISTING})
        for finding in report.findings
    )
    report = report.model_copy(update={"findings": existing})
    console = Console(record=True, width=120, color_system=None)

    render_terminal(report, console)
    output = console.export_text(styles=False)

    assert "0 new" in output
    assert "New findings" in output
    assert "None" in output
    assert "Unexplained diagnostics" in output
    assert "unknown:pyslang:MYSTERY" in output
    assert "MYSTERY" in output
    assert "raw [link=https://example.invalid]message[/link] is preserved" in output
