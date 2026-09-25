"""Integration coverage for the offline compatibility evidence runner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

SCRIPT = Path(__file__).parents[2] / "scripts" / "scan_compatibility.py"
SPEC = importlib.util.spec_from_file_location("scan_compatibility", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load compatibility runner")
compatibility = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = compatibility
SPEC.loader.exec_module(compatibility)

CompatibilityManifest = compatibility.CompatibilityManifest
ProjectSpec = compatibility.ProjectSpec
load_manifest = compatibility.load_manifest
run_manifest = compatibility.run_manifest
scan_project = compatibility.scan_project


LICENSE_BYTES = b"MIT License\n\nCopyright (c) Tiny Core contributors\n"
CLEAN_SOURCE = b"module top; endmodule\n"
ERROR_SOURCE = b"module top; assign broken = ; endmodule\n"


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=NUL",
            "-c",
            "user.name=RTL Lens Tests",
            "-c",
            "user.email=rtl-lens-tests@example.invalid",
            "-C",
            str(repository),
            *arguments,
        ],
        check=True,
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def make_committed_fixture(
    tmp_path: Path, *, source: bytes = CLEAN_SOURCE
) -> tuple[ProjectSpec, Path]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _git(checkout, "init", "--template=", "--quiet")
    (checkout / "rtl").mkdir()
    (checkout / "rtl" / "top.sv").write_bytes(source)
    (checkout / "LICENSE").write_bytes(LICENSE_BYTES)
    _git(checkout, "add", "--", "rtl/top.sv", "LICENSE")
    _git(checkout, "commit", "--quiet", "-m", "fixture")
    commit = _git(checkout, "rev-parse", "HEAD")
    project = ProjectSpec(
        id="tiny-core",
        repository="https://github.com/example/tiny-core",
        commit=commit,
        license="MIT",
        license_file="LICENSE",
        license_sha256=hashlib.sha256(LICENSE_BYTES).hexdigest(),
        attribution="Tiny Core contributors",
        scope="Standalone top module; no simulation or whole-repository claim.",
        files=["rtl/top.sv"],
        top_files=["rtl/top.sv"],
        include_dirs=[],
        defines=[],
        top_modules=["top"],
        expected_scan_state="complete",
    )
    return project, checkout


def write_manifest(path: Path, project: ProjectSpec) -> None:
    values = project.model_dump(mode="json")
    path.write_text(
        "\n".join(
            [
                "schema_version = 1",
                "[[projects]]",
                f"id = {json.dumps(values['id'])}",
                f"repository = {json.dumps(values['repository'])}",
                f"commit = {json.dumps(values['commit'])}",
                f"license = {json.dumps(values['license'])}",
                f"license_file = {json.dumps(values['license_file'])}",
                f"license_sha256 = {json.dumps(values['license_sha256'])}",
                f"attribution = {json.dumps(values['attribution'])}",
                f"scope = {json.dumps(values['scope'])}",
                f"files = {json.dumps(values['files'])}",
                f"top_files = {json.dumps(values['top_files'])}",
                f"include_dirs = {json.dumps(values['include_dirs'])}",
                f"defines = {json.dumps(values['defines'])}",
                f"top_modules = {json.dumps(values['top_modules'])}",
                f"expected_scan_state = {json.dumps(values['expected_scan_state'])}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_manifest_rejects_growth_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = make_committed_fixture(tmp_path)
    manifest = tmp_path / "compatibility.toml"
    write_manifest(manifest, project)
    original_open = Path.open

    def grow_then_open(path, *args, **kwargs):
        if path == manifest:
            with original_open(path, "ab") as output:
                output.write(b"#" * (compatibility._MANIFEST_LIMIT + 1))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_then_open)
    with pytest.raises(ValueError, match="manifest"):
        load_manifest(manifest)


def test_report_rejects_growth_before_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = tmp_path / "report.json"
    report.write_bytes(b"{}")
    original_open = Path.open

    def grow_then_open(path, *args, **kwargs):
        if path == report:
            with original_open(path, "ab") as output:
                output.write(b" " * 100)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_then_open)
    with pytest.raises(compatibility._ObservationFailure, match="missing-report"):
        compatibility._read_bounded(report, 16, "missing-report")


@pytest.mark.parametrize("payload", [b"", b"x" * 17])
def test_report_rejects_empty_or_oversized_bytes(tmp_path: Path, payload: bytes) -> None:
    report = tmp_path / "report.html"
    report.write_bytes(payload)
    with pytest.raises(compatibility._ObservationFailure, match="missing-report"):
        compatibility._read_bounded(report, 16, "missing-report")


def test_report_accepts_exact_byte_limit(tmp_path: Path) -> None:
    report = tmp_path / "report.html"
    report.write_bytes(b"x" * 16)
    assert compatibility._read_bounded(report, 16, "missing-report") == b"x" * 16


def test_git_output_uses_bounded_pipe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_popen = subprocess.Popen

    def noisy_git(command, **kwargs):
        assert kwargs["stdout"] == subprocess.PIPE
        return real_popen(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1000000)"],
            **kwargs,
        )

    monkeypatch.setattr(compatibility.subprocess, "Popen", noisy_git)
    with pytest.raises(compatibility._ObservationFailure, match="git-output-limit"):
        compatibility._git_text(tmp_path, ["rev-parse", "HEAD"], limit=64)


@pytest.mark.parametrize(
    ("child_code", "failure"),
    [
        ("import sys; sys.exit(1)", "git-read-failed"),
        ("import sys; sys.stdout.buffer.write(bytes([255]))", "git-output-invalid"),
        ("import time; time.sleep(30)", "git-timeout"),
        ("import sys; sys.stdout.write('a' * 64)", None),
    ],
)
def test_git_pipe_preserves_exit_encoding_timeout_and_exact_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, child_code: str, failure: str | None
) -> None:
    real_popen = subprocess.Popen
    children = []

    def controlled_git(command, **kwargs):
        child = real_popen([sys.executable, "-c", child_code], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(compatibility.subprocess, "Popen", controlled_git)
    monkeypatch.setattr(compatibility, "_GIT_TIMEOUT_SECONDS", 1)
    if failure:
        with pytest.raises(compatibility._ObservationFailure, match=failure):
            compatibility._git_text(tmp_path, ["rev-parse", "HEAD"], limit=64)
    else:
        assert compatibility._git_text(tmp_path, ["rev-parse", "HEAD"], limit=64) == "a" * 64
    assert len(children) == 1
    assert children[0].poll() is not None
    assert children[0].stdout.closed


def test_cached_clean_fixture_produces_redacted_complete_scan(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    output = tmp_path / "observations"

    result = scan_project(project, checkout, output)

    assert result["status"] == "complete"
    assert result["exit_code"] == 0
    assert result["diagnostic_count"] == 0
    assert result["unknown_count"] == 0
    assert result["redacted"] is True
    assert result["source_count"] == 1
    assert not (checkout / ".rtl-lens.toml").exists()
    assert str(tmp_path) not in (output / "result.json").read_text(encoding="utf-8")
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["metadata"]["redacted"] is True


def test_real_policy_error_is_still_a_completed_observation(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path, source=ERROR_SOURCE)

    result = scan_project(project, checkout, tmp_path / "observations")

    assert result["exit_code"] == 1
    assert result["status"] == "complete"
    assert result["diagnostic_count"] > 0
    assert result["unknown_count"] > 0


def test_load_manifest_uses_actual_fixture_commit_and_digest(tmp_path: Path) -> None:
    project, _ = make_committed_fixture(tmp_path)
    manifest_path = tmp_path / "compatibility.toml"
    write_manifest(manifest_path, project)

    loaded = load_manifest(manifest_path)

    assert loaded.schema_version == 1
    assert loaded.projects == (project,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "UPPER"),
        ("commit", "A" * 40),
        ("commit", "1" * 39),
        ("license_sha256", "2" * 63),
        ("repository", "http://github.com/example/tiny-core"),
        ("repository", "https://user@github.com/example/tiny-core"),
        ("repository", "https://github.com/-option/tiny-core"),
        ("repository", "https://github.com/example/tiny-core?ref=main"),
        ("license", "GPL-3.0"),
        ("attribution", ""),
        ("scope", "\n"),
    ],
)
def test_project_rejects_malformed_identity_fields(
    tmp_path: Path, field: str, value: object
) -> None:
    project, _ = make_committed_fixture(tmp_path)

    with pytest.raises(ValidationError):
        ProjectSpec.model_validate({**project.model_dump(), field: value})


@pytest.mark.parametrize(
    "unsafe",
    [
        "",
        "../top.sv",
        "rtl/../top.sv",
        "/rtl/top.sv",
        "C:/rtl/top.sv",
        "C:\\rtl\\top.sv",
        "\\\\server\\share\\top.sv",
        "rtl\\top.sv",
        "rtl/top.sv\n",
    ],
)
def test_project_rejects_unsafe_source_paths(tmp_path: Path, unsafe: str) -> None:
    project, _ = make_committed_fixture(tmp_path)

    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {**project.model_dump(), "files": [unsafe], "top_files": [unsafe]}
        )


def test_manifest_rejects_duplicate_ids_and_extra_fields(tmp_path: Path) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError):
        CompatibilityManifest(schema_version=1, projects=[project, project])
    with pytest.raises(ValidationError):
        CompatibilityManifest.model_validate(
            {"schema_version": 1, "projects": [project.model_dump()], "surprise": True}
        )


def test_manifest_enforces_schema_cardinality_and_size(tmp_path: Path) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError):
        CompatibilityManifest(schema_version=2, projects=[project])
    with pytest.raises(ValidationError):
        CompatibilityManifest(schema_version=1, projects=[])
    with pytest.raises(ValidationError):
        CompatibilityManifest(schema_version=1, projects=[project] * 11)
    oversized = tmp_path / "oversized.toml"
    oversized.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="size"):
        load_manifest(oversized)


def test_project_rejects_noncanonical_relationships_and_case_collisions(
    tmp_path: Path,
) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError, match="subset"):
        ProjectSpec.model_validate({**project.model_dump(), "top_files": ["rtl/other.sv"]})
    with pytest.raises(ValidationError, match="case"):
        ProjectSpec.model_validate(
            {
                **project.model_dump(),
                "files": ["rtl/top.sv", "RTL/TOP.SV"],
                "top_files": ["rtl/top.sv"],
            }
        )
    accepted = ProjectSpec.model_validate({**project.model_dump(), "include_dirs": ["."]})
    assert accepted.include_dirs == (".",)


def test_missing_cache_is_not_run_with_unknown_observation_values(tmp_path: Path) -> None:
    project, _ = make_committed_fixture(tmp_path)

    result = scan_project(project, tmp_path / "absent", tmp_path / "observations")

    assert result["status"] == "not-run"
    assert result["exit_code"] is None
    assert result["diagnostic_count"] is None
    assert result["unknown_count"] is None
    assert result["source_count"] is None
    assert result["redacted"] is None
    assert result["failures"] == ["cache-missing"]


@pytest.mark.parametrize("target", ["source", "license", "head", "missing-top"])
def test_cache_integrity_failures_do_not_scan(tmp_path: Path, target: str) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    if target == "source":
        (checkout / "rtl" / "top.sv").write_text("module changed; endmodule\n")
    elif target == "license":
        (checkout / "LICENSE").write_text("changed\n")
    elif target == "head":
        (checkout / "other.sv").write_text("module other; endmodule\n")
        _git(checkout, "add", "--", "other.sv")
        _git(checkout, "commit", "--quiet", "-m", "other")
    else:
        (checkout / "rtl" / "top.sv").unlink()

    result = scan_project(project, checkout, tmp_path / "observations")

    assert result["status"] == "failed"
    assert result["exit_code"] is None
    assert result["redacted"] is None
    assert not (tmp_path / "observations" / "report.json").exists()


def test_oversized_selected_file_is_rejected_before_scan(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path, source=b" " * (2 * 1024 * 1024 + 1))

    result = scan_project(project, checkout, tmp_path / "observations")

    assert result["status"] == "failed"
    assert result["failures"] == ["resource-limit"]


def test_nonempty_output_is_refused_without_reusing_stale_success(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    output = tmp_path / "observations"
    output.mkdir()
    (output / "result.json").write_text('{"status":"complete"}', encoding="utf-8")

    with pytest.raises(ValueError, match="nonempty"):
        scan_project(project, checkout, output)

    assert json.loads((output / "result.json").read_text())["status"] == "complete"


def test_existing_empty_output_is_accepted_and_source_overlap_is_refused(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()

    assert scan_project(project, checkout, empty)["status"] == "complete"

    with pytest.raises(ValueError, match="overlap"):
        scan_project(project, checkout, checkout / "evidence")
    assert not (checkout / "evidence").exists()


def test_timeout_and_malformed_report_cannot_create_stale_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, checkout = make_committed_fixture(tmp_path)

    def timeout(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise subprocess.TimeoutExpired([sys.executable], 90)

    monkeypatch.setattr(compatibility.subprocess, "run", timeout)
    timed_out = scan_project(project, checkout, tmp_path / "timeout")
    assert timed_out["status"] == "failed"
    assert timed_out["failures"] == ["scan-timeout"]
    assert not (tmp_path / "timeout" / "report.json").exists()

    def malformed(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        stage = Path(arguments[-1])
        report_dir = stage / ".rtl-lens"
        report_dir.mkdir()
        (report_dir / "report.json").write_text("{}", encoding="utf-8")
        (report_dir / "report.html").write_text("<html></html>", encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(compatibility.subprocess, "run", malformed)
    malformed_result = scan_project(project, checkout, tmp_path / "malformed")
    assert malformed_result["status"] == "failed"
    assert malformed_result["failures"] == ["invalid-report"]
    assert not (tmp_path / "malformed" / "report.json").exists()


@pytest.mark.parametrize(
    ("behavior", "failure"),
    [("missing-executable", "scan-unavailable"), ("missing-report", "missing-report")],
)
def test_missing_subprocess_or_report_is_a_bounded_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    behavior: str,
    failure: str,
) -> None:
    project, checkout = make_committed_fixture(tmp_path)

    def replacement(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del args, kwargs
        if behavior == "missing-executable":
            raise FileNotFoundError("python unavailable")
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(compatibility.subprocess, "run", replacement)
    result = scan_project(project, checkout, tmp_path / behavior)

    assert result["status"] == "failed"
    assert result["failures"] == [failure]
    assert result["diagnostic_count"] is None
    assert not (tmp_path / behavior / "report.json").exists()


def test_cli_invocation_is_an_argument_array_with_devnull_and_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    seed_output = tmp_path / "seed"
    assert scan_project(project, checkout, seed_output)["status"] == "complete"
    report_bytes = (seed_output / "report.json").read_bytes()
    html_bytes = (seed_output / "report.html").read_bytes()

    def controlled(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert arguments[:5] == [sys.executable, "-m", "rtl_lens.cli", "scan", arguments[4]]
        assert isinstance(arguments[4], str)
        assert kwargs == {
            "shell": False,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "timeout": 90,
            "check": False,
        }
        report_dir = Path(arguments[4]) / ".rtl-lens"
        report_dir.mkdir()
        (report_dir / "report.json").write_bytes(report_bytes)
        (report_dir / "report.html").write_bytes(html_bytes)
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(compatibility.subprocess, "run", controlled)
    result = scan_project(project, checkout, tmp_path / "controlled")

    assert result["status"] == "complete"


def test_run_manifest_writes_matching_redacted_aggregate_and_summary(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    cache_dir = tmp_path / "cache"
    cached = cache_dir / project.id / project.commit
    cached.parent.mkdir(parents=True)
    checkout.rename(cached)
    missing = ProjectSpec.model_validate(
        {**project.model_dump(), "id": "missing-core", "commit": "1" * 40}
    )
    manifest = CompatibilityManifest(schema_version=1, projects=[project, missing])
    output = tmp_path / "aggregate"

    results = run_manifest(manifest, cache_dir, output)

    aggregate = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert aggregate["schema_version"] == 1
    assert aggregate["result_count"] == 2
    assert aggregate["results"] == results
    assert [item["id"] for item in results] == ["tiny-core", "missing-core"]
    assert [item["status"] for item in results] == ["complete", "not-run"]
    assert [item["redacted"] for item in results] == [True, None]
    assert str(tmp_path) not in (output / "results.json").read_text(encoding="utf-8")
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert summary.count("| tiny-core |") == 1
    assert summary.count("| missing-core |") == 1
    assert "analysis completed, not clean RTL" in summary


def test_run_manifest_rejects_cache_output_overlap_before_writing(tmp_path: Path) -> None:
    project, _ = make_committed_fixture(tmp_path)
    manifest = CompatibilityManifest(schema_version=1, projects=[project])
    cache = tmp_path / "cache"

    with pytest.raises(ValueError, match="overlap"):
        run_manifest(manifest, cache, cache / "output")

    assert not (cache / "output").exists()


def test_cli_exit_codes_distinguish_complete_missing_and_invalid(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    cache = tmp_path / "cache"
    cached = cache / project.id / project.commit
    cached.parent.mkdir(parents=True)
    checkout.rename(cached)
    manifest_path = tmp_path / "compatibility.toml"
    write_manifest(manifest_path, project)

    assert (
        compatibility.main(
            [
                "--manifest",
                str(manifest_path),
                "--cache-dir",
                str(cache),
                "--output",
                str(tmp_path / "ok"),
            ]
        )
        == 0
    )
    assert (
        compatibility.main(
            [
                "--manifest",
                str(manifest_path),
                "--cache-dir",
                str(tmp_path / "missing"),
                "--output",
                str(tmp_path / "not-run"),
            ]
        )
        == 1
    )
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("schema_version = 99\n", encoding="utf-8")
    assert (
        compatibility.main(
            ["--manifest", str(invalid), "--output", str(tmp_path / "invalid-output")]
        )
        == 2
    )
    assert not (tmp_path / "invalid-output").exists()


def test_git_replace_ref_cannot_falsify_pinned_source_identity(tmp_path: Path) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    (checkout / "rtl/top.sv").write_bytes(ERROR_SOURCE)
    _git(checkout, "add", "rtl/top.sv")
    _git(checkout, "commit", "--quiet", "-m", "replacement")
    replacement = _git(checkout, "rev-parse", "HEAD")
    _git(checkout, "update-ref", "HEAD", project.commit)
    _git(checkout, "replace", project.commit, replacement)

    result = scan_project(project, checkout, tmp_path / "observations")

    assert result["status"] == "failed"
    assert result["failures"] == ["integrity-failed"]
    assert result["exit_code"] is None
    assert not (tmp_path / "observations/report.json").exists()


def test_inherited_git_directory_cannot_redirect_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    other_root = tmp_path / "other"
    other_root.mkdir()
    _, other = make_committed_fixture(other_root, source=ERROR_SOURCE)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))

    result = scan_project(project, checkout, tmp_path / "observations")

    assert result["status"] == "complete"
    assert result["diagnostic_count"] == 0


@pytest.mark.parametrize("changed", ["rtl/top.sv", "LICENSE"])
def test_staged_bytes_are_the_verified_snapshot_despite_cache_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    verify = compatibility._verify_checkout
    execute = subprocess.run

    def mutate_after_verification(*args: object, **kwargs: object) -> object:
        selected = verify(*args, **kwargs)
        (checkout / changed).write_bytes(b"!" * (2 * 1024 * 1024 + 1))
        return selected

    def inspect_then_execute(arguments: list[str], **kwargs: object) -> object:
        stage = Path(arguments[-1])
        assert (stage / "rtl/top.sv").read_bytes() == CLEAN_SOURCE
        assert (stage / "LICENSE").read_bytes() == LICENSE_BYTES
        return execute(arguments, **kwargs)

    monkeypatch.setattr(compatibility, "_verify_checkout", mutate_after_verification)
    monkeypatch.setattr(compatibility.subprocess, "run", inspect_then_execute)
    result = scan_project(project, checkout, tmp_path / "observations")

    assert result["status"] == "complete"
    assert result["diagnostic_count"] == 0


@pytest.mark.parametrize("identifier", ["con", "nul", "aux", "prn", "com1", "lpt9"])
def test_windows_device_ids_are_rejected(tmp_path: Path, identifier: str) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate({**project.model_dump(), "id": identifier})


@pytest.mark.parametrize(
    "path",
    ["CON.sv", "rtl/NuL.v", "com1/top.sv", "LPT¹/top.sv", "rtl./top.sv", "rtl /top.sv"],
)
def test_windows_alias_source_components_are_rejected(tmp_path: Path, path: str) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate({**project.model_dump(), "files": [path], "top_files": [path]})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("license_file", ".rtl-lens.toml"),
        ("license_file", ".RTL-LENS.TOML/notice"),
        ("license_file", ".rtl-lens/notice"),
        ("include_dirs", [".RTL-LENS"]),
        ("include_dirs", [".rtl-lens.toml"]),
        ("files", [".RTL-LENS/top.sv"]),
    ],
)
def test_controller_staging_names_cannot_be_used_by_inputs(
    tmp_path: Path, field: str, value: object
) -> None:
    project, _ = make_committed_fixture(tmp_path)
    values = {**project.model_dump(), field: value}
    if field == "files":
        values["top_files"] = value
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(values)


@pytest.mark.parametrize("suffix", ["./repo", "../repo", "owner/.", "owner/.."])
def test_repository_dot_segments_are_rejected(tmp_path: Path, suffix: str) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(
            {**project.model_dump(), "repository": "https://github.com/" + suffix}
        )


@pytest.fixture
def directory_junction(tmp_path: Path):
    if os.name != "nt":
        pytest.skip("live junction boundary requires Windows")
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable for junction fixture creation")
    target = tmp_path / "junction-target"
    target.mkdir()
    link = tmp_path / "junction-link"
    environment = {**os.environ, "RTL_TEST_LINK": str(link), "RTL_TEST_TARGET": str(target)}
    created = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$ErrorActionPreference='Stop'; New-Item -ItemType Junction "
                "-Path $env:RTL_TEST_LINK -Target $env:RTL_TEST_TARGET | Out-Null"
            ),
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if created.returncode != 0:
        pytest.skip("Windows junction creation is unavailable")
    try:
        yield link, target
    finally:
        # Remove only the junction entry, never recursively traverse its target.
        link.rmdir()


@pytest.mark.parametrize("nested", [False, True])
def test_output_junction_or_ancestor_cannot_redirect_writes(
    tmp_path: Path, directory_junction: tuple[Path, Path], nested: bool
) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    link, target = directory_junction
    output = link / "nested" if nested else link
    with pytest.raises(ValueError, match="unsafe"):
        scan_project(project, checkout, output)
    assert list(target.iterdir()) == []


def test_cache_junction_ancestor_is_rejected(
    tmp_path: Path, directory_junction: tuple[Path, Path]
) -> None:
    project, checkout = make_committed_fixture(tmp_path)
    link, target = directory_junction
    checkout.rename(target / "checkout")
    result = scan_project(project, link / "checkout", tmp_path / "observations")
    assert result["status"] == "failed"
    assert result["failures"] == ["unsafe-cache"]
    assert result["exit_code"] is None


def test_case_alias_directories_cannot_merge_distinct_source_trees(tmp_path: Path) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError, match="case"):
        ProjectSpec.model_validate(
            {**project.model_dump(), "files": ["rtl/top.sv", "RTL/other.sv"]}
        )


@pytest.mark.parametrize("path", ["CON .sv", "NUL .v", "COM1 .sv", "rtl/LPT1 .v"])
def test_windows_device_stems_with_spaces_are_rejected(tmp_path: Path, path: str) -> None:
    project, _ = make_committed_fixture(tmp_path)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate({**project.model_dump(), "files": [path], "top_files": [path]})
