"""Run deterministic, offline compatibility scans against verified Git checkouts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from rtl_lens.models.report import ScanReport, ScanState

_MIB = 1024 * 1024
_MANIFEST_LIMIT = _MIB
_FILE_LIMIT = 2 * _MIB
_SOURCE_TOTAL_LIMIT = 32 * _MIB
_JSON_LIMIT = 16 * _MIB
_HTML_LIMIT = 32 * _MIB
_GIT_TIMEOUT_SECONDS = 10
_SCAN_TIMEOUT_SECONDS = 90
_LICENSES = frozenset({"MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Apache-2.0", "CC0-1.0"})
_ENGINE_MODES = frozenset({"disabled", "auto", "required"})
_SOURCE_SUFFIXES = frozenset({".v", ".sv", ".vh", ".svh"})
_TOP_SUFFIXES = frozenset({".v", ".sv"})
_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_SHA40_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_REPOSITORY_PATTERN = re.compile(
    r"https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)/"
    r"([A-Za-z0-9_.][A-Za-z0-9_.-]*)\Z"
)
_CONTROL_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_DEVICES = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"{prefix}{digit}" for prefix in ("com", "lpt") for digit in "123456789¹²³"}
)

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=256)]


def _safe_component(value: str) -> bool:
    return (
        not value.endswith((".", " "))
        and not any(character in value for character in '<>"|?*')
        and value.split(".", 1)[0].rstrip(" ").casefold() not in _WINDOWS_DEVICES
    )


def _canonical_path(value: str, *, allow_dot: bool = False) -> str:
    if not value or _CONTROL_PATTERN.search(value) or "\\" in value or ":" in value:
        raise ValueError("path must be a safe POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError("path must be a safe POSIX relative path")
    if value != path.as_posix() or (value == "." and not allow_dot):
        raise ValueError("path must be canonical")
    if any(not _safe_component(part) for part in path.parts):
        raise ValueError("path contains a reserved or normalizing Windows component")
    if path.parts and path.parts[0].casefold() in {".rtl-lens.toml", ".rtl-lens"}:
        raise ValueError("path occupies the runner's configuration or report namespace")
    return value


def _unique_casefold(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    folded = [value.casefold() for value in values]
    if len(set(folded)) != len(values):
        raise ValueError(f"{field} must be unique without Windows case collisions")
    return values


class ProjectSpec(BaseModel):
    """One pinned, attribution-bearing project included in a compatibility scan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    repository: str
    commit: str
    license: str
    license_file: str
    license_sha256: str
    attribution: Identifier
    scope: Identifier
    files: tuple[str, ...] = Field(min_length=1, max_length=200)
    top_files: tuple[str, ...] = Field(min_length=1, max_length=200)
    include_dirs: tuple[str, ...] = Field(default=(), max_length=200)
    defines: tuple[Identifier, ...] = Field(default=(), max_length=200)
    top_modules: tuple[Identifier, ...] = Field(default=(), max_length=200)
    expected_scan_state: Literal["complete", "partial"]

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not _ID_PATTERN.fullmatch(value) or not _safe_component(value):
            raise ValueError("project id is invalid")
        return value

    @field_validator("repository")
    @classmethod
    def valid_repository(cls, value: str) -> str:
        match = _REPOSITORY_PATTERN.fullmatch(value)
        if match is None or match.group(2) in {".", ".."}:
            raise ValueError(
                "repository must be a credential-free GitHub HTTPS owner/repository URL"
            )
        return value

    @field_validator("commit")
    @classmethod
    def valid_commit(cls, value: str) -> str:
        if not _SHA40_PATTERN.fullmatch(value):
            raise ValueError("commit must be a full lowercase SHA-1")
        return value

    @field_validator("license")
    @classmethod
    def valid_license(cls, value: str) -> str:
        if value not in _LICENSES:
            raise ValueError("license is not in the compatibility allowlist")
        return value

    @field_validator("license_sha256")
    @classmethod
    def valid_license_digest(cls, value: str) -> str:
        if not _SHA256_PATTERN.fullmatch(value):
            raise ValueError("license_sha256 must be a lowercase SHA-256")
        return value

    @field_validator("attribution", "scope")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip() or _CONTROL_PATTERN.search(value):
            raise ValueError("text must be nonblank and contain no control characters")
        return value

    @field_validator("license_file")
    @classmethod
    def valid_license_path(cls, value: str) -> str:
        return _canonical_path(value)

    @field_validator("files")
    @classmethod
    def valid_files(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_canonical_path(value) for value in values)
        if any(PurePosixPath(value).suffix.lower() not in _SOURCE_SUFFIXES for value in checked):
            raise ValueError("files must contain only Verilog/SystemVerilog sources")
        return _unique_casefold(checked, "files")

    @field_validator("top_files")
    @classmethod
    def valid_top_files(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_canonical_path(value) for value in values)
        if any(PurePosixPath(value).suffix.lower() not in _TOP_SUFFIXES for value in checked):
            raise ValueError("top_files must contain HDL implementation sources")
        return _unique_casefold(checked, "top_files")

    @field_validator("include_dirs")
    @classmethod
    def valid_include_dirs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(_canonical_path(value, allow_dot=True) for value in values)
        return _unique_casefold(checked, "include_dirs")

    @field_validator("defines", "top_modules")
    @classmethod
    def safe_scalar_lists(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() or _CONTROL_PATTERN.search(value) for value in values):
            raise ValueError("configuration values must be nonblank and contain no controls")
        if len(set(values)) != len(values):
            raise ValueError("configuration values must be unique")
        return values

    @model_validator(mode="after")
    def valid_relationships(self) -> ProjectSpec:
        files = set(self.files)
        if not set(self.top_files).issubset(files):
            raise ValueError("top_files must be a subset of files")
        all_staged = (self.license_file, *self.files)
        if len({value.casefold() for value in all_staged}) != len(all_staged):
            raise ValueError("staged paths must not collide on Windows")
        prefixes: dict[str, str] = {}
        for value in (*all_staged, *self.include_dirs):
            parts = PurePosixPath(value).parts
            for length in range(1, len(parts) + 1):
                prefix = "/".join(parts[:length])
                folded = prefix.casefold()
                if folded in prefixes and prefixes[folded] != prefix:
                    raise ValueError("staged path components have Windows case collisions")
                prefixes[folded] = prefix
        return self


