"""Safe external Verilator execution with bounded SARIF ingestion."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock, Thread
from time import perf_counter
from typing import IO, Literal, cast

from rtl_lens.engines.sarif import SarifAdapterError, parse_verilator_sarif
from rtl_lens.models.diagnostic import RawDiagnostic
from rtl_lens.models.engine import EngineFailure, EngineRequest, EngineRun, EngineState

_FAILURE_MESSAGE_LIMIT = 500
_STDOUT_LIMIT = 1024 * 1024
_STDERR_LIMIT = 1024 * 1024
_SARIF_LIMIT = 16 * 1024 * 1024
_VERSION_TIMEOUT_SECONDS = 5
_PIPE_CHUNK_SIZE = 64 * 1024
_REAP_TIMEOUT_SECONDS = 1.0
_TRUNCATION_MARKER = "[truncated by rtl-lens]"


class _AdapterFailure(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class _ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    overflow_stream: Literal["stdout", "stderr"] | None = None


@dataclass
class _PipeCapture:
    content: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    error: Exception | None = None


class _OverflowState:
    def __init__(self) -> None:
        self._lock = Lock()
        self.stream: Literal["stdout", "stderr"] | None = None

    def record(self, stream: Literal["stdout", "stderr"]) -> None:
        with self._lock:
            if self.stream is None:
                self.stream = stream


class VerilatorEngine:
    """Translate Verilator SARIF into the shared analysis-engine contract."""

    name = "verilator"

    def __init__(self, executable: Path | None = None) -> None:
        self._executable = _normalized_executable(executable)

    def available(self) -> bool:
        """Return whether the configured executable can be resolved without running it."""
        if self._executable is None:
            return shutil.which("verilator") is not None
        if self._executable.suffix.casefold() == ".py":
            return self._executable.is_file()
        if self._executable.is_absolute() or self._executable.parent != Path("."):
            return self._executable.is_file()
        return shutil.which(str(self._executable)) is not None

    def version(self) -> str:
        """Return the native version from a shell-free bounded invocation."""
        completed = _run_bounded_process(
            [*self._command_prefix(), "--version"],
            cwd=None,
            timeout_seconds=_VERSION_TIMEOUT_SECONDS,
            stdout_limit=_STDOUT_LIMIT,
            stderr_limit=_STDERR_LIMIT,
        )
        _raise_if_truncated(completed)
        if completed.returncode != 0:
            raise _AdapterFailure(
                "version_failure",
                f"Verilator --version exited with code {completed.returncode}",
            )
        output = _decode_output(completed.stdout).strip()
        prefix = "Verilator "
        if not output.startswith(prefix) or not output.removeprefix(prefix).strip():
            raise _AdapterFailure("version_failure", "Verilator returned an invalid version")
        return output.removeprefix(prefix).strip()

    def run(self, request: EngineRequest) -> EngineRun:
        """Run Verilator without a shell and contain every adapter exception as data."""
        started = perf_counter()
        version: str | None = None
        try:
            version = self.version()
            diagnostics = self._analyze(request)
            return EngineRun(
                engine=self.name,
                state=EngineState.COMPLETED,
                version=version,
                diagnostics=diagnostics,
                duration_ms=_elapsed_ms(started),
            )
        except Exception as error:  # noqa: BLE001 - adapter exceptions never cross this boundary.
            return EngineRun(
                engine=self.name,
                state=EngineState.FAILED,
                version=version,
                failure=EngineFailure(
                    kind=_failure_kind(error),
                    message=_bounded_failure_message(error),
                    required=True,
                ),
                duration_ms=_elapsed_ms(started),
            )

    def _analyze(self, request: EngineRequest) -> tuple[RawDiagnostic, ...]:
        root = request.project.root.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"project root does not exist: {root}")

        defines = [f"-D{define}" for define in sorted(request.project.defines)]
        include_dirs = [
            f"-I{_validated_project_path(path, root, directory=True)}"
            for path in sorted(request.project.include_dirs, key=lambda item: item.as_posix())
        ]
        sources = [
            _validated_project_path(path, root, directory=False)
            for path in sorted(request.project.sources, key=lambda item: item.as_posix())
        ]

        with TemporaryDirectory(prefix="rtl-lens-verilator-") as temporary_directory:
            sarif_path = Path(temporary_directory) / "diagnostics.sarif.json"
            arguments = [
                *self._command_prefix(),
                "--lint-only",
                "--diagnostics-sarif-output",
                str(sarif_path),
                "--Wall",
                *defines,
                *include_dirs,
                *sources,
            ]
            completed = _run_bounded_process(
                arguments,
                cwd=root,
                timeout_seconds=request.timeout_seconds,
                stdout_limit=_STDOUT_LIMIT,
                stderr_limit=_STDERR_LIMIT,
            )
            _raise_if_truncated(completed)
            payload = _read_sarif(sarif_path)
            return parse_verilator_sarif(payload, root)

    def _command_prefix(self) -> list[str]:
        executable = self._executable or Path(shutil.which("verilator") or "verilator")
        if executable.suffix.casefold() == ".py":
            if not executable.is_file():
                raise FileNotFoundError(f"Verilator executable does not exist: {executable}")
            return [sys.executable, str(executable.resolve())]
        return [str(executable)]


def _normalized_executable(executable: Path | None) -> Path | None:
    if executable is None:
        return None
    if (
        executable.suffix.casefold() == ".py"
        or executable.is_absolute()
        or executable.parent != Path(".")
    ):
        return executable.resolve()
    return executable


def _validated_project_path(path: Path, root: Path, *, directory: bool) -> str:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise _AdapterFailure(
            "path_escape",
            f"Verilator path must resolve beneath the project root: {path}",
        )
    if directory:
        if not resolved.is_dir():
            raise FileNotFoundError(f"Verilator include directory does not exist: {path}")
    elif not resolved.is_file():
        raise FileNotFoundError(f"Verilator source does not exist: {path}")
    relative_path = resolved.relative_to(root).as_posix()
    if not directory and relative_path.startswith(("-", "+")):
        return f"./{relative_path}"
    return relative_path


def _read_sarif(sarif_path: Path) -> Mapping[str, object]:
    if not sarif_path.is_file():
        raise _AdapterFailure("missing_sarif", "Verilator did not produce a SARIF file")
    if sarif_path.stat().st_size > _SARIF_LIMIT:
        raise _AdapterFailure(
            "sarif_limit_exceeded",
            f"Verilator SARIF exceeded the {_SARIF_LIMIT}-byte limit",
        )
    with sarif_path.open("rb") as sarif_file:
        content = sarif_file.read(_SARIF_LIMIT + 1)
    if len(content) > _SARIF_LIMIT:
        raise _AdapterFailure(
            "sarif_limit_exceeded",
            f"Verilator SARIF exceeded the {_SARIF_LIMIT}-byte limit",
        )
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _AdapterFailure("malformed_sarif", "Verilator produced malformed SARIF") from error
    if not isinstance(payload, Mapping):
        raise _AdapterFailure("malformed_sarif", "Verilator SARIF must be a JSON object")
    return cast(Mapping[str, object], payload)


def _run_bounded_process(
    arguments: list[str],
    *,
    cwd: Path | None,
    timeout_seconds: float,
    stdout_limit: int,
    stderr_limit: int,
) -> _ProcessResult:
    process = subprocess.Popen(
        arguments,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        text=False,
        bufsize=0,
    )
    if process.stdout is None or process.stderr is None:
        _safe_kill(process)
        try:
            _safe_reap(process)
        finally:
            if process.stdout is not None:
                _close_pipe(process.stdout)
            if process.stderr is not None:
                _close_pipe(process.stderr)
        raise _AdapterFailure("subprocess_setup_failure", "Verilator pipes are unavailable")

    stdout_capture: _PipeCapture | None = None
    stderr_capture: _PipeCapture | None = None
    overflow: _OverflowState | None = None
    readers: tuple[Thread, ...] = ()
    started_readers: list[Thread] = []
    try:
        stdout_capture = _PipeCapture()
        stderr_capture = _PipeCapture()
        overflow = _OverflowState()
        readers = (
            Thread(
                target=_read_pipe,
                args=(
                    process.stdout,
                    stdout_limit,
                    stdout_capture,
                    process,
                    "stdout",
                    overflow,
                ),
                daemon=True,
                name="rtl-lens-verilator-stdout",
            ),
            Thread(
                target=_read_pipe,
                args=(
                    process.stderr,
                    stderr_limit,
                    stderr_capture,
                    process,
                    "stderr",
                    overflow,
                ),
                daemon=True,
                name="rtl-lens-verilator-stderr",
            ),
        )
        for reader in readers:
            reader.start()
            started_readers.append(reader)
    except BaseException as error:
        _safe_kill(process)
        try:
            _safe_reap(process)
        finally:
            _close_pipe(process.stdout)
            _close_pipe(process.stderr)
            for reader in started_readers:
                reader.join(_REAP_TIMEOUT_SECONDS)
        if any(reader.is_alive() for reader in started_readers):
            raise _AdapterFailure(
                "subprocess_cleanup_failure",
                "Verilator pipe reader survived partial startup cleanup",
            ) from error
        raise

    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _safe_kill(process)
        _safe_reap(process)
    except BaseException:
        _safe_kill(process)
        _safe_reap(process)
        raise
    finally:
        for reader in readers:
            reader.join(_REAP_TIMEOUT_SECONDS)
        if any(reader.is_alive() for reader in readers):
            _close_pipe(process.stdout)
            _close_pipe(process.stderr)
            for reader in readers:
                reader.join(_REAP_TIMEOUT_SECONDS)
    if any(reader.is_alive() for reader in readers):
        raise _AdapterFailure(
            "subprocess_cleanup_failure",
            "Verilator pipe readers did not stop after process cleanup",
        )
    if timed_out:
        raise _AdapterFailure(
            "timeout",
            f"Verilator exceeded the {timeout_seconds:g}s subprocess timeout",
        )
    reader_error = stdout_capture.error or stderr_capture.error
    if reader_error is not None and overflow.stream is None:
        raise _AdapterFailure(
            "subprocess_reader_failure",
            f"Verilator pipe reader failed: {type(reader_error).__name__}",
        ) from reader_error
    return _ProcessResult(
        returncode=process.returncode,
        stdout=bytes(stdout_capture.content),
        stderr=bytes(stderr_capture.content),
        stdout_truncated=stdout_capture.truncated,
        stderr_truncated=stderr_capture.truncated,
        overflow_stream=overflow.stream,
    )


def _read_pipe(
    stream: IO[bytes],
    limit: int,
    capture: _PipeCapture,
    process: subprocess.Popen[bytes],
    stream_name: Literal["stdout", "stderr"],
    overflow: _OverflowState,
) -> None:
    try:
        while chunk := stream.read(_PIPE_CHUNK_SIZE):
            remaining = max(0, limit - len(capture.content))
            capture.content.extend(chunk[:remaining])
            if len(chunk) > remaining:
                capture.truncated = True
                overflow.record(stream_name)
                _safe_kill(process)
    except Exception as error:  # noqa: BLE001 - reader failures become bounded adapter data.
        capture.error = error
        _safe_kill(process)
    finally:
        _close_pipe(stream)


def _safe_kill(process: subprocess.Popen[bytes]) -> None:
    try:
        process.kill()
    except OSError:
        pass


def _safe_reap(process: subprocess.Popen[bytes]) -> None:
    try:
        process.wait(timeout=_REAP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise _AdapterFailure(
            "subprocess_cleanup_failure",
            "Verilator did not exit after being killed",
        ) from error


def _close_pipe(stream: IO[bytes]) -> None:
    try:
        stream.close()
    except OSError:
        pass


def _raise_if_truncated(result: _ProcessResult) -> None:
    stream = result.overflow_stream
    if stream is None:
        stream = (
            "stdout" if result.stdout_truncated else "stderr" if result.stderr_truncated else None
        )
    if stream is not None:
        limit = _STDOUT_LIMIT if stream == "stdout" else _STDERR_LIMIT
        raise _AdapterFailure(
            f"{stream}_limit_exceeded",
            f"Verilator {stream} exceeded the {limit}-byte limit; {_TRUNCATION_MARKER}",
        )


def _decode_output(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")


def _failure_kind(error: Exception) -> str:
    if isinstance(error, (_AdapterFailure, SarifAdapterError)):
        return error.kind
    return type(error).__name__


def _bounded_failure_message(error: Exception) -> str:
    try:
        message = str(error).strip() or type(error).__name__
    except Exception:  # noqa: BLE001 - failure rendering must be total.
        message = f"{type(error).__name__} (message unavailable)"
    return message[:_FAILURE_MESSAGE_LIMIT]


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))
