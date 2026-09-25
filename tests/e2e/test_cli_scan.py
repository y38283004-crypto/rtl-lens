"""End-to-end CLI composition over the real scan service and renderers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from typer.testing import CliRunner

from rtl_lens.cli import app
from rtl_lens.models.diagnostic import RawDiagnostic, Severity, SourceLocation
from rtl_lens.models.engine import EngineRequest, EngineRun, EngineState

runner = CliRunner()


@dataclass(frozen=True)
class FixedEngine:
    name: str
    diagnostics: tuple[RawDiagnostic, ...] = ()
    is_available: bool = True

    def available(self) -> bool:
        return self.is_available

    def version(self) -> str:
        return "test"

    def run(self, request: EngineRequest) -> EngineRun:
        del request
        return EngineRun(
            engine=self.name,
            state=EngineState.COMPLETED,
            version="test",
            diagnostics=self.diagnostics,
        )


def _project(
    tmp_path: Path,
    *,
    engine_mode: str = "disabled",
    graph_display_limit: int = 200,
) -> None:
    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / ".rtl-lens.toml").write_text(
        f'[scan]\nengine_mode = "{engine_mode}"\ngraph_display_limit = {graph_display_limit}\n',
        encoding="utf-8",
    )


def test_scan_writes_terminal_json_and_self_contained_html(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    _project(tmp_path)
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: FixedEngine("pyslang"))

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "RTL Lens scan report" in result.stdout
    assert "JSON report:" in result.stdout
    assert "HTML report:" in result.stdout
    payload = json.loads((tmp_path / ".rtl-lens" / "report.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source_count"] == 1
    html = (tmp_path / ".rtl-lens" / "report.html").read_text(encoding="utf-8")
    assert "RTL Lens" in html
    assert "https://" not in html


def test_scan_runs_the_real_pyslang_adapter(tmp_path: Path) -> None:
    _project(tmp_path)

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    payload = json.loads((tmp_path / ".rtl-lens" / "report.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["completed_engines"] == ["pyslang"]


def test_scan_fail_on_warning_overrides_only_policy_exit(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    _project(tmp_path)
    diagnostic = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=1, column=8),
        message="unused",
    )
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: FixedEngine("pyslang", (diagnostic,)))

    result = runner.invoke(app, ["scan", str(tmp_path), "--fail-on", "warning"])

    assert result.exit_code == 1
    assert "WARNING" in result.stdout


def test_optional_partial_scan_warns_but_preserves_policy_exit(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    _project(tmp_path, engine_mode="auto")
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: FixedEngine("pyslang"))
    monkeypatch.setattr(
        cli, "VerilatorEngine", lambda: FixedEngine("verilator", is_available=False)
    )

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "PARTIAL" in result.stdout
    assert "completeness" in result.stdout


def test_report_failure_is_runtime_exit_without_false_success(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    _project(tmp_path, graph_display_limit=17)
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: FixedEngine("pyslang"))

    def reject_html(report, destination: Path, *, graph_display_limit: int) -> None:
        del report, destination
        assert graph_display_limit == 17
        raise OSError("disk full")

    monkeypatch.setattr(cli, "write_html_report", reject_html)
    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 2
    assert "disk full" in result.stdout
    assert "HTML report:" not in result.stdout
    assert "Traceback" not in result.stdout


def test_scan_rejects_colliding_report_destinations_before_writing(
    tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    _project(tmp_path)
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: FixedEngine("pyslang"))
    calls: list[str] = []
    monkeypatch.setattr(cli, "write_json_report", lambda report, destination: calls.append("json"))
    monkeypatch.setattr(cli, "write_html_report", lambda report, destination: calls.append("html"))

    result = runner.invoke(
        app,
        ["scan", str(tmp_path), "--json", "same.out", "--html", "same.out"],
    )

    assert result.exit_code == 3
    assert "JSON and HTML" in result.stdout
    assert "destinations" in result.stdout
    assert calls == []


def test_scan_shareable_reports_apply_configured_paths_and_named_environment_secrets(
    tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    secret = "CLI-SECRET-123"
    private_path = tmp_path / "private" / "generated.sv"
    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / ".rtl-lens.toml").write_text(
        """[scan]
engine_mode = "disabled"
redact_sources = true
redact_path_prefixes = ["private"]
redact_environment_variables = ["RTL_LENS_TEST_SECRET", "RTL_LENS_MISSING_SECRET"]
""",
        encoding="utf-8",
    )
    diagnostic = RawDiagnostic(
        engine="pyslang",
        original_code="unused-variable",
        severity=Severity.WARNING,
        location=SourceLocation(path="private/generated.sv", line=1, column=8),
        message=f"generated below {private_path}; credential={secret}",
        source_snippet=f'localparam string token = "{secret}";',
    )
    monkeypatch.setenv("RTL_LENS_TEST_SECRET", secret)
    monkeypatch.delenv("RTL_LENS_MISSING_SECRET", raising=False)
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: FixedEngine("pyslang", (diagnostic,)))

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    json_payload = (tmp_path / ".rtl-lens" / "report.json").read_text(encoding="utf-8")
    html_payload = (tmp_path / ".rtl-lens" / "report.html").read_text(encoding="utf-8")
    for payload in (json_payload.replace("\\\\", "\\"), html_payload):
        assert str(tmp_path).casefold() not in payload.casefold()
        assert str(private_path).casefold() not in payload.casefold()
        assert secret not in payload
    assert json.loads(json_payload)["metadata"]["redacted"] is True
    assert "RTL_LENS_TEST_SECRET" not in json_payload


def test_scan_rejects_invalid_redaction_environment_name_before_writing(tmp_path: Path) -> None:
    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / ".rtl-lens.toml").write_text(
        """[scan]
engine_mode = "disabled"
redact_sources = true
redact_environment_variables = ["TOKEN-NAME"]
""",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 3
    assert "environment" in result.stdout
    assert not (tmp_path / ".rtl-lens" / "report.json").exists()
    assert not (tmp_path / ".rtl-lens" / "report.html").exists()
