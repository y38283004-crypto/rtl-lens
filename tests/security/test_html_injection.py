"""Shareable JSON/HTML redaction and hostile-markup boundaries."""

from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup

from rtl_lens.models.analysis import AnalysisWarning
from rtl_lens.models.report import ScanReport
from rtl_lens.renderers.html_report import render_shareable_html, write_html_report
from rtl_lens.renderers.json_report import write_json_report
from rtl_lens.security.redaction import RedactionPolicy

from .conftest import CONFIGURED_PREFIX, HOME, HOSTILE, PROJECT, SECRET, UNMARKED


def _assert_shareable_payload(payload: str) -> None:
    folded = payload.replace("\\\\", "\\").casefold()
    assert str(HOME).casefold() not in folded
    assert PROJECT.casefold() not in folded
    assert str(CONFIGURED_PREFIX).casefold() not in folded
    assert SECRET.casefold() not in folded
    assert UNMARKED in payload


def test_shareable_html_redacts_before_visible_and_embedded_rendering(
    hostile_report: ScanReport,
) -> None:
    html = render_shareable_html(
        hostile_report,
        home=HOME,
        path_prefixes=(CONFIGURED_PREFIX,),
        secret_values=(SECRET,),
    )

    _assert_shareable_payload(html)
    document = BeautifulSoup(html, "html.parser")
    assert document.find(id="owned") is None
    assert not document.select("[onload], [onerror], [onfocus], [onmouseover], [autofocus]")
    assert not document.select("script[src], link[href], img[src], iframe[src], source[src]")
    assert HOSTILE in document.get_text(" ", strip=True)
    report_data = document.select_one("script#report-data[type='application/json']")
    assert report_data is not None
    embedded = json.loads(report_data.string or "")
    _assert_shareable_payload(json.dumps(embedded))
    csp = document.select_one("meta[http-equiv='Content-Security-Policy']")
    assert csp is not None
    assert "connect-src 'none'" in str(csp.get("content"))


def test_shareable_json_and_html_writers_use_the_same_policy(
    hostile_report: ScanReport,
    tmp_path: Path,
) -> None:
    policy = RedactionPolicy(
        home=HOME,
        path_prefixes=(CONFIGURED_PREFIX,),
        secret_values=(SECRET,),
    )
    json_destination = tmp_path / "report.json"
    html_destination = tmp_path / "report.html"

    write_json_report(hostile_report, json_destination, redaction_policy=policy)
    write_html_report(hostile_report, html_destination, redaction_policy=policy)

    json_payload = json_destination.read_text(encoding="utf-8")
    html_payload = html_destination.read_text(encoding="utf-8")
    _assert_shareable_payload(json_payload)
    _assert_shareable_payload(html_payload)
    assert json.loads(json_payload)["metadata"]["redacted"] is True


def test_local_writers_preserve_nonshareable_values(
    hostile_report: ScanReport,
    tmp_path: Path,
) -> None:
    json_destination = tmp_path / "local.json"
    html_destination = tmp_path / "local.html"

    write_json_report(hostile_report, json_destination)
    write_html_report(hostile_report, html_destination)

    json_payload = json_destination.read_text(encoding="utf-8")
    html_payload = html_destination.read_text(encoding="utf-8")
    assert json.loads(json_payload)["metadata"]["project_root"] == PROJECT
    assert SECRET in json_payload
    assert PROJECT in html_payload
    assert SECRET in html_payload
    assert hostile_report.findings[0].source_snippet in json_payload
    assert hostile_report.findings[0].source_snippet in html_payload


def test_redacted_report_flag_activates_default_home_and_project_redaction(
    hostile_report: ScanReport,
    tmp_path: Path,
) -> None:
    runtime_home = str(Path.home())
    default_warning = AnalysisWarning(
        kind="default-home",
        message=f"runtime home is {runtime_home}",
    )
    flagged = hostile_report.model_copy(
        update={
            "metadata": hostile_report.metadata.model_copy(update={"redacted": True}),
            "analysis_warnings": hostile_report.analysis_warnings + (default_warning,),
        },
        deep=True,
    )
    destination = tmp_path / "flagged.json"

    write_json_report(flagged, destination)

    payload = destination.read_text(encoding="utf-8")
    assert PROJECT.casefold() not in payload.casefold()
    assert runtime_home.casefold() not in payload.replace("\\\\", "\\").casefold()
    assert flagged.findings[0].source_snippet not in payload
