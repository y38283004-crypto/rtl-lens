"""Behavior tests for deterministic, repository-relative source discovery."""

from pathlib import Path

import pytest

from rtl_lens.models.project import ProjectConfig, ScanConfig
from rtl_lens.project import _should_skip_file, resolve_project


def test_discovery_is_sorted_and_repository_relative(tmp_path: Path) -> None:
    """Supported files are ordered by repository-relative path rather than filesystem order."""
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "z.sv").write_text("module z; endmodule", encoding="utf-8")
    (rtl / "a.v").write_text("module a; endmodule", encoding="utf-8")

    project = resolve_project(tmp_path, ProjectConfig())

    assert project.root == tmp_path.resolve()
    assert project.sources == (Path("rtl/a.v"), Path("rtl/z.sv"))


def test_discovery_respects_source_roots_and_ignores_generated_directories(tmp_path: Path) -> None:
    """Ignored metadata, environments, and configured output never enter an engine request."""
    included = tmp_path / "rtl" / "top.sv"
    included.parent.mkdir()
    included.write_text("module top; endmodule", encoding="utf-8")
    for directory in (".git", ".venv", ".rtl-lens", "generated"):
        ignored = tmp_path / directory
        ignored.mkdir()
        (ignored / "ignored.sv").write_text("module ignored; endmodule", encoding="utf-8")

    project = resolve_project(
        tmp_path,
        ProjectConfig(scan=ScanConfig(source_roots=(Path("."),), output_dir=Path("generated"))),
    )

    assert project.sources == (Path("rtl/top.sv"),)


def test_discovery_preserves_unicode_repository_relative_paths(tmp_path: Path) -> None:
    """Unicode directory and source names are retained in the portable source identity."""
    source = tmp_path / "源码" / "模块.sv"
    source.parent.mkdir()
    source.write_text("module unicode_name; endmodule", encoding="utf-8")

    project = resolve_project(
        tmp_path, ProjectConfig(scan=ScanConfig(source_roots=(Path("源码"),)))
    )

    assert project.sources == (Path("源码/模块.sv"),)


def test_discovery_ignores_a_symlink_escaping_the_repository_root(tmp_path: Path) -> None:
    """A real escaping symlink is excluded before a later engine can consume it."""
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "inside.sv").write_text("module inside; endmodule", encoding="utf-8")
    outside = tmp_path.parent / "outside.sv"
    outside.write_text("module outside; endmodule", encoding="utf-8")
    escaping_link = rtl / "escaping.sv"
    try:
        escaping_link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    project = resolve_project(tmp_path, ProjectConfig())

    assert escaping_link.is_symlink()
    assert project.sources == (Path("rtl/inside.sv"),)


def test_discovery_rejects_file_when_resolved_target_is_in_ignored_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovery excludes a file whose resolved target lands inside configured output."""
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "inside.sv").write_text("module inside; endmodule", encoding="utf-8")
    candidate = rtl / "linked.sv"
    candidate.write_text("module linked; endmodule", encoding="utf-8")
    output = tmp_path / "generated"
    output.mkdir()
    ignored_target = output / "artifact.sv"
    ignored_target.write_text("module artifact; endmodule", encoding="utf-8")
    original_resolve = Path.resolve

    def resolve_with_candidate_redirect(self: Path, *args: object, **kwargs: object) -> Path:
        if self == candidate:
            return ignored_target.resolve()
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_with_candidate_redirect)

    project = resolve_project(
        tmp_path,
        ProjectConfig(scan=ScanConfig(source_roots=(Path("rtl"),), output_dir=Path("generated"))),
    )

    assert project.sources == (Path("rtl/inside.sv"),)


def test_file_target_resolved_inside_ignored_output_tree_is_rejected(tmp_path: Path) -> None:
    """A resolved file target inside configured output remains excluded from discovery."""
    output = (tmp_path / "generated").resolve()
    output.mkdir()
    candidate = output / "artifact.sv"
    candidate.write_text("module artifact; endmodule", encoding="utf-8")

    assert _should_skip_file(candidate, tmp_path.resolve(), frozenset({output}))
