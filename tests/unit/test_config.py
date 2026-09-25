"""Behavior tests for strict project configuration loading."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from rtl_lens.config import config_digest, load_config
from rtl_lens.models.diagnostic import Severity
from rtl_lens.models.project import ProjectConfig


def test_cli_override_wins_over_toml(tmp_path: Path) -> None:
    """An explicitly allowed CLI value has the highest configuration priority."""
    (tmp_path / ".rtl-lens.toml").write_text(
        '[scan]\nlanguage = "en"\nsource_roots = ["rtl"]\n', encoding="utf-8"
    )

    config = load_config(tmp_path, {"scan.language": "zh-CN"})

    assert config.scan.language == "zh-CN"
    assert config.scan.source_roots == (Path("rtl"),)


def test_toml_values_win_over_documented_defaults(tmp_path: Path) -> None:
    """Project TOML supplies only the values it explicitly declares."""
    (tmp_path / ".rtl-lens.toml").write_text("[scan]\ntimeout = 12\n", encoding="utf-8")

    config = load_config(tmp_path)

    assert config.scan.timeout == 12
    assert config.scan.language == "en"
    assert config.scan.source_roots == (Path("."),)


def test_unknown_toml_key_is_rejected(tmp_path: Path) -> None:
    """Misspelled project configuration must not silently change scan behavior."""
    (tmp_path / ".rtl-lens.toml").write_text("[scan]\nunknown = true\n", encoding="utf-8")

    with pytest.raises(ValidationError, match="unknown"):
        load_config(tmp_path)


def test_only_explicitly_allowed_dotted_overrides_are_accepted(tmp_path: Path) -> None:
    """CLI overrides cannot introduce arbitrary configuration fields."""
    with pytest.raises(ValueError, match="scan.unknown"):
        load_config(tmp_path, {"scan.unknown": "value"})


def test_override_requires_its_toml_section_to_be_a_table(tmp_path: Path) -> None:
    """A malformed TOML section has a type error before overrides are merged."""
    (tmp_path / ".rtl-lens.toml").write_text('scan = "not-a-table"\n', encoding="utf-8")

    with pytest.raises(TypeError, match="scan"):
        load_config(tmp_path, {"scan.language": "zh-CN"})


def test_config_digest_is_stable_and_distinguishes_effective_configuration(tmp_path: Path) -> None:
    """Digesting identical effective configuration yields a SHA-256 identifier."""
    default_digest = config_digest(ProjectConfig())
    changed_digest = config_digest(load_config(tmp_path, {"scan.language": "zh-CN"}))

    assert default_digest == "fd22b545ad6f39b0046e1175495300aa8b595abcb4ca2c8711464dfba29bfe6f"
    assert changed_digest != default_digest


def test_fail_on_override_is_validated_and_changes_effective_digest(tmp_path: Path) -> None:
    default = load_config(tmp_path)
    warning = load_config(tmp_path, {"scan.fail_on": "warning"})

    assert warning.scan.fail_on is Severity.WARNING
    assert config_digest(warning) != config_digest(default)


@pytest.mark.parametrize("limit", (1, 200, 2000))
def test_graph_display_limit_accepts_documented_toml_bounds(tmp_path: Path, limit: int) -> None:
    (tmp_path / ".rtl-lens.toml").write_text(
        f"[scan]\ngraph_display_limit = {limit}\n", encoding="utf-8"
    )

    assert load_config(tmp_path).scan.graph_display_limit == limit


@pytest.mark.parametrize("limit", (1, 200, 2000))
def test_graph_display_limit_accepts_documented_overrides(tmp_path: Path, limit: int) -> None:
    config = load_config(tmp_path, {"scan.graph_display_limit": limit})

    assert config.scan.graph_display_limit == limit


@pytest.mark.parametrize("limit", (0, 2001))
def test_graph_display_limit_rejects_override_values_outside_bounds(
    tmp_path: Path, limit: int
) -> None:
    with pytest.raises(ValidationError):
        load_config(tmp_path, {"scan.graph_display_limit": limit})


@pytest.mark.parametrize("limit", (0, 2001))
def test_graph_display_limit_rejects_toml_values_outside_bounds(tmp_path: Path, limit: int) -> None:
    (tmp_path / ".rtl-lens.toml").write_text(
        f"[scan]\ngraph_display_limit = {limit}\n", encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        load_config(tmp_path)
