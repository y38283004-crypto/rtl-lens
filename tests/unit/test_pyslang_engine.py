"""Behavior tests for the isolated PySlang adapter."""

import os
import signal
from multiprocessing import active_children
from pathlib import Path
from shutil import rmtree
from time import monotonic, sleep
from typing import Any

import pytest

import rtl_lens.engines.pyslang_engine as pyslang_engine_module
from rtl_lens.engines.pyslang_engine import PySlangEngine
from rtl_lens.models.analysis import ModuleGraph
from rtl_lens.models.diagnostic import Severity
from rtl_lens.models.engine import EngineRequest, EngineState
from rtl_lens.models.project import ResolvedProject

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "projects" / "pyslang_error"
OPTIONS_ROOT = Path(__file__).parents[1] / "fixtures" / "projects" / "pyslang_options"


def _sleeping_worker(_payload: dict[str, Any], _result_queue: Any) -> None:
    sleep(60)


def _stubborn_worker(_payload: dict[str, Any], _result_path: str) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    sleep(60)


def _oversized_result_worker(_payload: dict[str, Any], result_path: str) -> None:
    with Path(result_path).open("wb") as result_file:
        result_file.truncate(64 * 1024 * 1024 + 1)


class _StubbornProcess:
    def __init__(self) -> None:
        self._alive = iter((True, True, False))
        self.join_timeouts: list[float | None] = []
        self.terminated = False
        self.killed = False
        self.closed = False

    def is_alive(self) -> bool:
        return next(self._alive)

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)

    def close(self) -> None:
        self.closed = True


class _AlwaysAliveProcess(_StubbornProcess):
    exitcode = None

    def start(self) -> None:
        pass

    def is_alive(self) -> bool:
        return True


class _FakeContext:
    def __init__(self, process: _AlwaysAliveProcess) -> None:
        self.process = process

    def Process(self, **_kwargs: Any) -> _AlwaysAliveProcess:
        return self.process


class _UnprintableError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("stringification failed")


def _hierarchy_project(tmp_path: Path) -> ResolvedProject:
    source = tmp_path / "top.sv"
    source.write_text(
        """
module alu; endmodule
module top;
  logic [3:0] narrow;
  assign narrow = 8'hff;
  alu first();
  alu duplicate();
  generate
    if (1) begin : generated
      missing_ip nested();
    end
  endgenerate
endmodule
""",
        encoding="utf-8",
    )
    return ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))


def _udp_project(tmp_path: Path) -> ResolvedProject:
    source = tmp_path / "top.sv"
    source.write_text(
        """
primitive udp_and(out, a, b);
  output out;
  input a, b;
  table
    11 : 1;
    0? : 0;
    ?0 : 0;
  endtable
endprimitive
module child; endmodule
module top;
  logic a, b, out;
  udp_and udp_instance(out, a, b);
  child u_child();
endmodule
""",
        encoding="utf-8",
    )
    return ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))


def test_pyslang_engine_returns_observed_structured_diagnostic() -> None:
    """Dropping PySlang's native code, location, or message must break the adapter contract."""
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.COMPLETED
    assert result.engine == "pyslang"
    assert result.failure is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.engine == "pyslang"
    assert diagnostic.original_code == "constant-conversion"
    assert diagnostic.severity is Severity.WARNING
    assert diagnostic.location.path == "top.sv"
    assert diagnostic.location.line == 3
    assert diagnostic.location.column == 16
    assert diagnostic.message == (
        "implicit conversion from 'logic[7:0]' to 'logic[3:0]' changes value from 8'd255 to 4'b1111"
    )


def test_pyslang_engine_returns_graph_and_diagnostics_from_one_worker_scan(
    tmp_path: Path,
) -> None:
    """The worker must carry a canonical graph beside diagnostics from the same scan."""
    result = PySlangEngine().run(
        EngineRequest(project=_hierarchy_project(tmp_path), timeout_seconds=10)
    )

    assert result.state is EngineState.COMPLETED
    assert result.diagnostics
    assert result.module_graph == ModuleGraph(
        nodes=("alu", "missing_ip", "top"),
        edges=(("top", "alu"), ("top", "missing_ip")),
        unresolved=("missing_ip",),
    )
    assert result.analysis_warnings == ()


