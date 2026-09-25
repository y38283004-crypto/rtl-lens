"""Adversarial process-boundary tests for hard-bounded Verilator execution."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from threading import Event
from time import perf_counter
from typing import Any, cast

import pytest

from rtl_lens.engines import verilator_engine
from rtl_lens.engines.verilator_engine import VerilatorEngine
from rtl_lens.models.engine import EngineRequest, EngineState
from rtl_lens.models.project import ResolvedProject

FAKE_VERILATOR = Path(__file__).parents[1] / "fixtures" / "bin" / "fake_verilator.py"


def _request(root: Path, mode: str, *, timeout: int = 4) -> EngineRequest:
    source = root / "top.sv"
    root.mkdir(parents=True, exist_ok=True)
    source.write_text("module top; endmodule\n", encoding="utf-8")
    project = ResolvedProject(
        root=root,
        sources=(Path("top.sv"),),
        defines=(f"RTL_LENS_MODE={mode}",),
    )
    return EngineRequest(project=project, timeout_seconds=timeout)


def test_production_does_not_use_posthoc_capture_output() -> None:
    source = inspect.getsource(verilator_engine)

    assert "subprocess.run(" not in source
    assert "capture_output=True" not in source


@pytest.mark.parametrize(
    ("mode", "kind"),
    (
        ("stdout-overflow-hang", "stdout_limit_exceeded"),
        ("stderr-overflow-hang", "stderr_limit_exceeded"),
    ),
)
def test_stream_overflow_kills_early_and_reports_a_bounded_truncation_marker(
    tmp_path: Path, mode: str, kind: str
) -> None:
    started = perf_counter()

    result = VerilatorEngine(FAKE_VERILATOR).run(_request(tmp_path, mode))
    elapsed = perf_counter() - started

    assert elapsed < 3
    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == kind
    assert result.failure.message.endswith("[truncated by rtl-lens]")
    assert len(result.failure.message) <= 500


def test_stdout_and_stderr_are_drained_concurrently_without_deadlock(tmp_path: Path) -> None:
    result = VerilatorEngine(FAKE_VERILATOR).run(
        _request(tmp_path, "dual-pipe-pressure", timeout=3)
    )

    assert result.state is EngineState.COMPLETED
    assert result.failure is None
    assert result.diagnostics


def test_version_and_analysis_use_binary_shell_free_pipes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []
    original_popen = subprocess.Popen

    def capture(arguments: list[str], **kwargs: object):
        calls.append((arguments, kwargs))
        return original_popen(arguments, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", capture)
    engine = VerilatorEngine(FAKE_VERILATOR)

    assert engine.version() == "5.040-fake"
    result = engine.run(_request(tmp_path, "ok", timeout=3))

    assert result.state is EngineState.COMPLETED
    assert len(calls) == 3
    for _arguments, options in calls:
        assert options["stdin"] is subprocess.DEVNULL
        assert options["stdout"] is subprocess.PIPE
        assert options["stderr"] is subprocess.PIPE
        assert options["shell"] is False
        assert options["text"] is False
        assert options["bufsize"] == 0
    assert calls[0][1]["cwd"] is None
    assert calls[-1][1]["cwd"] == tmp_path.resolve()


def test_timeout_kills_and_reaps_the_direct_child(tmp_path: Path, monkeypatch) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    def capture(arguments: list[str], **kwargs: object):
        process = original_popen(arguments, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", capture)

    result = VerilatorEngine(FAKE_VERILATOR).run(_request(tmp_path, "timeout", timeout=1))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "timeout"
    assert len(processes) == 2
    assert processes[-1].poll() is not None


def test_runner_retains_only_the_fixed_prefix_before_killing(tmp_path: Path) -> None:
    sarif_path = tmp_path / "unused.sarif.json"
    result = verilator_engine._run_bounded_process(
        [
            sys.executable,
            str(FAKE_VERILATOR.resolve()),
            "--lint-only",
            "--diagnostics-sarif-output",
            str(sarif_path),
            "-DRTL_LENS_MODE=stdout-overflow-hang",
            "top.sv",
        ],
        cwd=tmp_path,
        timeout_seconds=3,
        stdout_limit=4096,
        stderr_limit=4096,
    )

    assert result.stdout_truncated is True
    assert result.stderr_truncated is False
    assert len(result.stdout) == 4096
    assert len(result.stderr) <= 4096


def test_reader_failure_and_kill_race_are_captured_without_escaping() -> None:
    class BrokenStream:
        closed = False

        def read(self, _size: int) -> bytes:
            raise OSError("reader broke")

        def close(self) -> None:
            self.closed = True

    class ExitedProcess:
        kill_calls = 0

        def kill(self) -> None:
            self.kill_calls += 1
            raise OSError("already exited")

    stream = BrokenStream()
    process = ExitedProcess()
    capture = verilator_engine._PipeCapture()

    verilator_engine._read_pipe(
        cast(Any, stream),
        32,
        capture,
        cast(Any, process),
        "stdout",
        verilator_engine._OverflowState(),
    )

    assert isinstance(capture.error, OSError)
    assert process.kill_calls == 1
    assert stream.closed is True


def test_partial_reader_start_failure_kills_and_reaps_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen
    original_thread = verilator_engine.Thread
    thread_count = 0

    def capture_process(arguments: list[str], **kwargs: object):
        process = original_popen(arguments, **kwargs)
        processes.append(process)
        return process

    class FailedStart:
        def start(self) -> None:
            raise RuntimeError("thread start failed")

        def join(self, _timeout: float) -> None:
            return None

        def is_alive(self) -> bool:
            return False

    def thread_factory(*args: object, **kwargs: object):
        nonlocal thread_count
        thread_count += 1
        if thread_count == 2:
            return FailedStart()
        return original_thread(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", capture_process)
    monkeypatch.setattr(verilator_engine, "Thread", thread_factory)
    leaked = False
    try:
        with pytest.raises(RuntimeError, match="thread start failed"):
            verilator_engine._run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=None,
                timeout_seconds=3,
                stdout_limit=32,
                stderr_limit=32,
            )
        leaked = processes[-1].poll() is None
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

    assert leaked is False


def test_engine_contains_reader_failure_and_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    class BrokenPipe:
        def __init__(self, wrapped: Any) -> None:
            self._wrapped = wrapped

        def read(self, _size: int) -> bytes:
            raise OSError("reader broke")

        def close(self) -> None:
            self._wrapped.close()

    def capture(arguments: list[str], **kwargs: object):
        process = original_popen(arguments, **kwargs)
        processes.append(process)
        if len(processes) == 2:
            process.stdout = cast(Any, BrokenPipe(process.stdout))
        return process

    monkeypatch.setattr(subprocess, "Popen", capture)

    result = VerilatorEngine(FAKE_VERILATOR).run(_request(tmp_path, "ok", timeout=3))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "subprocess_reader_failure"
    assert len(result.failure.message) <= 500
    assert len(processes) == 2
    assert processes[-1].poll() is not None


def test_reap_failure_still_closes_blocked_pipe_readers(monkeypatch: pytest.MonkeyPatch) -> None:
    class BlockingPipe:
        def __init__(self) -> None:
            self.closed = False
            self._closed = Event()

        def read(self, _size: int) -> bytes:
            self._closed.wait(timeout=5)
            return b""

        def close(self) -> None:
            self.closed = True
            self._closed.set()

    class UnreapableProcess:
        def __init__(self) -> None:
            self.stdout = BlockingPipe()
            self.stderr = BlockingPipe()
            self.returncode = None
            self.kill_calls = 0

        def wait(self, timeout: float) -> int:
            raise subprocess.TimeoutExpired("fake", timeout)

        def kill(self) -> None:
            self.kill_calls += 1

    process = UnreapableProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)

    with pytest.raises(Exception) as captured:
        verilator_engine._run_bounded_process(
            ["fake"],
            cwd=None,
            timeout_seconds=0.01,
            stdout_limit=32,
            stderr_limit=32,
        )

    assert getattr(captured.value, "kind", None) == "subprocess_cleanup_failure"
    assert process.kill_calls == 1
    assert process.stdout.closed is True
    assert process.stderr.closed is True


def test_reader_constructor_failure_kills_reaps_and_closes_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen
    original_thread = verilator_engine.Thread
    constructor_count = 0

    def capture_process(arguments: list[str], **kwargs: object):
        process = original_popen(arguments, **kwargs)
        processes.append(process)
        return process

    def thread_factory(*args: object, **kwargs: object):
        nonlocal constructor_count
        constructor_count += 1
        if constructor_count == 2:
            raise RuntimeError("thread construction failed")
        return original_thread(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", capture_process)
    monkeypatch.setattr(verilator_engine, "Thread", thread_factory)
    leaked = False
    try:
        with pytest.raises(RuntimeError, match="thread construction failed"):
            verilator_engine._run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=None,
                timeout_seconds=3,
                stdout_limit=32,
                stderr_limit=32,
            )
        leaked = processes[-1].poll() is None
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

    assert leaked is False
    assert processes[-1].stdout is not None and processes[-1].stdout.closed
    assert processes[-1].stderr is not None and processes[-1].stderr.closed


def test_unavailable_single_pipe_branch_closes_the_other_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TrackingPipe:
        closed = False

        def close(self) -> None:
            self.closed = True

    class MissingStdoutProcess:
        stdout = None
        stderr = TrackingPipe()
        returncode = 0

        def kill(self) -> None:
            return None

        def wait(self, timeout: float) -> int:
            return 0

    process = MissingStdoutProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: process)

    with pytest.raises(Exception) as captured:
        verilator_engine._run_bounded_process(
            ["fake"],
            cwd=None,
            timeout_seconds=1,
            stdout_limit=32,
            stderr_limit=32,
        )

    assert getattr(captured.value, "kind", None) == "subprocess_setup_failure"
    assert process.stderr.closed is True


def test_simultaneous_overflow_reports_the_recorded_first_stream() -> None:
    result = verilator_engine._ProcessResult(
        returncode=-1,
        stdout=b"x",
        stderr=b"x",
        stdout_truncated=True,
        stderr_truncated=True,
        overflow_stream="stderr",
    )

    with pytest.raises(Exception) as captured:
        verilator_engine._raise_if_truncated(result)

    assert getattr(captured.value, "kind", None) == "stderr_limit_exceeded"


def test_overflow_state_constructor_failure_cleans_all_process_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen

    def capture_process(arguments: list[str], **kwargs: object):
        process = original_popen(arguments, **kwargs)
        processes.append(process)
        return process

    def fail_overflow_state() -> None:
        raise RuntimeError("overflow state construction failed")

    monkeypatch.setattr(subprocess, "Popen", capture_process)
    monkeypatch.setattr(verilator_engine, "_OverflowState", fail_overflow_state)
    leaked = False
    try:
        with pytest.raises(RuntimeError, match="overflow state construction failed"):
            verilator_engine._run_bounded_process(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=None,
                timeout_seconds=3,
                stdout_limit=32,
                stderr_limit=32,
            )
        leaked = processes[-1].poll() is None
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

    assert leaked is False
    assert processes[-1].stdout is not None and processes[-1].stdout.closed
    assert processes[-1].stderr is not None and processes[-1].stderr.closed
