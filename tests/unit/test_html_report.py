"""Behavior and security tests for self-contained HTML reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from rtl_lens.knowledge.schema import LocalizedExplanation
from rtl_lens.models.analysis import ModuleGraph, TrendSummary
from rtl_lens.models.diagnostic import BaselineState
from rtl_lens.models.report import ScanReport, ScanState
from rtl_lens.renderers import html_report
from rtl_lens.renderers.html_report import write_html_report

FIXTURE = Path(__file__).parents[1] / "fixtures" / "reports" / "partial-report.json"
REPRESENTATIVE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "reports" / "representative.json"


def _sample_report() -> ScanReport:
    return ScanReport.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _representative_report() -> ScanReport:
    return ScanReport.model_validate_json(REPRESENTATIVE_FIXTURE.read_text(encoding="utf-8"))


def _known_no_baseline_report() -> ScanReport:
    report = _sample_report()
    return report.model_copy(
        update={
            "trends": TrendSummary(
                new=tuple(
                    finding.fingerprint
                    for finding in report.findings
                    if finding.baseline_state is BaselineState.NEW
                ),
                unchanged=tuple(
                    finding.fingerprint
                    for finding in report.findings
                    if finding.baseline_state is BaselineState.EXISTING
                ),
                baseline_configuration_known=True,
                baseline_configured=False,
            )
        }
    )


def _incomplete_comparison_report() -> ScanReport:
    report = _representative_report()
    return report.model_copy(
        update={
            "trends": TrendSummary(
                new=report.trends.new,
                unchanged=report.trends.unchanged,
                baseline_configuration_known=True,
                baseline_configured=True,
                comparison_complete=False,
            )
        }
    )


def test_html_report_renders_capped_analysis_views_and_complete_escaped_data(
    tmp_path: Path,
) -> None:
    report = _representative_report()
    destination = tmp_path / "report.html"

    write_html_report(report, destination, graph_display_limit=2)

    html = destination.read_text(encoding="utf-8")
    document = BeautifulSoup(html, "html.parser")
    warnings = document.select_one("section#analysis-warnings")
    trends = document.select_one("section#baseline-trends")
    relationships = document.select_one("section#module-relationships")
    findings = document.select_one("section#findings")
    assert warnings is not None
    assert trends is not None
    assert relationships is not None
    assert findings is not None
    sections = list(document.main.find_all("section", recursive=False))  # type: ignore[union-attr]
    assert sections.index(warnings) < sections.index(trends) < sections.index(relationships)
    assert sections.index(relationships) < sections.index(findings)

    warning_text = warnings.get_text(" ", strip=True)
    assert "WARNING" in warning_text
    assert '<img id="warning-owned"' in warning_text
    trend_text = trends.get_text(" ", strip=True)
    assert "Baseline configured" in trend_text
    assert "Comparison complete" in trend_text
    assert "2 NEW" in trend_text
    assert "1 UNCHANGED" in trend_text
    assert "1 RESOLVED" in trend_text
    assert "Assignment <strong>width</strong> mismatch" in trend_text
    assert "4444444444444444444444444444444444444444444444444444444444444444" in trend_text
    assert (
        document.select_one("label[for='baseline-filter']").get_text(  # type: ignore[union-attr]
            " ", strip=True
        )
        == "Comparison"
    )
    assert [
        option.get_text(" ", strip=True) for option in document.select("#baseline-filter option")
    ] == ["All comparison states", "New", "Unchanged"]
    assert {row.get("data-baseline") for row in document.select("[data-testid='finding-row']")} == {
        "comparison-new",
        "comparison-unchanged",
    }

    relationship_text = relationships.get_text(" ", strip=True)
    assert "4 nodes" in relationship_text
    assert "3 relationships" in relationship_text
    assert "1 unresolved module" in relationship_text
    assert "Displaying 2 of 3 relationships" in relationship_text
    search = relationships.select_one("input#relationship-search")
    assert search is not None
    assert relationships.select_one("label[for='relationship-search']") is not None
    live_count = relationships.select_one("[data-testid='relationship-visible-count']")
    assert live_count is not None
    assert live_count.get("aria-live") == "polite"
    table = relationships.select_one("table")
    assert table is not None
    assert "Module relationships" in (
        table.caption.get_text(" ", strip=True) if table.caption else ""
    )
    assert [heading.get_text(" ", strip=True) for heading in table.select("thead th")] == [
        "Parent module",
        "Instantiated module",
        "Resolution",
    ]
    rows = table.select("[data-testid='relationship-row']")
    assert len(rows) == 2
    assert all(not row.has_attr("hidden") for row in rows)
    assert [row.get("data-search") for row in rows] == [
        f"{parent} {child}" for parent, child in report.module_graph.edges[:2]
    ]

    assert document.find(id="warning-owned") is None
    assert document.find(id="graph-script-owned") is None
    assert document.find(id="graph-owned") is None
    assert not document.select("[onload], [onerror], [onfocus], [onmouseover], [autofocus]")
    report_data = document.select_one("script#report-data[type='application/json']")
    assert report_data is not None
    payload = json.loads(report_data.string or "")
    assert payload["module_graph"]["edges"] == [list(edge) for edge in report.module_graph.edges]
    assert len(payload["module_graph"]["edges"]) == 3
    assert not document.select("script[src], link[href], img[src], iframe[src], source[src]")
    assert "health score" not in document.get_text(" ", strip=True).lower()
    assert "overall score" not in document.get_text(" ", strip=True).lower()


def test_html_report_marks_legacy_baseline_configuration_status_unknown(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.html"

    write_html_report(_sample_report(), destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    summary = document.select_one("[data-testid='summary']")
    trends = document.select_one("[data-testid='baseline-trends']")
    assert summary is not None
    assert trends is not None
    summary_text = summary.get_text(" ", strip=True)
    trend_text = trends.get_text(" ", strip=True)
    assert "3 current / status unknown" in summary_text.lower()
    assert "Legacy baseline configuration status" in summary_text
    assert "Resolution unavailable" in summary_text
    assert "Baseline configuration status unknown" in trend_text
    assert "3 CURRENT / STATUS UNKNOWN" in trend_text
    assert "No baseline configured" not in trend_text
    assert "Not in baseline" not in summary_text
    assert "No longer present" not in summary_text
    findings = document.select_one("section#findings")
    assert findings is not None
    assert [
        option.get_text(" ", strip=True) for option in findings.select("#baseline-filter option")
    ] == ["All comparison states", "Current / Status Unknown"]
    assert {row.get("data-baseline") for row in findings.select("[data-testid='finding-row']")} == {
        "comparison-status-unknown"
    }
    finding_text = findings.get_text(" ", strip=True)
    assert "CURRENT / STATUS UNKNOWN" in finding_text
    assert "NEW" not in finding_text
    assert "EXISTING" not in finding_text


def test_html_report_marks_known_no_baseline_findings_current_and_uncompared(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.html"

    write_html_report(_known_no_baseline_report(), destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    summary = document.select_one("[data-testid='summary']")
    trends = document.select_one("[data-testid='baseline-trends']")
    findings = document.select_one("section#findings")
    assert summary is not None
    assert trends is not None
    assert findings is not None
    assert "3 current / uncompared" in summary.get_text(" ", strip=True).lower()
    assert "No baseline configured" in trends.get_text(" ", strip=True)
    assert [
        option.get_text(" ", strip=True) for option in findings.select("#baseline-filter option")
    ] == ["All comparison states", "Current / Uncompared"]
    assert {row.get("data-baseline") for row in findings.select("[data-testid='finding-row']")} == {
        "comparison-uncompared"
    }
    finding_text = findings.get_text(" ", strip=True)
    assert "CURRENT / UNCOMPARED" in finding_text
    assert "NEW" not in finding_text
    assert "EXISTING" not in finding_text


def test_html_report_withholds_resolution_when_comparison_is_incomplete(
    tmp_path: Path,
) -> None:
    report = _incomplete_comparison_report()
    destination = tmp_path / "report.html"

    write_html_report(report, destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    summary = document.select_one("[data-testid='summary']")
    trends = document.select_one("[data-testid='baseline-trends']")
    assert summary is not None
    assert trends is not None
    summary_text = summary.get_text(" ", strip=True)
    trend_text = trends.get_text(" ", strip=True)
    assert "2 current / unmatched" in summary_text.lower()
    assert "1 current / matched" in summary_text.lower()
    assert "Resolution unavailable" in summary_text
    assert "Comparison unavailable or incomplete" in trend_text
    assert "2 CURRENT / UNMATCHED" in trend_text
    assert "1 CURRENT / MATCHED" in trend_text
    assert "Resolution unavailable" in trend_text
    assert "No longer present" not in summary_text
    assert "no longer present in this scan" not in trend_text
    findings = document.select_one("section#findings")
    assert findings is not None
    assert [
        option.get_text(" ", strip=True) for option in findings.select("#baseline-filter option")
    ] == ["All comparison states", "Current / Unmatched", "Current / Matched"]
    assert {row.get("data-baseline") for row in findings.select("[data-testid='finding-row']")} == {
        "comparison-unmatched",
        "comparison-matched",
    }
    finding_text = findings.get_text(" ", strip=True)
    assert "CURRENT / UNMATCHED" in finding_text
    assert "CURRENT / MATCHED" in finding_text
    assert "NEW" not in finding_text
    assert "EXISTING" not in finding_text


def test_html_report_does_not_claim_a_malformed_baseline_was_compared(
    tmp_path: Path,
) -> None:
    source = _representative_report()
    report = source.model_copy(
        update={
            "metadata": source.metadata.model_copy(
                update={"scan_state": ScanState.FAILED, "completed_engines": ()}
            ),
            "findings": (),
            "engine_runs": (),
            "resolved_fingerprints": (),
            "trends": TrendSummary(
                baseline_configuration_known=True,
                baseline_configured=True,
                comparison_complete=False,
            ),
        }
    )
    destination = tmp_path / "report.html"

    write_html_report(report, destination)

    text = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser").get_text(
        " ", strip=True
    )
    assert "Comparison unavailable or incomplete" in text
    assert "Resolution unavailable" in text
    assert "Current findings are compared with the configured baseline" not in text
    assert "Comparison complete" not in text


def test_html_report_two_argument_call_defaults_to_200_relationship_rows(
    tmp_path: Path,
) -> None:
    edges = tuple((f"parent-{index:03d}", f"child-{index:03d}") for index in range(201))
    nodes = tuple(sorted({name for edge in edges for name in edge}))
    report = _representative_report().model_copy(
        update={"module_graph": ModuleGraph(nodes=nodes, edges=edges)}
    )
    destination = tmp_path / "report.html"

    write_html_report(report, destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    assert len(document.select("[data-testid='relationship-row']")) == 200
    relationships = document.select_one("section#module-relationships")
    assert relationships is not None
    assert "Displaying 200 of 201 relationships" in relationships.get_text(" ", strip=True)
    assert all(
        not row.has_attr("hidden") for row in document.select("[data-testid='relationship-row']")
    )


@pytest.mark.parametrize("limit", [0, 2001])
def test_html_report_rejects_display_limits_outside_documented_bounds(
    limit: int,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="graph_display_limit must be between 1 and 2000"):
        write_html_report(
            _representative_report(),
            tmp_path / "report.html",
            graph_display_limit=limit,
        )


def test_html_report_renders_explicit_no_relationships_state(tmp_path: Path) -> None:
    destination = tmp_path / "report.html"

    write_html_report(_sample_report(), destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    relationships = document.select_one("section#module-relationships")
    assert relationships is not None
    assert "No module relationships were extracted." in relationships.get_text(" ", strip=True)
    assert relationships.select_one("table") is None
    assert relationships.select_one("#relationship-search") is None


def test_html_report_exposes_complete_readable_structure_without_a_score(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.html"

    write_html_report(_sample_report(), destination)

    html = destination.read_text(encoding="utf-8")
    document = BeautifulSoup(html, "html.parser")
    assert document.main is not None
    assert document.select_one("[data-testid='summary']") is not None
    assert document.select_one("[data-testid='engine-status']") is not None
    assert len(document.select("[data-testid='finding-row']")) == 3
    assert document.select_one("label[for='severity-filter']") is not None
    assert document.select_one("label[for='baseline-filter']") is not None
    assert document.select_one("label[for='engine-filter']") is not None
    visible_count = document.select_one("[data-testid='visible-count']")
    assert visible_count is not None
    assert visible_count.get("aria-live") == "polite"
    text = document.get_text(" ", strip=True)
    assert "PARTIAL" in text
    assert "3 findings" in text
    assert "1 error" in text
    assert "1 warning" in text
    assert "1 info" in text
    assert "3 current / status unknown" in text.lower()
    assert "Resolution unavailable" in text
    assert "FAILED" in text
    assert "No curated explanation" in text
    english = document.select_one("[data-testid='explanation-en']")
    chinese = document.select_one("[data-testid='explanation-zh-cn']")
    assert english is not None
    assert english.get("lang") == "en"
    assert "English" in english.get_text(" ", strip=True)
    assert "Assignment width mismatch" in english.get_text(" ", strip=True)
    assert "The source and destination widths differ" in english.get_text(" ", strip=True)
    assert "Silent truncation can change numeric results" in english.get_text(" ", strip=True)
    assert "Make both widths agree" in english.get_text(" ", strip=True)
    assert chinese is not None
    assert chinese.get("lang") == "zh-CN"
    assert "简体中文" in chinese.get_text(" ", strip=True)
    assert "赋值两侧位宽不一致" in chinese.get_text(" ", strip=True)
    assert "源信号与目标信号位宽不同" in chinese.get_text(" ", strip=True)
    assert "静默截断可能改变数值结果" in chinese.get_text(" ", strip=True)
    assert "统一两侧位宽" in chinese.get_text(" ", strip=True)
    assert "health score" not in text.lower()
    assert "overall score" not in text.lower()


def test_html_report_loads_knowledge_once_and_escapes_hostile_explanations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.html"
    hostile = LocalizedExplanation(
        title='<img id="explanation-owned" src=x onerror="window.__explanationOwned=1">',
        cause='</script><script id="explanation-script">window.__explanationOwned=1</script>',
        risk='<a id="explanation-link" href="https://example.invalid">risk</a>',
        fix='<svg id="explanation-svg" onload="window.__explanationOwned=1"></svg>',
    )

    class FakeStore:
        def get(self, rule_id: str, language: str) -> LocalizedExplanation | None:
            if rule_id == "width-mismatch" and language in {"en", "zh-CN"}:
                return hostile
            return None

    load_calls = 0

    def load_default() -> FakeStore:
        nonlocal load_calls
        load_calls += 1
        return FakeStore()

    monkeypatch.setattr(html_report.KnowledgeStore, "load_default", load_default)

    write_html_report(_sample_report(), destination)

    assert load_calls == 1
    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    assert document.find(id="explanation-owned") is None
    assert document.find(id="explanation-script") is None
    assert document.find(id="explanation-link") is None
    assert document.find(id="explanation-svg") is None
    explanation = document.select_one("[data-testid='explanation-en']")
    assert explanation is not None
    text = explanation.get_text(" ", strip=True)
    assert '<img id="explanation-owned"' in text
    assert '</script><script id="explanation-script">' in text
    assert '<a id="explanation-link"' in text
    assert '<svg id="explanation-svg"' in text


def test_html_report_handles_knowledge_lookup_failure_without_crashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.html"

    class FailingStore:
        def get(self, rule_id: str, language: str) -> None:
            del rule_id, language
            raise LookupError("broken knowledge index")

    monkeypatch.setattr(html_report.KnowledgeStore, "load_default", lambda: FailingStore())

    write_html_report(_sample_report(), destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    assert len(document.select(".explanation-state")) == len(_sample_report().findings)
    assert all(
        item.get_text(" ", strip=True) == "No curated explanation"
        for item in document.select(".explanation-state")
    )


def test_html_report_aria_labelledby_targets_use_safe_existing_ids(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.html"

    write_html_report(_incomplete_comparison_report(), destination)

    document = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    ids = {str(item["id"]) for item in document.select("[id]")}
    assert all(" " not in item_id and "/" not in item_id for item_id in ids)
    for labelled in document.select("[aria-labelledby]"):
        referenced = str(labelled["aria-labelledby"]).split()
        assert referenced
        assert all(token in ids for token in referenced)


def test_html_report_is_self_contained_and_escapes_every_untrusted_context(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.html"

    write_html_report(_sample_report(), destination)

    html = destination.read_text(encoding="utf-8")
    document = BeautifulSoup(html, "html.parser")
    assert not document.select("script[src], link[href], img[src], iframe[src], source[src]")
    assert document.find(id="owned") is None
    assert document.find(id="failure-owned") is None
    assert document.find(id="version-owned") is None
    assert not document.select("[onload], [onerror], [onfocus], [onmouseover], [autofocus]")
    text = document.get_text(" ", strip=True)
    assert "<strong>width</strong>" in text
    assert '</script><script id="owned">window.__owned=1</script>' in text
    assert "&lt;em&gt;" in text
    assert "<always_comb> a = b & c; </always_comb>" in text
    assert "<valid-looking>tag</valid-looking>" in text
    report_data = document.select_one("script#report-data[type='application/json']")
    assert report_data is not None
    payload = json.loads(report_data.string or "")
    assert payload["findings"][0]["message"].startswith("</script><script")
    assert '</script><script id="owned">' not in html
    assert 'window.__attrOwned=1" autofocus' not in html


def test_html_report_atomically_replaces_destination_and_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.html"
    original = b"old report"
    destination.write_bytes(original)

    def fail_replace(source: str | Path, target: str | Path) -> None:
        temporary = Path(source)
        assert temporary.parent == destination.parent
        assert Path(target) == destination
        assert temporary.read_text(encoding="utf-8").startswith("<!doctype html>")
        raise OSError("replace failed")

    monkeypatch.setattr(html_report.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_html_report(_sample_report(), destination)

    assert destination.read_bytes() == original
    assert set(tmp_path.iterdir()) == {destination}


@pytest.mark.parametrize("operation", ["write", "fsync"])
def test_html_report_write_failures_preserve_destination_and_clean_temporary_file(
    operation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.html"
    original = b"old report"
    destination.write_bytes(original)

    def fail_operation(*args: object) -> None:
        del args
        raise OSError(f"{operation} failed")

    monkeypatch.setattr(html_report.os, operation, fail_operation)

    with pytest.raises(OSError, match=rf"{operation} failed"):
        write_html_report(_sample_report(), destination)

    assert destination.read_bytes() == original
    assert set(tmp_path.iterdir()) == {destination}


def test_html_report_fsyncs_and_closes_before_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.html"
    events: list[str] = []
    descriptor: int | None = None
    real_write = html_report.os.write
    real_fsync = html_report.os.fsync
    real_close = html_report.os.close
    real_replace = html_report.os.replace

    def observed_write(fd: int, data: bytes | bytearray | memoryview) -> int:
        nonlocal descriptor
        descriptor = fd
        events.append("write")
        return real_write(fd, data)

    def observed_fsync(fd: int) -> None:
        events.append("fsync")
        real_fsync(fd)

    def observed_close(fd: int) -> None:
        events.append("close")
        real_close(fd)

    def observed_replace(source: str | Path, target: str | Path) -> None:
        events.append("replace")
        assert descriptor is not None
        with pytest.raises(OSError):
            html_report.os.fstat(descriptor)
        real_replace(source, target)

    monkeypatch.setattr(html_report.os, "write", observed_write)
    monkeypatch.setattr(html_report.os, "fsync", observed_fsync)
    monkeypatch.setattr(html_report.os, "close", observed_close)
    monkeypatch.setattr(html_report.os, "replace", observed_replace)

    write_html_report(_sample_report(), destination)

    assert events.index("write") < events.index("fsync") < events.index("close")
    assert events.index("close") < events.index("replace")


def test_html_report_uses_unique_same_directory_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.html"
    real_replace = html_report.os.replace
    temporary_paths: list[Path] = []

    def observed_replace(source: str | Path, target: str | Path) -> None:
        temporary_paths.append(Path(source))
        real_replace(source, target)

    monkeypatch.setattr(html_report.os, "replace", observed_replace)

    write_html_report(_sample_report(), destination)
    write_html_report(_sample_report(), destination)

    assert len(set(temporary_paths)) == 2
    assert all(path.parent == destination.parent for path in temporary_paths)
    assert set(tmp_path.iterdir()) == {destination}
