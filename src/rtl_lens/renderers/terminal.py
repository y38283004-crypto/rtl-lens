"""Accessible terminal rendering for immutable scan reports."""

from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.text import Text

from rtl_lens.models.diagnostic import BaselineState, Finding, Severity
from rtl_lens.models.engine import EngineRun
from rtl_lens.models.report import ScanReport, ScanState

_STATE_STYLES = {
    ScanState.COMPLETE: "bold green",
    ScanState.PARTIAL: "bold yellow",
    ScanState.FAILED: "bold red",
}
_SEVERITY_STYLES = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "bold yellow",
    Severity.INFO: "bold blue",
}


def render_terminal(report: ScanReport, console: Console) -> None:
    """Render completeness, findings, and engine failures without score-like output."""
    console.print(Text("RTL Lens scan report", style="bold"))
    console.print(_summary(report))
    console.print(_project_line(report))

    console.print(Text("Engines", style="bold"))
    for run in report.engine_runs:
        console.print(_engine_line(run))

    new_findings = tuple(
        finding for finding in report.findings if finding.baseline_state is BaselineState.NEW
    )
    console.print(Text("New findings", style="bold"))
    if not new_findings:
        console.print(Text("  None"))
    else:
        for finding in new_findings:
            _render_finding(finding, console)

    unexplained = tuple(finding for finding in report.findings if finding.explanation_id is None)
    console.print(Text("Unexplained diagnostics", style="bold"))
    if not unexplained:
        console.print(Text("  None"))
    else:
        for finding in unexplained:
            _render_unexplained(finding, console)


def _summary(report: ScanReport) -> Text:
    severity_counts = Counter(finding.severity for finding in report.findings)
    new_count = sum(finding.baseline_state is BaselineState.NEW for finding in report.findings)
    line = Text("Status: ")
    state = report.metadata.scan_state
    line.append(state.value.upper(), style=_STATE_STYLES[state])
    line.append(
        f" | {len(report.findings)} findings | {new_count} new"
        f" | {severity_counts[Severity.ERROR]} error"
        f" | {severity_counts[Severity.WARNING]} warning"
        f" | {severity_counts[Severity.INFO]} info"
    )
    return line


def _project_line(report: ScanReport) -> Text:
    line = Text("Project: ")
    line.append(report.metadata.project_root)
    line.append(
        f" | {report.metadata.source_count} sources"
        f" | {len(report.metadata.completed_engines)}/{len(report.metadata.requested_engines)}"
        " engines completed"
    )
    return line


def _engine_line(run: EngineRun) -> Text:
    line = Text("  ")
    line.append(run.engine)
    line.append(" | ")
    line.append(run.state.value.upper())
    if run.version:
        line.append(" | version ")
        line.append(run.version)
    if run.failure is not None:
        requirement = "required" if run.failure.required else "optional"
        line.append(f" | {requirement} | ")
        line.append(run.failure.kind)
        line.append(": ")
        line.append(run.failure.message)
    return line


def _render_finding(finding: Finding, console: Console) -> None:
    header = Text("  ")
    header.append(finding.severity.value.upper(), style=_SEVERITY_STYLES[finding.severity])
    header.append(" | NEW | ")
    header.append(finding.canonical_rule)
    header.append(" | ")
    header.append(f"{finding.location.path}:{finding.location.line}:{finding.location.column}")
    console.print(header)

    title = Text("    ")
    title.append(finding.title)
    if finding.message:
        title.append(": ")
        title.append(finding.message)
    console.print(title)


def _render_unexplained(finding: Finding, console: Console) -> None:
    header = Text("  ")
    header.append(finding.canonical_rule)
    header.append(" | ")
    header.append(f"{finding.location.path}:{finding.location.line}:{finding.location.column}")
    console.print(header)
    for diagnostic in finding.provenance:
        detail = Text("    ")
        detail.append(diagnostic.engine)
        detail.append("/")
        detail.append(diagnostic.original_code)
        detail.append(": ")
        detail.append(diagnostic.message)
        console.print(detail)
