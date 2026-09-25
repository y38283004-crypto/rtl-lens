"""Resolved output, baseline, and atomic-writer path boundaries."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rtl_lens.cli import app
from rtl_lens.models.project import ProjectConfig, ResolvedProject, ScanConfig
from rtl_lens.models.report import ScanMetadata, ScanReport
from rtl_lens.renderers.html_report import write_html_report
from rtl_lens.renderers.json_report import write_json_report
from rtl_lens.security.paths import (
    resolve_baseline_path,
    resolve_output_root,
    resolve_report_destination,
)
from rtl_lens.services.scan import preflight_scan_configuration

runner = CliRunner()


def _report(root: Path) -> ScanReport:
    return ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=str(root),
            started_at=datetime(2026, 8, 29, tzinfo=UTC),
            duration_ms=1,
            requested_engines=(),
            completed_engines=(),
            config_digest="0" * 64,
            redacted=False,
        ),
        findings=(),
    )


def _project(root: Path, output_dir: str = "artifacts") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (root / ".rtl-lens.toml").write_text(
        f'[scan]\nengine_mode = "disabled"\noutput_dir = "{output_dir}"\n',
        encoding="utf-8",
    )


def test_relative_output_root_is_project_confined(tmp_path: Path) -> None:
    assert resolve_output_root(tmp_path, Path("artifacts")) == (tmp_path / "artifacts").resolve()

    with pytest.raises(ValueError, match="output root"):
        resolve_output_root(tmp_path, Path("../outside"))


def test_absolute_output_root_is_explicitly_allowed(tmp_path: Path) -> None:
    outside = (tmp_path.parent / "explicit-output").resolve()

    assert resolve_output_root(tmp_path, outside) == outside


def test_relative_report_override_is_beneath_configured_output_root(tmp_path: Path) -> None:
    destination = resolve_report_destination(
        tmp_path,
        Path("artifacts"),
        Path("nested/report.json"),
        "report.json",
    )

    assert destination == (tmp_path / "artifacts" / "nested" / "report.json").resolve()


def test_default_report_destination_is_beneath_configured_output_root(tmp_path: Path) -> None:
    assert (
        resolve_report_destination(tmp_path, Path("artifacts"), None, "report.json")
        == (tmp_path / "artifacts" / "report.json").resolve()
    )


@pytest.mark.parametrize(
    "override",
    [
        Path("../escape.json"),
        Path("nested/../../escape.json"),
        Path("../artifacts-sibling/report.json"),
    ],
)
def test_relative_report_override_cannot_escape_output_root(tmp_path: Path, override: Path) -> None:
    with pytest.raises(ValueError, match="report destination"):
        resolve_report_destination(tmp_path, Path("artifacts"), override, "report.json")


def test_absolute_report_override_is_explicitly_allowed(tmp_path: Path) -> None:
    destination = (tmp_path.parent / "explicit-report.json").resolve()

    assert (
        resolve_report_destination(tmp_path, Path("artifacts"), destination, "report.json")
        == destination
    )


def test_resolver_refuses_leaf_symlink_before_dereferencing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    leaf = tmp_path / "artifacts" / "report.json"
    original_is_symlink = Path.is_symlink

    def simulated_leaf_symlink(path: Path) -> bool:
        return path == leaf or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", simulated_leaf_symlink)

    with pytest.raises(ValueError, match="symlink"):
        resolve_report_destination(tmp_path, Path("artifacts"), None, "report.json")


def test_relative_baseline_is_beneath_configured_output_root(tmp_path: Path) -> None:
    assert (
        resolve_baseline_path(tmp_path, Path("artifacts"), Path("baseline.json"))
        == (tmp_path / "artifacts" / "baseline.json").resolve()
    )

    with pytest.raises(ValueError, match="baseline"):
        resolve_baseline_path(tmp_path, Path("artifacts"), Path("../baseline.json"))


def test_absolute_baseline_is_explicitly_allowed(tmp_path: Path) -> None:
    baseline = (tmp_path.parent / "explicit-baseline.json").resolve()

    assert resolve_baseline_path(tmp_path, Path("artifacts"), baseline) == baseline


def test_cli_relative_overrides_are_written_beneath_output_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _project(project)

    result = runner.invoke(
        app,
        [
            "scan",
            str(project),
            "--json",
            "nested/custom.json",
            "--html",
            "nested/custom.html",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (project / "artifacts" / "nested" / "custom.json").is_file()
    assert (project / "artifacts" / "nested" / "custom.html").is_file()
    assert not (project / "nested").exists()


def test_cli_rejects_relative_destination_and_output_root_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _project(project)

    destination_escape = runner.invoke(
        app,
        ["scan", str(project), "--json", "../escaped.json"],
    )

    assert destination_escape.exit_code == 3
    assert "report destination" in destination_escape.stdout
    assert not (project / "escaped.json").exists()

    _project(project, "../outside")
    output_escape = runner.invoke(app, ["scan", str(project)])

    assert output_escape.exit_code == 3
    assert "output root" in output_escape.stdout
    assert not (tmp_path / "outside").exists()


def test_cli_allows_explicit_absolute_report_destinations(tmp_path: Path) -> None:
    project = tmp_path / "project"
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    _project(project)

    result = runner.invoke(
        app,
        [
            "scan",
            str(project),
            "--json",
            str(explicit / "report.json"),
            "--html",
            str(explicit / "report.html"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert (explicit / "report.json").is_file()
    assert (explicit / "report.html").is_file()


def test_cli_refuses_existing_leaf_symlink_without_overwriting_target(tmp_path: Path) -> None:
    project = tmp_path / "project"
    output = project / "artifacts"
    _project(project)
    output.mkdir()
    target = output / "target.json"
    target.write_text("do not replace\n", encoding="utf-8")
    destination = output / "report.json"
    try:
        destination.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    result = runner.invoke(app, ["scan", str(project)])

    assert result.exit_code == 3
    assert "symlink" in result.stdout
    assert destination.is_symlink()
    assert target.read_text(encoding="utf-8") == "do not replace\n"


def test_scan_preflight_loads_relative_baseline_from_output_root(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    output.mkdir()
    write_json_report(_report(tmp_path), output / "baseline.json")
    project = ResolvedProject(root=tmp_path, sources=())
    config = ProjectConfig(
        scan=ScanConfig(output_dir=Path("artifacts"), baseline_path=Path("baseline.json"))
    )

    loaded = preflight_scan_configuration(project, config)

    assert loaded == _report(tmp_path)


def test_symlinked_output_parent_cannot_escape_boundary(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    outside = tmp_path.parent / "outside-output"
    output.mkdir()
    outside.mkdir(exist_ok=True)
    link = output / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    with pytest.raises(ValueError, match="report destination"):
        resolve_report_destination(
            tmp_path,
            Path("artifacts"),
            Path("linked/report.json"),
            "report.json",
        )


def test_symlinked_relative_output_root_cannot_escape_project(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-root"
    outside.mkdir(exist_ok=True)
    output = tmp_path / "artifacts"
    try:
        output.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    with pytest.raises(ValueError, match="output root"):
        resolve_output_root(tmp_path, Path("artifacts"))


def test_relative_baseline_cannot_escape_through_symlinked_parent(tmp_path: Path) -> None:
    output = tmp_path / "artifacts"
    outside = tmp_path.parent / "outside-baseline"
    output.mkdir()
    outside.mkdir(exist_ok=True)
    link = output / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    with pytest.raises(ValueError, match="baseline"):
        resolve_baseline_path(tmp_path, Path("artifacts"), Path("linked/baseline.json"))


@pytest.mark.parametrize("writer", [write_json_report, write_html_report])
def test_atomic_writer_refuses_existing_symlink_destination(
    tmp_path: Path,
    writer: Callable[[ScanReport, Path], None],
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("do not replace\n", encoding="utf-8")
    destination = tmp_path / "report.out"
    try:
        destination.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    with pytest.raises(ValueError, match="symlink"):
        writer(_report(tmp_path), destination)

    assert destination.is_symlink()
    assert target.read_text(encoding="utf-8") == "do not replace\n"
