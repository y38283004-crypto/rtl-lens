"""Resolved path authorization for reports, baselines, and atomic writers."""

from __future__ import annotations

from pathlib import Path


def resolve_output_root(project_root: Path, configured: Path) -> Path:
    """Resolve an output root, confining relative values to ``project_root``."""
    root = project_root.resolve()
    if configured.is_absolute():
        return configured.resolve()
    output_root = (root / configured).resolve()
    if not output_root.is_relative_to(root):
        raise ValueError("relative output root must resolve beneath the project root")
    return output_root


def resolve_report_destination(
    project_root: Path,
    output_dir: Path,
    override: Path | None,
    default_name: str,
) -> Path:
    """Resolve one report path beneath the output root unless explicitly absolute."""
    output_root = resolve_output_root(project_root, output_dir)
    if override is not None and override.is_absolute():
        return _resolve_report_leaf(override, boundary=None)
    relative = override if override is not None else Path(default_name)
    return _resolve_report_leaf(output_root / relative, boundary=output_root)


def resolve_baseline_path(
    project_root: Path,
    output_dir: Path,
    configured: Path,
) -> Path:
    """Resolve a baseline beneath the output root unless explicitly absolute."""
    if configured.is_absolute():
        return configured.resolve()
    output_root = resolve_output_root(project_root, output_dir)
    baseline = (output_root / configured).resolve()
    if not baseline.is_relative_to(output_root):
        raise ValueError("relative baseline path must resolve beneath the output root")
    return baseline


def validate_atomic_destination(destination: Path) -> Path:
    """Refuse symlink leaves and require a real directory for atomic output."""
    if destination.is_symlink():
        raise ValueError("report destination must not be a symlink")
    if destination.exists() and not destination.is_file():
        raise ValueError("report destination must be a regular file or not exist")
    if not destination.parent.is_dir():
        raise ValueError("report destination parent must be an existing directory")
    return destination


def _resolve_report_leaf(candidate: Path, *, boundary: Path | None) -> Path:
    """Authorize a resolved target while preserving its leaf for a second symlink check."""
    if candidate.is_symlink():
        raise ValueError("report destination must not be a symlink")
    destination = candidate.parent.resolve() / candidate.name
    resolved_destination = destination.resolve()
    if boundary is not None and not resolved_destination.is_relative_to(boundary):
        raise ValueError("relative report destination must resolve beneath the output root")
    return destination
