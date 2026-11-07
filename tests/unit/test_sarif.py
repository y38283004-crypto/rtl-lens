"""Schema and repository-boundary tests for Verilator SARIF ingestion."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from rtl_lens.engines.sarif import SarifAdapterError, parse_verilator_sarif
from rtl_lens.models.diagnostic import Severity, SourceLocation

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sarif" / "verilator-width.sarif.json"


def _fixture_payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _prepare_source(root: Path) -> None:
    source = root / "rtl" / "top.sv"
    source.parent.mkdir()
    source.write_text("module top; endmodule\n", encoding="utf-8")


def test_parse_verilator_width_sarif(tmp_path: Path) -> None:
    """Dropping Verilator's result conversion must lose its native WIDTH finding."""
    _prepare_source(tmp_path)

    diagnostics = parse_verilator_sarif(_fixture_payload(), tmp_path)

    assert len(diagnostics) == 1
    assert diagnostics[0].engine == "verilator"
    assert diagnostics[0].engine_version == "5.040"
    assert diagnostics[0].original_code == "WIDTHTRUNC"
    assert diagnostics[0].severity is Severity.WARNING
    assert diagnostics[0].location == SourceLocation(path="rtl/top.sv", line=8, column=5)
    assert diagnostics[0].message.startswith("Operator ASSIGN expects 4 bits")


@pytest.mark.parametrize(
    ("mutate", "missing_field"),
    [
        (lambda payload: payload.pop("version"), "version"),
        (lambda payload: payload.pop("runs"), "runs"),
        (lambda payload: payload["runs"][0].pop("tool"), "tool"),
        (lambda payload: payload["runs"][0]["tool"].pop("driver"), "driver"),
        (lambda payload: payload["runs"][0]["tool"]["driver"].pop("version"), "version"),
        (lambda payload: payload["runs"][0].pop("results"), "results"),
        (lambda payload: payload["runs"][0]["results"][0].pop("level"), "level"),
        (lambda payload: payload["runs"][0]["results"][0].pop("message"), "message"),
        (lambda payload: payload["runs"][0]["results"][0].pop("locations"), "locations"),
    ],
)
def test_parse_rejects_missing_required_sarif_fields(
    tmp_path: Path,
    mutate: Any,
    missing_field: str,
) -> None:
    """Treating missing producer fields as defaults must not invent diagnostics."""
    payload = _fixture_payload()
    mutate(payload)

    with pytest.raises(SarifAdapterError, match=missing_field) as captured:
        parse_verilator_sarif(payload, tmp_path)

    assert captured.value.kind == "malformed_sarif"


@pytest.mark.parametrize(
    "value",
    [None, [], {"version": "2.1.0", "runs": "not-a-list"}],
)
def test_parse_rejects_wrong_typed_sarif_payloads(tmp_path: Path, value: object) -> None:
    """Removing container type checks must expose parser exceptions or silent empties."""
    with pytest.raises(SarifAdapterError) as captured:
        parse_verilator_sarif(value, tmp_path)  # type: ignore[arg-type]

    assert captured.value.kind == "malformed_sarif"


def test_parse_keeps_rule_diagnostic_when_verilator_appends_exit_summary(tmp_path: Path) -> None:
    """Verilator 5.040 emits an unlocated, unnamed fatal summary after warnings."""
    payload = _fixture_payload()
    payload["runs"][0]["results"].append(
        {"level": "error", "message": {"text": "Exiting due to 1 warning(s)"}}
    )

    diagnostics = parse_verilator_sarif(payload, tmp_path)

    assert len(diagnostics) == 1
    assert diagnostics[0].original_code == "WIDTHTRUNC"
    assert diagnostics[0].severity is Severity.WARNING


def test_parse_ignores_unlocated_information_without_inventing_a_source(tmp_path: Path) -> None:
    payload = _fixture_payload()
    payload["runs"][0]["results"] = [{"level": "none", "message": {"text": "Verilation completed"}}]

    assert parse_verilator_sarif(payload, tmp_path) == ()


def test_parse_preserves_unnamed_located_syntax_error(tmp_path: Path) -> None:
    payload = _fixture_payload()
    result = payload["runs"][0]["results"][0]
    result.pop("ruleId")
    result["level"] = "error"
    result["message"]["text"] = "syntax error, unexpected endmodule"

    diagnostics = parse_verilator_sarif(payload, tmp_path)

    assert len(diagnostics) == 1
    assert diagnostics[0].original_code == "UNNAMED"
    assert diagnostics[0].severity is Severity.ERROR
    assert diagnostics[0].location == SourceLocation(path="rtl/top.sv", line=8, column=5)
    assert diagnostics[0].message == "syntax error, unexpected endmodule"


