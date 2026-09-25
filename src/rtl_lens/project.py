"""Deterministic, repository-bounded RTL project discovery."""

from __future__ import annotations

import os
from pathlib import Path

from rtl_lens.models.project import ProjectConfig, ResolvedProject

SUPPORTED_SUFFIXES = frozenset({".v", ".sv"})
IGNORED_DIRS = frozenset({".git", ".venv", ".rtl-lens"})


def resolve_project(root: Path, config: ProjectConfig) -> ResolvedProject:
    """Discover supported sources as sorted paths relative to a resolved root."""
    resolved_root = root.resolve()
    ignored_paths = _ignored_paths(resolved_root, config)
    sources: set[Path] = set()

    for configured_root in config.scan.source_roots:
        source_root = (
            configured_root if configured_root.is_absolute() else resolved_root / configured_root
        )
        resolved_source_root = source_root.resolve()
        if (
            not resolved_source_root.is_dir()
            or not _is_within(resolved_source_root, resolved_root)
            or _is_ignored(resolved_source_root, ignored_paths)
        ):
            continue
        for directory, child_directories, filenames in os.walk(resolved_source_root):
            current_directory = Path(directory)
            child_directories[:] = [
                name
                for name in child_directories
                if not _should_skip_directory(
                    current_directory / name, resolved_root, ignored_paths
                )
            ]
            for filename in filenames:
                candidate = current_directory / filename
                if candidate.suffix not in SUPPORTED_SUFFIXES:
                    continue
                resolved_candidate = candidate.resolve()
                if _should_skip_file(resolved_candidate, resolved_root, ignored_paths):
                    continue
                sources.add(candidate.relative_to(resolved_root))

    return ResolvedProject(
        root=resolved_root,
        sources=tuple(sorted(sources, key=lambda path: path.as_posix())),
        include_dirs=config.scan.include_dirs,
        defines=config.scan.defines,
        top_modules=config.scan.top_modules,
    )


def _ignored_paths(root: Path, config: ProjectConfig) -> frozenset[Path]:
    output_dir = config.scan.output_dir
    resolved_output = (
        output_dir.resolve() if output_dir.is_absolute() else (root / output_dir).resolve()
    )
    paths = {root / name for name in IGNORED_DIRS}
    if _is_within(resolved_output, root):
        paths.add(resolved_output)
    return frozenset(path.resolve() for path in paths)


def _should_skip_directory(candidate: Path, root: Path, ignored_paths: frozenset[Path]) -> bool:
    resolved_candidate = candidate.resolve()
    return (
        candidate.name in IGNORED_DIRS
        or not _is_within(resolved_candidate, root)
        or _is_ignored(resolved_candidate, ignored_paths)
    )


def _should_skip_file(candidate: Path, root: Path, ignored_paths: frozenset[Path]) -> bool:
    return not _is_within(candidate, root) or _is_ignored(candidate, ignored_paths)


def _is_ignored(candidate: Path, ignored_paths: frozenset[Path]) -> bool:
    return any(
        candidate == ignored_path or candidate.is_relative_to(ignored_path)
        for ignored_path in ignored_paths
    )


def _is_within(candidate: Path, root: Path) -> bool:
    return candidate.is_relative_to(root)
