"""Public scan exit-code precedence and configuration boundaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rtl_lens.cli import app
from rtl_lens.models.engine import EngineRequest, EngineRun, EngineState

runner = CliRunner()


@dataclass(frozen=True)
class Engine:
    name: str
    is_available: bool = True

    def available(self) -> bool:
        return self.is_available

    def version(self) -> str:
        return "test"

    def run(self, request: EngineRequest) -> EngineRun:
        del request
        return EngineRun(engine=self.name, state=EngineState.COMPLETED)


def test_required_engine_missing_is_exit_two(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / ".rtl-lens.toml").write_text('[scan]\nengine_mode = "required"\n', encoding="utf-8")
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: Engine("pyslang"))
    monkeypatch.setattr(cli, "VerilatorEngine", lambda: Engine("verilator", is_available=False))

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 2
    assert "FAILED" in result.stdout


def test_invalid_config_is_exit_three_before_engine_construction(
    tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    (tmp_path / ".rtl-lens.toml").write_text("[scan]\ntimeout = 0\n", encoding="utf-8")

    def forbidden_engine():
        raise AssertionError("engine should not be constructed")

    monkeypatch.setattr(cli, "_pyslang_engine", forbidden_engine)
    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 3
    assert "Invalid project or configuration" in result.stdout
    assert "Traceback" not in result.stdout


def test_custom_config_is_loaded_without_copying_it_into_project(
    tmp_path: Path, monkeypatch
) -> None:
    alternate = tmp_path / "alternate.toml"
    alternate.write_text('[scan]\nengine_mode = "disabled"\n', encoding="utf-8")
    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")

    from rtl_lens import cli

    monkeypatch.setattr(cli, "_pyslang_engine", lambda: Engine("pyslang"))
    result = runner.invoke(app, ["scan", str(tmp_path), "--config", str(alternate)])

    assert result.exit_code == 0
    assert not (tmp_path / ".rtl-lens.toml").exists()
    report = json.loads((tmp_path / ".rtl-lens" / "report.json").read_text(encoding="utf-8"))
    assert report["metadata"]["requested_engines"] == ["pyslang"]


def test_configuration_exit_outprioritizes_report_failure(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / ".rtl-lens.toml").write_text(
        '[scan]\nlanguage = "fr"\nengine_mode = "disabled"\n', encoding="utf-8"
    )
    monkeypatch.setattr(cli, "preflight_scan_configuration", lambda project, config: None)
    monkeypatch.setattr(cli, "_pyslang_engine", lambda: Engine("pyslang"))

    def failed_writer(report, destination: Path) -> None:
        del report, destination
        raise OSError("writer failed")

    monkeypatch.setattr(cli, "write_json_report", failed_writer)
    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 3
    assert "writer failed" in result.stdout
    assert "Traceback" not in result.stdout


@pytest.mark.parametrize(
    "configuration",
    (
        '[scan]\nlanguage = "fr"\nengine_mode = "disabled"\n',
        '[scan]\nbaseline_path = "missing.json"\nengine_mode = "disabled"\n',
    ),
)
def test_configuration_preflight_outprioritizes_adapter_import_failure(
    configuration: str, tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    (tmp_path / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    (tmp_path / ".rtl-lens.toml").write_text(configuration, encoding="utf-8")

    def failed_adapter():
        raise ImportError("native binding failed")

    monkeypatch.setattr(cli, "_pyslang_engine", failed_adapter)
    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 3
    assert "Invalid project or configuration" in result.stdout
    assert "native binding failed" not in result.stdout
    assert "Traceback" not in result.stdout


def test_malformed_cli_invocation_retains_typer_usage_exit() -> None:
    result = runner.invoke(app, ["scan", "--fail-on", "fatal"])

    assert result.exit_code == 2
    assert "Invalid value" in result.stdout + result.stderr