def test_pyslang_engine_preserves_graph_when_project_contains_udp(
    tmp_path: Path,
) -> None:
    """A UDP definition must not degrade the ordinary module graph or primary result."""
    result = PySlangEngine().run(EngineRequest(project=_udp_project(tmp_path), timeout_seconds=10))

    assert result.state is EngineState.COMPLETED
    assert result.failure is None
    assert result.diagnostics == ()
    assert result.module_graph == ModuleGraph(
        nodes=("child", "top", "udp_and"),
        edges=(("top", "child"), ("top", "udp_and")),
        unresolved=("udp_and",),
    )
    assert result.analysis_warnings == ()


def test_native_analysis_builds_graph_without_a_second_compilation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Graph extraction must reuse the one compilation and each source tree added to it."""
    original_compilation = pyslang_engine_module.Compilation
    original_from_file = pyslang_engine_module.SyntaxTree.fromFile
    compilation_count = 0
    from_file_count = 0
    add_tree_count = 0

    class CountingCompilation:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            nonlocal compilation_count
            compilation_count += 1
            self._inner = original_compilation(*args, **kwargs)

        def addSyntaxTree(self, tree: Any) -> None:
            nonlocal add_tree_count
            add_tree_count += 1
            self._inner.addSyntaxTree(tree)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

    class CountingSyntaxTree:
        @staticmethod
        def fromFile(*args: Any, **kwargs: Any) -> Any:
            nonlocal from_file_count
            from_file_count += 1
            return original_from_file(*args, **kwargs)

    monkeypatch.setattr(pyslang_engine_module, "Compilation", CountingCompilation)
    monkeypatch.setattr(pyslang_engine_module, "SyntaxTree", CountingSyntaxTree)
    project = _hierarchy_project(tmp_path)

    native = pyslang_engine_module._analyze_native(
        EngineRequest(project=project, timeout_seconds=10)
    )

    assert native.module_graph is not None
    assert compilation_count == 1
    assert from_file_count == len(project.sources)
    assert add_tree_count == len(project.sources)


def test_graph_failure_retains_diagnostics_and_completed_artifact_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Graph degradation must not discard diagnostics or become an adapter failure."""

    def raise_graph_error(*_args: Any, **_kwargs: Any) -> ModuleGraph:
        raise RuntimeError("x" * 1_000)

    monkeypatch.setattr(
        pyslang_engine_module,
        "build_module_graph",
        raise_graph_error,
        raising=False,
    )
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    native = pyslang_engine_module._analyze_native(
        EngineRequest(project=project, timeout_seconds=10)
    )

    assert native.diagnostics
    assert native.module_graph is None
    assert len(native.analysis_warnings) == 1
    assert native.analysis_warnings[0].kind == "module_graph"
    assert native.analysis_warnings[0].message == "x" * 500


def test_graph_failure_warning_handles_unprintable_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warning construction must stay total when graph exception formatting fails."""

    def raise_unprintable(*_args: Any, **_kwargs: Any) -> ModuleGraph:
        raise _UnprintableError()

    monkeypatch.setattr(
        pyslang_engine_module,
        "build_module_graph",
        raise_unprintable,
        raising=False,
    )
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    native = pyslang_engine_module._analyze_native(
        EngineRequest(project=project, timeout_seconds=10)
    )

    assert native.module_graph is None
    assert len(native.analysis_warnings) == 1
    warning = native.analysis_warnings[0]
    assert warning.kind == "module_graph"
    assert 0 < len(warning.message) <= 500
    assert "message unavailable" in warning.message


def test_oversized_graph_is_omitted_without_discarding_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The independent 16 MiB graph cap must degrade only the graph artifact."""
    oversized_graph = ModuleGraph(nodes=("x" * (16 * 1024 * 1024),))
    monkeypatch.setattr(
        pyslang_engine_module,
        "build_module_graph",
        lambda *_args, **_kwargs: oversized_graph,
        raising=False,
    )
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    native = pyslang_engine_module._analyze_native(
        EngineRequest(project=project, timeout_seconds=10)
    )

    assert native.diagnostics
    assert native.module_graph is None
    assert len(native.analysis_warnings) == 1
    assert native.analysis_warnings[0].kind == "module_graph_limit"


