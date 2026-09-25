"""Bilingual rule explanation CLI behavior."""

from __future__ import annotations

from typer.testing import CliRunner

from rtl_lens.cli import app

runner = CliRunner()


def test_explain_renders_both_reviewed_locales() -> None:
    result = runner.invoke(app, ["explain", "width-mismatch"])

    assert result.exit_code == 0
    assert "Assignment width mismatch" in result.stdout
    assert "赋值两侧位宽不一致" in result.stdout
    assert "Cause" in result.stdout
    assert "原因" in result.stdout


def test_explain_unknown_rule_is_configuration_exit() -> None:
    result = runner.invoke(app, ["explain", "does-not-exist"])

    assert result.exit_code == 3
    assert "Unknown rule" in result.stdout
    assert "Traceback" not in result.stdout
