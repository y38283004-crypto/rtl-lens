"""Strict loading and stable identity for RTL Lens project configuration."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping
from pathlib import Path

from rtl_lens.models.project import ProjectConfig

CONFIG_FILENAME = ".rtl-lens.toml"
ALLOWED_OVERRIDES = frozenset(
    {
        "scan.source_roots",
        "scan.include_dirs",
        "scan.defines",
        "scan.top_modules",
        "scan.timeout",
        "scan.language",
        "scan.engine_mode",
        "scan.output_dir",
        "scan.baseline_path",
        "scan.redact_sources",
        "scan.fail_on",
        "scan.graph_display_limit",
    }
)


def load_config(
    root: Path,
    overrides: dict[str, object] | None = None,
    *,
    config_path: Path | None = None,
) -> ProjectConfig:
    """Load defaults, then project TOML, then explicitly allowed CLI overrides."""
    selected_path = config_path or root / CONFIG_FILENAME
    values: dict[str, object]
    if selected_path.is_file():
        loaded = tomllib.loads(selected_path.read_text(encoding="utf-8"))
        values = dict(loaded)
    else:
        values = {}

    for dotted_name, value in (overrides or {}).items():
        if dotted_name not in ALLOWED_OVERRIDES:
            raise ValueError(f"unsupported configuration override: {dotted_name}")
        section, field = dotted_name.split(".", maxsplit=1)
        current_section = values.setdefault(section, {})
        if not isinstance(current_section, Mapping):
            raise TypeError(f"configuration section must be a table: {section}")
        updated_section = dict(current_section)
        updated_section[field] = value
        values[section] = updated_section

    return ProjectConfig.model_validate(values)


def config_digest(config: ProjectConfig) -> str:
    """Return the SHA-256 identity of the validated effective configuration."""
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