def test_pyslang_engine_enforces_hard_timeout_and_reaps_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stuck native call must terminate promptly without leaving a live child process."""
    monkeypatch.setattr(pyslang_engine_module, "_worker_main", _sleeping_worker, raising=False)
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))
    children_before = {child.pid for child in active_children()}
    started = monotonic()

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=1))

    assert monotonic() - started < 5
    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "timeout"
    assert {child.pid for child in active_children()} <= children_before


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM ignore semantics require POSIX")
def test_pyslang_engine_kills_worker_that_ignores_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real POSIX child that ignores terminate must still be killed and reaped promptly."""
    monkeypatch.setattr(pyslang_engine_module, "_worker_main", _stubborn_worker)
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))
    children_before = {child.pid for child in active_children()}
    started = monotonic()

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=1))

    assert monotonic() - started < 3
    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "timeout"
    assert {child.pid for child in active_children()} <= children_before


def test_worker_cleanup_uses_only_bounded_joins_and_escalates_to_kill() -> None:
    """Cleanup must never wait indefinitely when terminate does not stop the worker."""
    process = _StubbornProcess()

    pyslang_engine_module._close_process(process, started=True)  # type: ignore[arg-type]

    assert process.terminated is True
    assert process.killed is True
    assert process.join_timeouts == [0.25, 0.25]
    assert process.closed is True


def test_timeout_transfers_still_alive_process_and_tempdir_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unkillable child must not destabilize timeout or trigger main-path temp cleanup."""
    process = _AlwaysAliveProcess()
    transferred: list[tuple[Any, Path]] = []

    def capture_transfer(child: Any, temporary_directory: Path) -> None:
        transferred.append((child, temporary_directory))

    monkeypatch.setattr(pyslang_engine_module, "get_context", lambda _method: _FakeContext(process))
    monkeypatch.setattr(
        pyslang_engine_module,
        "_transfer_process_ownership",
        capture_transfer,
        raising=False,
    )
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=1))

    try:
        assert result.state is EngineState.FAILED
        assert result.failure is not None
        assert result.failure.kind == "timeout"
        assert process.join_timeouts[-2:] == [0.25, 0.25]
        assert process.closed is False
        assert len(transferred) == 1
        assert transferred[0][0] is process
        assert transferred[0][1].is_dir()
    finally:
        for _, temporary_directory in transferred:
            rmtree(temporary_directory, ignore_errors=True)


def test_detach_removes_process_from_interpreter_shutdown_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The daemon reaper, not multiprocessing shutdown, must own an unkillable child."""
    process = _AlwaysAliveProcess()
    registry: set[Any] = {process}
    monkeypatch.setattr(
        pyslang_engine_module,
        "_multiprocessing_children",
        registry,
        raising=False,
    )

    pyslang_engine_module._detach_process_from_shutdown(process)  # type: ignore[arg-type]

    assert process not in registry


def test_temporary_directory_cleanup_retries_without_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A transient cleanup error must transfer ownership to a daemon retry."""
    temporary_directory = tmp_path / "worker-result"
    temporary_directory.mkdir()
    original_rmtree = rmtree
    attempts = 0

    def flaky_rmtree(path: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("worker still releasing file")
        original_rmtree(path)

    monkeypatch.setattr(pyslang_engine_module, "rmtree", flaky_rmtree)

    pyslang_engine_module._cleanup_temporary_directory(temporary_directory)

    deadline = monotonic() + 2
    while temporary_directory.exists() and monotonic() < deadline:
        sleep(0.01)
    assert attempts >= 2
    assert not temporary_directory.exists()


def test_pyslang_engine_rejects_oversized_worker_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A result larger than 64 MiB must be rejected before parsing."""
    monkeypatch.setattr(pyslang_engine_module, "_worker_main", _oversized_result_worker)
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "transport_limit_exceeded"


