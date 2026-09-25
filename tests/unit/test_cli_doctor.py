"""Read-only environment diagnostics exposed by the CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from rtl_lens.cli import app

runner = CliRunner()


class AvailablePySlang:
    def available(self) -> bool:
        return True

    def version(self) -> str:
        return "11.0"


class MissingVerilator:
    def available(self) -> bool:
        return False


def test_doctor_reports_independent_checks_and_optional_warning(
    tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    monkeypatch.setattr(cli, "_pyslang_engine", AvailablePySlang)
    monkeypatch.setattr(cli, "VerilatorEngine", MissingVerilator)
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)

    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 0
    for label in (
        "Python",
        "PySlang",
        "Verilator",
        "Configuration",
        "Output directory",
        "Container",
    ):
        assert label in result.stdout
    assert "WARN" in result.stdout
    assert not (tmp_path / ".rtl-lens").exists()


def test_doctor_checks_every_item_when_required_dependency_fails(
    tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    class BrokenPySlang:
        def available(self) -> bool:
            raise RuntimeError("binding unavailable")

    monkeypatch.setattr(cli, "_pyslang_engine", BrokenPySlang)
    monkeypatch.setattr(cli, "VerilatorEngine", MissingVerilator)

    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 2
    assert "binding unavailable" in result.stdout
    assert "Container" in result.stdout
    assert "Traceback" not in result.stdout


def test_doctor_invalid_configuration_is_exit_three(tmp_path: Path) -> None:
    (tmp_path / ".rtl-lens.toml").write_text("[scan]\ntimeout = 0\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 3
    assert "Configuration" in result.stdout
    assert "FAIL" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_import_does_not_load_pyslang_native_bindings(tmp_path: Path) -> None:
    script = """
import builtins
real_import = builtins.__import__
def blocked(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "pyslang" or name.startswith("pyslang."):
        raise ImportError("blocked native binding")
    return real_import(name, globals, locals, fromlist, level)
builtins.__import__ = blocked
import rtl_lens.cli
from typer.testing import CliRunner
runner = CliRunner()
assert runner.invoke(rtl_lens.cli.app, ["--help"]).exit_code == 0
assert runner.invoke(rtl_lens.cli.app, ["version"]).exit_code == 0
print("CLI loaded")
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "CLI loaded"


def test_doctor_container_probe_failure_is_an_optional_warning(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    monkeypatch.setattr(cli, "_pyslang_engine", AvailablePySlang)
    monkeypatch.setattr(cli, "VerilatorEngine", MissingVerilator)

    def failed_lookup(name: str) -> str | None:
        del name
        raise OSError("PATH lookup failed")

    monkeypatch.setattr(cli.shutil, "which", failed_lookup)
    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 0
    assert "Container" in result.stdout
    assert "WARN" in result.stdout
    assert "PATH lookup failed" in result.stdout
    assert "Traceback" not in result.stdout


def test_doctor_output_probe_failure_is_isolated_as_invalid_project(
    tmp_path: Path, monkeypatch
) -> None:
    from rtl_lens import cli

    monkeypatch.setattr(cli, "_pyslang_engine", AvailablePySlang)
    monkeypatch.setattr(cli, "VerilatorEngine", MissingVerilator)

    def failed_access(path: Path) -> bool:
        del path
        raise OSError("output probe failed")

    monkeypatch.setattr(cli, "_is_writable_directory", failed_access)
    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 3
    assert "Output directory" in result.stdout
    assert "output probe failed" in result.stdout
    assert "Container" in result.stdout
    assert "Traceback" not in result.stdout