class CompatibilityManifest(BaseModel):
    """Versioned collection of compatibility projects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    projects: tuple[ProjectSpec, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_project_ids(self) -> CompatibilityManifest:
        ids = [project.id for project in self.projects]
        if len(set(ids)) != len(ids):
            raise ValueError("project ids must be unique")
        return self


def load_manifest(path: Path) -> CompatibilityManifest:
    """Load a bounded TOML compatibility manifest without external access."""
    if path.is_symlink() or not path.is_file():
        raise ValueError("manifest must be a regular file")
    size = path.stat().st_size
    if size <= 0 or size > _MANIFEST_LIMIT:
        raise ValueError("manifest size is outside the supported range")
    try:
        with path.open("rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("manifest must be a regular file")
            raw = source.read(_MANIFEST_LIMIT + 1)
        if not raw or len(raw) > _MANIFEST_LIMIT:
            raise ValueError("manifest size is outside the supported range")
        payload = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError("manifest is unreadable or malformed") from error
    return CompatibilityManifest.model_validate(payload)


class _ObservationFailure(Exception):
    def __init__(self, kind: str, *, not_run: bool = False) -> None:
        super().__init__(kind)
        self.kind = kind
        self.not_run = not_run


def _overlap(first: Path, second: Path) -> bool:
    left = first.resolve()
    right = second.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _prepare_output(output: Path) -> Path:
    if _contains_reparse_point(output):
        raise ValueError("output directory is unsafe")
    if output.exists():
        if not output.is_dir():
            raise ValueError("output path is not a directory")
        if any(output.iterdir()):
            raise ValueError("output directory must be empty; refusing nonempty output")
    else:
        output.mkdir(parents=True)
    return output.resolve()


def _git_text(checkout: Path, arguments: list[str], *, limit: int = 256) -> str:
    git = shutil.which("git")
    if git is None:
        raise _ObservationFailure("git-unavailable", not_run=True)
    # Caller Git environment must not redirect this checkout or inject configuration.
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_NO_REPLACE_OBJECTS="1",
        GIT_NO_LAZY_FETCH="1",
        GIT_TERMINAL_PROMPT="0",
    )
    command = [
        git,
        "--no-replace-objects",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-C",
        str(checkout),
        *arguments,
    ]
    try:
        process = subprocess.Popen(
            command,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
    except OSError as error:
        raise _ObservationFailure("git-unavailable", not_run=True) from error
    assert process.stdout is not None
    stdout = process.stdout
    captured = bytearray()
    read_failed = threading.Event()

    def read_output() -> None:
        try:
            captured.extend(stdout.read(limit + 1))
            if len(captured) > limit:
                process.kill()
        except OSError:
            read_failed.set()
        finally:
            stdout.close()

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        return_code = process.wait(timeout=_GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise _ObservationFailure("git-timeout", not_run=True) from None
    finally:
        reader.join(timeout=5)
    if len(captured) > limit:
        raise _ObservationFailure("git-output-limit")
    if reader.is_alive() or read_failed.is_set() or return_code != 0:
        raise _ObservationFailure("git-read-failed")
    try:
        return captured.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise _ObservationFailure("git-output-invalid") from error


def _contains_reparse_point(path: Path) -> bool:
    """Inspect lexical ancestors before resolving; works with Python 3.11 on Windows."""
    absolute = path.absolute()
    for current in (*reversed(absolute.parents), absolute):
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or (
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            return True
    return False


def _verified_file(checkout: Path, project: ProjectSpec, relative: str) -> bytes:
    candidate = checkout.joinpath(*PurePosixPath(relative).parts)
    try:
        if _contains_reparse_point(candidate):
            raise _ObservationFailure("integrity-failed")
        metadata = candidate.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise _ObservationFailure("integrity-failed")
        if not candidate.resolve().is_relative_to(checkout.resolve()):
            raise _ObservationFailure("integrity-failed")
        if metadata.st_size <= 0 or metadata.st_size > _FILE_LIMIT:
            raise _ObservationFailure("resource-limit")
        with candidate.open("rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise _ObservationFailure("integrity-failed")
            payload = source.read(_FILE_LIMIT + 1)
        if not payload or len(payload) > _FILE_LIMIT:
            raise _ObservationFailure("resource-limit")
    except OSError as error:
        raise _ObservationFailure("integrity-failed") from error
    committed_blob = _git_text(checkout, ["rev-parse", f"{project.commit}:{relative}"])
    actual_blob = hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload, usedforsecurity=False
    ).hexdigest()
    if not _SHA40_PATTERN.fullmatch(committed_blob) or actual_blob != committed_blob:
        raise _ObservationFailure("integrity-failed")
    return payload


def _verify_checkout(project: ProjectSpec, checkout: Path) -> list[tuple[str, bytes]]:
    if _contains_reparse_point(checkout):
        raise _ObservationFailure("unsafe-cache")
    if not checkout.exists():
        raise _ObservationFailure("cache-missing", not_run=True)
    if checkout.is_symlink() or not checkout.is_dir():
        raise _ObservationFailure("unsafe-cache")
    head = _git_text(checkout, ["rev-parse", "--verify", "HEAD"])
    if head != project.commit:
        raise _ObservationFailure("revision-mismatch")
    selected: list[tuple[str, bytes]] = []
    total_sources = 0
    for relative in project.files:
        payload = _verified_file(checkout, project, relative)
        total_sources += len(payload)
        if total_sources > _SOURCE_TOTAL_LIMIT:
            raise _ObservationFailure("resource-limit")
        selected.append((relative, payload))
    license_bytes = _verified_file(checkout, project, project.license_file)
    digest = hashlib.sha256(license_bytes).hexdigest()
    if digest != project.license_sha256:
        raise _ObservationFailure("integrity-failed")
    selected.append((project.license_file, license_bytes))
    return selected


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _toml_list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _write_stage_config(stage: Path, project: ProjectSpec, engine_mode: str) -> None:
    config = "\n".join(
        [
            "[scan]",
            'source_roots = ["."]',
            f"include_dirs = {_toml_list(project.include_dirs)}",
            f"defines = {_toml_list(project.defines)}",
            f"top_modules = {_toml_list(project.top_modules)}",
            "timeout = 30",
            'language = "en"',
            f"engine_mode = {_toml_string(engine_mode)}",
            'output_dir = ".rtl-lens"',
            "redact_sources = true",
            "redact_path_prefixes = []",
            "redact_environment_variables = []",
            'fail_on = "error"',
            "graph_display_limit = 200",
            "",
        ]
    )
    (stage / ".rtl-lens.toml").write_text(config, encoding="utf-8")


def _base_result(project: ProjectSpec, engine_mode: str) -> dict[str, object]:
    return {
        "id": project.id,
        "repository": project.repository,
        "commit": project.commit,
        "license": project.license,
        "license_sha256": project.license_sha256,
        "scope": project.scope,
        "files": list(project.files),
        "top_files": list(project.top_files),
        "expected_scan_state": project.expected_scan_state,
        "engine_mode": engine_mode,
        "status": "failed",
        "exit_code": None,
        "elapsed_ms": None,
        "diagnostic_count": None,
        "unknown_count": None,
        "source_count": None,
        "redacted": None,
        "requested_engines": None,
        "completed_engines": None,
        "tool_versions": None,
        "failures": [],
    }


def _write_result(output: Path, result: dict[str, object]) -> None:
    (output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _record_failure(
    output: Path,
    result: dict[str, object],
    failure: _ObservationFailure,
    *,
    elapsed_ms: int | None = None,
    exit_code: int | None = None,
) -> dict[str, object]:
    result["status"] = "not-run" if failure.not_run else "failed"
    result["failures"] = [failure.kind]
    result["elapsed_ms"] = elapsed_ms
    result["exit_code"] = exit_code
    _write_result(output, result)
    return result


def _read_bounded(path: Path, limit: int, failure: str) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise _ObservationFailure(failure)
        size = path.stat().st_size
        if size <= 0 or size > limit:
            raise _ObservationFailure(failure)
        with path.open("rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise _ObservationFailure(failure)
            payload = source.read(limit + 1)
        if not payload or len(payload) > limit:
            raise _ObservationFailure(failure)
        return payload
    except OSError as error:
        raise _ObservationFailure(failure) from error


def _tool_versions(report: ScanReport) -> dict[str, str]:
    try:
        package = importlib.metadata.version("rtl-lens")
    except importlib.metadata.PackageNotFoundError:
        package = "unknown"
    versions = {"python": platform.python_version(), "rtl-lens": package}
    for engine in report.engine_runs:
        if engine.version:
            versions[engine.engine] = engine.version
    return versions


def _validated_reports(stage: Path) -> tuple[ScanReport, bytes, bytes]:
    report_path = stage / ".rtl-lens" / "report.json"
    html_path = stage / ".rtl-lens" / "report.html"
    report_bytes = _read_bounded(report_path, _JSON_LIMIT, "missing-report")
    html_bytes = _read_bounded(html_path, _HTML_LIMIT, "missing-report")
    try:
        report = ScanReport.model_validate_json(report_bytes)
    except Exception as error:
        raise _ObservationFailure("invalid-report") from error
    if not report.metadata.redacted or report.metadata.source_count <= 0:
        raise _ObservationFailure("invalid-report")
    stage_markers = {str(stage), str(stage).replace("\\", "/")}
    decoded_json = report_bytes.decode("utf-8", errors="replace")
    decoded_html = html_bytes.decode("utf-8", errors="replace")
    if any(marker in decoded_json or marker in decoded_html for marker in stage_markers):
        raise _ObservationFailure("invalid-report")
    return report, report_bytes, html_bytes


def scan_project(
    project: ProjectSpec,
    checkout: Path,
    output: Path,
    *,
    engine_mode: str = "disabled",
) -> dict[str, object]:
    """Scan one verified checkout without executing anything from that checkout."""
    if engine_mode not in _ENGINE_MODES:
        raise ValueError("invalid engine mode")
    if _overlap(checkout, output):
        raise ValueError("source and output directories overlap")
    output_root = _prepare_output(output)
    result = _base_result(project, engine_mode)
    try:
        selected = _verify_checkout(project, checkout)
    except _ObservationFailure as failure:
        return _record_failure(output_root, result, failure)

    with tempfile.TemporaryDirectory(prefix="rtl-lens-compatibility-") as temporary:
        stage = Path(temporary)
        try:
            for relative, source in selected:
                destination = stage.joinpath(*PurePosixPath(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source)
            _write_stage_config(stage, project, engine_mode)
        except OSError:
            return _record_failure(output_root, result, _ObservationFailure("staging-failed"))

        started = time.perf_counter()
        command = [sys.executable, "-m", "rtl_lens.cli", "scan", str(stage)]
        try:
            completed = subprocess.run(
                command,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_SCAN_TIMEOUT_SECONDS,
                check=False,
            )
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            elapsed = round((time.perf_counter() - started) * 1000)
            return _record_failure(
                output_root,
                result,
                _ObservationFailure("scan-timeout"),
                elapsed_ms=elapsed,
            )
        except OSError:
            elapsed = round((time.perf_counter() - started) * 1000)
            return _record_failure(
                output_root,
                result,
                _ObservationFailure("scan-unavailable"),
                elapsed_ms=elapsed,
            )
        elapsed = round((time.perf_counter() - started) * 1000)
        try:
            report, report_bytes, html_bytes = _validated_reports(stage)
        except _ObservationFailure as failure:
            return _record_failure(
                output_root, result, failure, elapsed_ms=elapsed, exit_code=exit_code
            )

        status = report.metadata.scan_state.value
        failures: list[str] = []
        if exit_code not in (0, 1) or report.metadata.scan_state is ScanState.FAILED:
            status = "failed"
            failures = ["scan-runtime"]
        result.update(
            {
                "status": status,
                "exit_code": exit_code,
                "elapsed_ms": elapsed,
                "diagnostic_count": len(report.findings),
                "unknown_count": sum(
                    finding.canonical_rule.startswith("engine-native:")
                    for finding in report.findings
                ),
                "source_count": report.metadata.source_count,
                "redacted": True,
                "requested_engines": list(report.metadata.requested_engines),
                "completed_engines": list(report.metadata.completed_engines),
                "tool_versions": _tool_versions(report),
                "failures": failures,
            }
        )
        (output_root / "report.json").write_bytes(report_bytes)
        (output_root / "report.html").write_bytes(html_bytes)
        _write_result(output_root, result)
        return result


def _escape_markdown(value: object) -> str:
    if value is None:
        return "—"
    return (
        str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    )


def _summary(results: list[dict[str, object]]) -> str:
    lines = [
        "# RTL Lens compatibility observations",
        "",
        "> **Warning:** complete means analysis completed, not clean RTL.",
        "",
        "| Project | Repository | Commit | License | Status | Diagnostics | Unknown | Redacted | Failures |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for result in results:
        values = (
            result["id"],
            result["repository"],
            result["commit"],
            result["license"],
            result["status"],
            result["diagnostic_count"],
            result["unknown_count"],
            result["redacted"],
            ", ".join(result["failures"]),  # type: ignore[arg-type]
        )
        lines.append("| " + " | ".join(_escape_markdown(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def run_manifest(
    manifest: CompatibilityManifest,
    cache_dir: Path,
    output: Path,
    *,
    engine_mode: str = "disabled",
) -> list[dict[str, object]]:
    """Run a validated manifest solely from its caller-managed local cache."""
    if engine_mode not in _ENGINE_MODES:
        raise ValueError("invalid engine mode")
    if _contains_reparse_point(cache_dir):
        raise ValueError("cache directory is unsafe")
    if _overlap(cache_dir, output):
        raise ValueError("cache and output directories overlap")
    output_root = _prepare_output(output)
    cache_root = cache_dir.resolve()
    results: list[dict[str, object]] = []
    for project in manifest.projects:
        checkout = cache_dir / project.id / project.commit
        project_output = output_root / project.id
        if checkout.exists() and not checkout.resolve().is_relative_to(cache_root):
            project_output.mkdir()
            result = _base_result(project, engine_mode)
            results.append(
                _record_failure(project_output, result, _ObservationFailure("unsafe-cache"))
            )
        else:
            results.append(scan_project(project, checkout, project_output, engine_mode=engine_mode))
    aggregate = {"schema_version": 1, "result_count": len(results), "results": results}
    (output_root / "results.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "summary.md").write_text(_summary(results), encoding="utf-8")
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("compatibility.toml"))
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "rtl-lens-compatibility-cache",
    )
    parser.add_argument("--output", type=Path, default=Path(".artifacts/compatibility"))
    parser.add_argument("--engine-mode", choices=sorted(_ENGINE_MODES), default="disabled")
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    try:
        manifest = load_manifest(args.manifest)
        results = run_manifest(manifest, args.cache_dir, args.output, engine_mode=args.engine_mode)
    except Exception:  # noqa: BLE001 - CLI exposes only a bounded invocation failure.
        print("compatibility scan rejected invalid manifest, cache, or output", file=sys.stderr)
        return 2
    return 0 if all(result["status"] == "complete" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