def test_pyslang_engine_rechecks_deadline_after_result_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A result read that crosses the deadline must return timeout, not late success."""
    original_read = Path.read_bytes

    def slow_read(path: Path) -> bytes:
        sleep(1.1)
        return original_read(path)

    monkeypatch.setattr(pyslang_engine_module, "_read_result_file", slow_read, raising=False)
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=1))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "timeout"


def test_pyslang_engine_rechecks_deadline_after_result_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation that crosses the deadline must return timeout, not late success."""
    original_validate = pyslang_engine_module._WorkerResult.model_validate_json

    def slow_validate(payload: bytes) -> Any:
        sleep(1.1)
        return original_validate(payload)

    monkeypatch.setattr(
        pyslang_engine_module,
        "_validate_worker_result",
        slow_validate,
        raising=False,
    )
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=1))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "timeout"


def test_pyslang_engine_contains_version_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken version provider must become data instead of escaping the boundary."""
    engine = PySlangEngine()

    def fail_version() -> str:
        raise RuntimeError("version unavailable")

    monkeypatch.setattr(engine, "version", fail_version)
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = engine.run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.FAILED
    assert result.version is None
    assert result.failure is not None
    assert result.failure.kind == "RuntimeError"


def test_pyslang_engine_contains_unprintable_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even an exception whose __str__ raises must return a bounded failure record."""
    engine = PySlangEngine()

    def fail_analysis(_request: EngineRequest) -> tuple[Any, ...]:
        raise _UnprintableError()

    monkeypatch.setattr(engine, "_analyze", fail_analysis)
    project = ResolvedProject(root=FIXTURE_ROOT, sources=(Path("top.sv"),))

    result = engine.run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.FAILED
    assert result.failure is not None
    assert result.failure.kind == "_UnprintableError"
    assert 0 < len(result.failure.message) <= 500


def test_pyslang_engine_bounds_long_diagnostic_messages(tmp_path: Path) -> None:
    """Native messages longer than the transport cap must carry a truncation marker."""
    identifier = "missing_" + "x" * 5000
    source = tmp_path / "top.sv"
    source.write_text(
        f"`default_nettype none\nmodule top; assign {identifier} = 1'b1; endmodule\n",
        encoding="utf-8",
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.COMPLETED
    assert result.diagnostics
    assert all(len(diagnostic.message) <= 4096 for diagnostic in result.diagnostics)
    assert any(
        diagnostic.message.endswith("[truncated by rtl-lens]") for diagnostic in result.diagnostics
    )


def test_pyslang_engine_reports_diagnostic_count_overflow(tmp_path: Path) -> None:
    """More than 10,000 native diagnostics must return an observable bounded failure."""
    source = tmp_path / "top.sv"
    declarations = "\n".join(f"logic [3:0] value_{index};" for index in range(10_001))
    assignments = "\n".join(f"assign value_{index} = 8'hff;" for index in range(10_001))
    source.write_text(
        f"module top;\n{declarations}\n{assignments}\nendmodule\n",
        encoding="utf-8",
    )
    project = ResolvedProject(root=tmp_path, sources=(Path("top.sv"),))

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=30))

    assert result.state is EngineState.FAILED
    assert len(result.diagnostics) <= 10_000
    assert result.failure is not None
    assert result.failure.kind == "diagnostic_limit_exceeded"


def test_pyslang_engine_applies_include_directories() -> None:
    """Ignoring configured include paths must expose the fixture's missing-include errors."""
    root = OPTIONS_ROOT / "include"
    project = ResolvedProject(
        root=root,
        sources=(Path("top.sv"),),
        include_dirs=(Path("headers"),),
    )

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.COMPLETED
    assert result.diagnostics == ()


def test_pyslang_engine_applies_preprocessor_defines() -> None:
    """Ignoring configured defines must hide the fixture's selected narrow-width branch."""
    root = OPTIONS_ROOT / "define"
    project = ResolvedProject(
        root=root,
        sources=(Path("top.sv"),),
        defines=("RTL_LENS_NARROW",),
    )

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.COMPLETED
    assert [diagnostic.original_code for diagnostic in result.diagnostics] == [
        "constant-conversion"
    ]


def test_pyslang_engine_applies_top_module_selection() -> None:
    """Ignoring configured tops must elaborate the fixture's invalid unselected module."""
    root = OPTIONS_ROOT / "top"
    project = ResolvedProject(
        root=root,
        sources=(Path("top.sv"),),
        top_modules=("selected",),
    )

    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))

    assert result.state is EngineState.COMPLETED
    assert result.diagnostics == ()
