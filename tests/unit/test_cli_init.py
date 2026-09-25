"""CLI initialization and public help behavior."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from rtl_lens.cli import app
from rtl_lens.config import load_config

runner = CliRunner()


def test_help_lists_the_public_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("scan", "init", "doctor", "explain", "version"):
        assert command in result.stdout


def test_version_metadata_failure_is_bounded_runtime_exit(monkeypatch) -> None:
    from rtl_lens import cli

    def failed_metadata() -> str:
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(cli, "package_version", failed_metadata)
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 2
    assert "metadata unavailable" in result.stdout
    assert "Traceback" not in result.stdout


def test_version_presentation_failure_uses_plain_fallback(monkeypatch) -> None:
    from rtl_lens import cli

    class BrokenConsole:
        def print(self, value) -> None:
            del value
            raise OSError("console unavailable")

    monkeypatch.setattr(cli, "_console", BrokenConsole)
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 2
    assert "console unavailable" in result.stdout
    assert "Traceback" not in result.stdout


def test_init_creates_a_valid_starter_without_overwriting(tmp_path: Path) -> None:
    first = runner.invoke(app, ["init", str(tmp_path)])

    assert first.exit_code == 0
    config_path = tmp_path / ".rtl-lens.toml"
    assert config_path.is_file()
    assert load_config(tmp_path).scan.output_dir == Path(".rtl-lens")
    assert load_config(tmp_path).scan.graph_display_limit == 200

    original = config_path.read_bytes()
    second = runner.invoke(app, ["init", str(tmp_path)])

    assert second.exit_code == 3
    assert config_path.read_bytes() == original
    assert "already exists" in second.stdout
    assert "Traceback" not in second.stdout


def test_init_force_atomically_replaces_existing_config(tmp_path: Path) -> None:
    config_path = tmp_path / ".rtl-lens.toml"
    config_path.write_text("not valid toml =", encoding="utf-8")

    result = runner.invoke(app, ["init", str(tmp_path), "--force"])

    assert result.exit_code == 0
    assert load_config(tmp_path).scan.timeout == 30
    assert not tuple(tmp_path.glob(".rtl-lens.toml.*.tmp"))


def test_init_force_failure_preserves_existing_file(tmp_path: Path, monkeypatch) -> None:
    from rtl_lens import cli

    config_path = tmp_path / ".rtl-lens.toml"
    config_path.write_text("sentinel", encoding="utf-8")

    def reject_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("replace denied")

    monkeypatch.setattr(cli.os, "replace", reject_replace)
    result = runner.invoke(app, ["init", str(tmp_path), "--force"])

    assert result.exit_code == 2
    assert config_path.read_text(encoding="utf-8") == "sentinel"
    assert not tuple(tmp_path.glob(".rtl-lens.toml.*.tmp"))
    assert "replace denied" in result.stdout
    assert "Traceback" not in result.stdout