@pytest.mark.parametrize(
    "message",
    ["Cannot open input file", "Exiting due to 1 error(s)", "Exiting due to 2 warning(s)"],
)
def test_parse_does_not_hide_unlocated_errors_or_unexplained_exit_counts(
    tmp_path: Path, message: str
) -> None:
    payload = _fixture_payload()
    payload["runs"][0]["results"].append({"level": "error", "message": {"text": message}})

    with pytest.raises(SarifAdapterError) as captured:
        parse_verilator_sarif(payload, tmp_path)

    assert captured.value.kind == "unlocated_diagnostic"


def test_parse_rejects_empty_rule_id_instead_of_treating_it_as_unnamed(tmp_path: Path) -> None:
    payload = _fixture_payload()
    payload["runs"][0]["results"][0]["ruleId"] = ""

    with pytest.raises(SarifAdapterError, match="ruleId"):
        parse_verilator_sarif(payload, tmp_path)


@pytest.mark.parametrize("locations", [None, 0, "", {}])
def test_parse_validates_optional_locations_even_on_information(
    tmp_path: Path, locations: object
) -> None:
    payload = _fixture_payload()
    payload["runs"][0]["results"] = [
        {"level": "none", "message": {"text": "Information"}, "locations": locations}
    ]

    with pytest.raises(SarifAdapterError, match="locations"):
        parse_verilator_sarif(payload, tmp_path)


def test_parse_accepts_exit_summary_with_matching_error_and_warning_counts(tmp_path: Path) -> None:
    payload = _fixture_payload()
    results = payload["runs"][0]["results"]
    error = deepcopy(results[0])
    error["ruleId"] = "ASSIGNIN"
    error["level"] = "error"
    results.extend(
        [error, {"level": "error", "message": {"text": "Exiting due to 1 error(s), 1 warning(s)"}}]
    )

    diagnostics = parse_verilator_sarif(payload, tmp_path)

    assert [item.original_code for item in diagnostics] == ["WIDTHTRUNC", "ASSIGNIN"]
    assert [item.severity for item in diagnostics] == [Severity.WARNING, Severity.ERROR]


@pytest.mark.parametrize(
    "uri",
    [
        "../outside.sv",
        "%2e%2e/outside.sv",
        "/outside.sv",
        "C:/outside.sv",
        "file:///outside.sv",
        "file:///C:/outside.sv",
        "https://example.invalid/top.sv",
    ],
)
def test_parse_rejects_uri_paths_that_escape_project_root(tmp_path: Path, uri: str) -> None:
    """Normalizing before confinement checks must allow an attacker-controlled path escape."""
    payload = _fixture_payload()
    payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
        "uri"
    ] = uri

    with pytest.raises(SarifAdapterError, match="project root") as captured:
        parse_verilator_sarif(payload, tmp_path)

    assert captured.value.kind == "path_escape"


def test_parse_rejects_symlinked_uri_that_escapes_root(tmp_path: Path) -> None:
    """A lexical in-root path must not conceal a symlink to a file outside the repository."""
    outside = tmp_path.parent / "outside.sv"
    outside.write_text("module outside; endmodule\n", encoding="utf-8")
    link = tmp_path / "rtl" / "top.sv"
    link.parent.mkdir()
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(SarifAdapterError, match="project root") as captured:
        parse_verilator_sarif(_fixture_payload(), tmp_path)

    assert captured.value.kind == "path_escape"


def test_parse_accepts_absolute_and_file_uris_only_when_inside_root(tmp_path: Path) -> None:
    """Rejecting all absolute forms would discard valid Verilator output under the project."""
    _prepare_source(tmp_path)
    expected = SourceLocation(path="rtl/top.sv", line=8, column=5)

    for uri in ((tmp_path / "rtl" / "top.sv").as_uri(), str(tmp_path / "rtl" / "top.sv")):
        payload = deepcopy(_fixture_payload())
        payload["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"][
            "uri"
        ] = uri
        assert parse_verilator_sarif(payload, tmp_path)[0].location == expected
