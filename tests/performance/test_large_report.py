"""Secure rendering ceilings for the largest supported report fixture."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from bs4 import BeautifulSoup

from rtl_lens.models.analysis import ModuleGraph
from rtl_lens.models.diagnostic import Finding, RawDiagnostic, Severity, SourceLocation
from rtl_lens.models.report import ScanMetadata, ScanReport
from rtl_lens.renderers.html_report import write_html_report
from rtl_lens.renderers.json_report import write_json_report
from rtl_lens.security.redaction import RedactionPolicy

_FINDING_LIMIT = 500
_RENDER_LIMIT_SECONDS = 5.0
_HOME = Path(r"C:\Users\PerformanceAlice")
_PROJECT = r"C:\Users\PerformanceAlice\private-chip"
_PRIVATE_PREFIX = Path(r"D:\customer-ip\confidential")
_SECRET = "LARGE-REPORT-SECRET-CANARY"
_HOSTILE = '<img id="performance-owned" src=x onerror="window.__owned=1">'


def _large_report() -> ScanReport:
    nodes = tuple(f"module_{index:03d}-{_SECRET}" for index in range(_FINDING_LIMIT))
    edges = tuple((nodes[index - 1], nodes[index]) for index in range(1, len(nodes)))
    findings: list[Finding] = []
    severities = tuple(Severity)
    for index in range(_FINDING_LIMIT):
        severity = severities[index % len(severities)]
        location = SourceLocation(
            path=rf"{_PROJECT}\rtl\module_{index:03d}.sv",
            line=index + 1,
            column=1,
        )
        raw = RawDiagnostic(
            engine="verilator" if index % 2 == 0 else "pyslang",
            engine_version=f"tool-{index % 7} from {_PRIVATE_PREFIX}",
            original_code=f"PERF-{index:03d}",
            severity=severity,
            location=location,
            message=f"{_HOSTILE} {_PRIVATE_PREFIX} {_SECRET} diagnostic {index:03d}",
            symbol=f"private_symbol_{index:03d}-{_SECRET}",
            source_snippet=f"assign leaked_{index:03d} = {_SECRET};",
        )
        findings.append(
            Finding(
                fingerprint=f"{index:064x}",
                canonical_rule=f"performance-rule-{index % 11}",
                severity=severity,
                location=location,
                title=f"Private finding {index:03d} {_SECRET}",
                message=raw.message,
                symbol=raw.symbol,
                source_snippet=raw.source_snippet,
                provenance=(raw,),
            )
        )
    return ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=_PROJECT,
            started_at=datetime(2026, 8, 30, tzinfo=UTC),
            duration_ms=1000,
            requested_engines=("pyslang", "verilator"),
            completed_engines=("pyslang", "verilator"),
            config_digest="f" * 64,
            redacted=False,
            source_count=_FINDING_LIMIT,
        ),
        findings=tuple(findings),
        module_graph=ModuleGraph(nodes=nodes, edges=edges),
    )


def test_shareable_large_report_stays_bounded_private_and_offline(tmp_path: Path) -> None:
    report = _large_report()
    policy = RedactionPolicy(
        home=_HOME,
        path_prefixes=(_PRIVATE_PREFIX,),
        secret_values=(_SECRET,),
    )
    json_destination = tmp_path / "large-report.json"
    html_destination = tmp_path / "large-report.html"

    json_started = perf_counter()
    write_json_report(report, json_destination, redaction_policy=policy)
    json_elapsed = perf_counter() - json_started

    html_started = perf_counter()
    write_html_report(
        report,
        html_destination,
        graph_display_limit=_FINDING_LIMIT,
        redaction_policy=policy,
    )
    html_elapsed = perf_counter() - html_started

    json_payload = json_destination.read_text(encoding="utf-8")
    html_payload = html_destination.read_text(encoding="utf-8")
    parsed_json = ScanReport.model_validate_json(json_payload)
    document = BeautifulSoup(html_payload, "html.parser")
    report_data = document.select_one("script#report-data[type='application/json']")
    assert report_data is not None
    embedded_report = ScanReport.model_validate(json.loads(report_data.string or ""))

    assert len(parsed_json.findings) == _FINDING_LIMIT
    assert len(embedded_report.findings) == _FINDING_LIMIT
    assert len(parsed_json.module_graph.edges) == _FINDING_LIMIT - 1
    assert len(document.select("[data-testid='finding-row']")) == _FINDING_LIMIT
    assert json_elapsed < _RENDER_LIMIT_SECONDS
    assert html_elapsed < _RENDER_LIMIT_SECONDS

    for payload in (json_payload, html_payload):
        folded = payload.replace("\\\\", "\\").casefold()
        assert str(_HOME).casefold() not in folded
        assert _PROJECT.casefold() not in folded
        assert str(_PRIVATE_PREFIX).casefold() not in folded
        assert _SECRET.casefold() not in folded
        assert "assign leaked_" not in payload

    assert parsed_json.metadata.redacted is True
    assert embedded_report.metadata.redacted is True
    assert document.find(id="performance-owned") is None
    assert not document.select("[onload], [onerror], [onfocus], [onmouseover], [autofocus]")
    assert not document.select("script[src], link[href], img[src], iframe[src], source[src]")
    assert "http://" not in html_payload.casefold()
    assert "https://" not in html_payload.casefold()
    csp = document.select_one("meta[http-equiv='Content-Security-Policy']")
    assert csp is not None
    assert "connect-src 'none'" in str(csp.get("content"))
