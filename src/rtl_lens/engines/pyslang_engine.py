"""Isolated analysis through PySlang's supported public API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from multiprocessing import get_context
from multiprocessing.process import BaseProcess
from multiprocessing.process import (  # type: ignore[attr-defined]
    _children as _multiprocessing_children,
)
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from threading import Thread
from time import perf_counter, sleep
from typing import cast

import pyslang
from pydantic import BaseModel, ConfigDict
from pyslang import (  # type: ignore[attr-defined]
    Bag,
    Diagnostic,
    DiagnosticEngine,
    DiagnosticSeverity,
    SourceManager,
)
from pyslang.ast import (  # type: ignore[import-not-found]
    Compilation,
    CompilationOptions,
    DefinitionKind,
    DefinitionSymbol,
)
from pyslang.parsing import PreprocessorOptions  # type: ignore[import-not-found]
from pyslang.syntax import SyntaxTree  # type: ignore[import-not-found]

from rtl_lens.analysis.module_graph import build_module_graph
from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph
from rtl_lens.models.diagnostic import RawDiagnostic, Severity, SourceLocation
from rtl_lens.models.engine import EngineFailure, EngineRequest, EngineRun, EngineState

_FAILURE_MESSAGE_LIMIT = 500
_DIAGNOSTIC_LIMIT = 10_000
_DIAGNOSTIC_MESSAGE_LIMIT = 4_096
_TRUNCATION_MARKER = "[truncated by rtl-lens]"
_GRAPH_ARTIFACT_LIMIT = 16 * 1024 * 1024
_RESULT_FILE_LIMIT = 64 * 1024 * 1024
_TERMINATE_GRACE_SECONDS = 0.25
_KILL_GRACE_SECONDS = 0.25
_REAPER_POLL_SECONDS = 0.25


class _WorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    diagnostics: tuple[RawDiagnostic, ...] = ()
    module_graph: ModuleGraph | None = None
    analysis_warnings: tuple[AnalysisWarning, ...] = ()
    failure_kind: str | None = None
    failure_message: str | None = None


class _AdapterFailure(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(eq=False)
class _ReaperOwnership:
    process: BaseProcess
    temporary_directory: Path


_reaper_owners: set[_ReaperOwnership] = set()
_cleanup_owners: set[Path] = set()


class PySlangEngine:
    """Translate native PySlang diagnostics into the RTL Lens engine contract."""

    name = "pyslang"

    def version(self) -> str:
        """Return the installed PySlang package version."""
        return cast(str, pyslang.__version__)

    def available(self) -> bool:
        """Return true because importing this adapter loaded the required bindings."""
        return True

    def run(self, request: EngineRequest) -> EngineRun:
        """Analyze all resolved sources and contain Python exceptions as failures."""
        started = perf_counter()
        try:
            version = self.version()
            result = self._analyze(request)
            return EngineRun(
                engine=self.name,
                state=EngineState.COMPLETED,
                version=version,
                diagnostics=result.diagnostics,
                duration_ms=_elapsed_ms(started),
                module_graph=result.module_graph,
                analysis_warnings=result.analysis_warnings,
            )
        except Exception as error:  # noqa: BLE001 - this is the adapter exception boundary.
            return EngineRun(
                engine=self.name,
                state=EngineState.FAILED,
                version=_safe_version(self),
                failure=EngineFailure(
                    kind=error.kind if isinstance(error, _AdapterFailure) else type(error).__name__,
                    message=_bounded_failure_message(error),
                    required=True,
                ),
                duration_ms=_elapsed_ms(started),
            )

    def _analyze(self, request: EngineRequest) -> _WorkerResult:
        context = get_context("spawn")
        deadline = perf_counter() + request.timeout_seconds
        temporary_directory = Path(mkdtemp(prefix="rtl-lens-pyslang-"))
        process: BaseProcess | None = None
        started = False
        try:
            result_path = temporary_directory / "result.json"
            process = context.Process(
                target=_worker_main,
                args=(request.model_dump(mode="json"), str(result_path)),
                daemon=True,
            )
            process.start()
            started = True
            process.join(max(0.0, deadline - perf_counter()))
            if process.is_alive():
                raise _timeout_failure(request.timeout_seconds)
            if not result_path.is_file():
                raise _AdapterFailure(
                    "worker_failure",
                    f"pyslang worker exited with code {process.exitcode} without a result",
                )
            _ensure_before_deadline(deadline, request.timeout_seconds)
            result_payload = _read_result_file(result_path)
            _ensure_before_deadline(deadline, request.timeout_seconds)
            result = _validate_worker_result(result_payload)
            _ensure_before_deadline(deadline, request.timeout_seconds)
        finally:
            alive = process is not None and _close_process(process, started=started)
            if alive and process is not None:
                _transfer_process_ownership(process, temporary_directory)
            else:
                _cleanup_temporary_directory(temporary_directory)

        if result.failure_kind is not None:
            raise _AdapterFailure(
                result.failure_kind,
                result.failure_message or result.failure_kind,
            )
        return result


def _worker_main(request_payload: dict[str, object], result_path: str) -> None:
    """Run native PySlang analysis in a terminable, spawn-safe worker process."""
    try:
        request = EngineRequest.model_validate(request_payload)
        result = _analyze_native(request)
    except Exception as error:  # noqa: BLE001 - exceptions cross the worker boundary as data.
        result = _WorkerResult(
            failure_kind=(
                error.kind if isinstance(error, _AdapterFailure) else type(error).__name__
            ),
            failure_message=_bounded_failure_message(error),
        )
    Path(result_path).write_text(result.model_dump_json(), encoding="utf-8")


def _analyze_native(request: EngineRequest) -> _WorkerResult:
    root = request.project.root.resolve()
    source_manager = SourceManager()
    for include_dir in request.project.include_dirs:
        include_path = include_dir if include_dir.is_absolute() else root / include_dir
        source_manager.addUserDirectories(str(include_path))

    preprocessor_options = PreprocessorOptions()
    preprocessor_options.predefines = list(request.project.defines)
    syntax_options = Bag([preprocessor_options])

    compilation_options = CompilationOptions()
    compilation_options.topModules = set(request.project.top_modules)
    compilation = Compilation(Bag([compilation_options]))
    for source in request.project.sources:
        source_path = source if source.is_absolute() else root / source
        compilation.addSyntaxTree(
            SyntaxTree.fromFile(str(source_path), source_manager, syntax_options)
        )

    diagnostics = _convert_all_diagnostics(compilation, root)
    try:
        module_graph = build_module_graph(
            tuple(json.loads(tree.root.to_json()) for tree in compilation.getSyntaxTrees()),
            frozenset(
                definition.name
                for definition in compilation.getDefinitions()
                if isinstance(definition, DefinitionSymbol)
                and definition.definitionKind
                in {
                    DefinitionKind.Module,
                    DefinitionKind.Interface,
                    DefinitionKind.Program,
                }
            ),
        )
        graph_size = len(module_graph.model_dump_json().encode("utf-8"))
        if graph_size > _GRAPH_ARTIFACT_LIMIT:
            return _WorkerResult(
                diagnostics=diagnostics,
                analysis_warnings=(
                    AnalysisWarning(
                        kind="module_graph_limit",
                        message=(
                            f"module graph artifact exceeded the {_GRAPH_ARTIFACT_LIMIT}-byte limit"
                        ),
                    ),
                ),
            )
    except Exception as error:  # noqa: BLE001 - graph degradation retains diagnostics.
        return _WorkerResult(
            diagnostics=diagnostics,
            analysis_warnings=(
                AnalysisWarning(
                    kind="module_graph",
                    message=_bounded_failure_message(error),
                ),
            ),
        )
    return _WorkerResult(diagnostics=diagnostics, module_graph=module_graph)


def _convert_all_diagnostics(
    compilation: Compilation,
    project_root: Path,
) -> tuple[RawDiagnostic, ...]:
    diagnostic_engine = DiagnosticEngine(compilation.sourceManager)
    converted: list[RawDiagnostic] = []
    for diagnostic in compilation.getAllDiagnostics():
        if len(converted) == _DIAGNOSTIC_LIMIT:
            raise _AdapterFailure(
                "diagnostic_limit_exceeded",
                f"pyslang produced more than {_DIAGNOSTIC_LIMIT} diagnostics",
            )
        converted.append(
            _convert_diagnostic(
                diagnostic,
                diagnostic_engine=diagnostic_engine,
                source_manager=compilation.sourceManager,
                project_root=project_root,
                engine_version=cast(str, pyslang.__version__),
            )
        )
    return tuple(converted)


def _convert_diagnostic(
    diagnostic: Diagnostic,
    *,
    diagnostic_engine: DiagnosticEngine,
    source_manager: SourceManager,
    project_root: Path,
    engine_version: str,
) -> RawDiagnostic:
    location = diagnostic.location
    source_path = Path(source_manager.getFullPath(location.buffer)).resolve()
    relative_path = source_path.relative_to(project_root).as_posix()
    original_code = diagnostic_engine.getOptionName(diagnostic.code) or str(diagnostic.code)
    native_severity = diagnostic_engine.getSeverity(diagnostic.code, location)
    return RawDiagnostic(
        engine="pyslang",
        engine_version=engine_version,
        original_code=original_code,
        severity=_convert_severity(native_severity),
        location=SourceLocation(
            path=relative_path,
            line=source_manager.getLineNumber(location),
            column=source_manager.getColumnNumber(location),
        ),
        message=_bounded_diagnostic_message(diagnostic_engine.formatMessage(diagnostic)),
    )


def _convert_severity(severity: DiagnosticSeverity) -> Severity:
    if severity in (DiagnosticSeverity.Error, DiagnosticSeverity.Fatal):
        return Severity.ERROR
    if severity is DiagnosticSeverity.Warning:
        return Severity.WARNING
    return Severity.INFO


def _bounded_failure_message(error: Exception) -> str:
    try:
        message = str(error).strip() or type(error).__name__
    except Exception:  # noqa: BLE001 - exception formatting must also be total.
        message = f"{type(error).__name__} (message unavailable)"
    return message[:_FAILURE_MESSAGE_LIMIT]


def _bounded_diagnostic_message(message: str) -> str:
    if len(message) <= _DIAGNOSTIC_MESSAGE_LIMIT:
        return message
    prefix_length = _DIAGNOSTIC_MESSAGE_LIMIT - len(_TRUNCATION_MARKER)
    return message[:prefix_length] + _TRUNCATION_MARKER


def _safe_version(engine: PySlangEngine) -> str | None:
    try:
        return engine.version()
    except Exception:  # noqa: BLE001 - failure rendering cannot call back into a broken provider.
        return None


def _timeout_failure(timeout_seconds: int) -> _AdapterFailure:
    return _AdapterFailure(
        "timeout",
        f"pyslang exceeded the {timeout_seconds}s analysis timeout",
    )


def _ensure_before_deadline(deadline: float, timeout_seconds: int) -> None:
    if perf_counter() >= deadline:
        raise _timeout_failure(timeout_seconds)


def _read_result_file(result_path: Path) -> bytes:
    if result_path.stat().st_size > _RESULT_FILE_LIMIT:
        raise _AdapterFailure(
            "transport_limit_exceeded",
            f"pyslang worker result exceeded the {_RESULT_FILE_LIMIT}-byte transport limit",
        )
    with result_path.open("rb") as result_file:
        payload = result_file.read(_RESULT_FILE_LIMIT + 1)
    if len(payload) > _RESULT_FILE_LIMIT:
        raise _AdapterFailure(
            "transport_limit_exceeded",
            f"pyslang worker result exceeded the {_RESULT_FILE_LIMIT}-byte transport limit",
        )
    return payload


def _validate_worker_result(payload: bytes) -> _WorkerResult:
    return _WorkerResult.model_validate_json(payload)


def _close_process(process: BaseProcess, *, started: bool) -> bool:
    """Stop a child within fixed graces and report whether ownership must transfer."""
    if not started:
        _safe_close_process(process)
        return False
    alive = _process_is_alive(process)
    if alive:
        _safe_terminate_process(process)
        _safe_join_process(process, _TERMINATE_GRACE_SECONDS)
        alive = _process_is_alive(process)
    if alive:
        _safe_kill_process(process)
        _safe_join_process(process, _KILL_GRACE_SECONDS)
        alive = _process_is_alive(process)
    if not alive:
        _safe_close_process(process)
    return alive


def _process_is_alive(process: BaseProcess) -> bool:
    try:
        return process.is_alive()
    except Exception:  # noqa: BLE001 - cleanup errors cannot replace the scan result.
        return True


def _safe_terminate_process(process: BaseProcess) -> None:
    try:
        process.terminate()
    except Exception:  # noqa: BLE001,S110 - kill escalation still gets a chance.
        pass


def _safe_kill_process(process: BaseProcess) -> None:
    try:
        process.kill()
    except Exception:  # noqa: BLE001,S110 - ownership transfers if still alive.
        pass


def _safe_join_process(process: BaseProcess, timeout: float) -> None:
    try:
        process.join(timeout)
    except Exception:  # noqa: BLE001,S110 - preserve timeout reporting.
        pass


def _safe_close_process(process: BaseProcess) -> None:
    try:
        process.close()
    except Exception:  # noqa: BLE001,S110 - dead-handle cleanup is best effort.
        pass


def _cleanup_temporary_directory(temporary_directory: Path) -> None:
    try:
        rmtree(temporary_directory)
    except Exception:  # noqa: BLE001 - cleanup errors cannot replace engine results.
        if temporary_directory in _cleanup_owners:
            return
        _cleanup_owners.add(temporary_directory)
        try:
            Thread(
                target=_retry_temporary_directory_cleanup,
                args=(temporary_directory,),
                name="rtl-lens-temp-cleaner",
                daemon=True,
            ).start()
        except Exception:  # noqa: BLE001,S110 - global ownership remains explicit.
            pass


def _retry_temporary_directory_cleanup(temporary_directory: Path) -> None:
    while temporary_directory.exists():
        try:
            rmtree(temporary_directory)
        except Exception:  # noqa: BLE001 - retry without blocking interpreter exit.
            sleep(_REAPER_POLL_SECONDS)
    _cleanup_owners.discard(temporary_directory)


def _detach_process_from_shutdown(process: BaseProcess) -> None:
    # multiprocessing has no public API for transferring shutdown ownership. Discarding this
    # single child is the minimum compatibility shim that prevents its private atexit join.
    _multiprocessing_children.discard(process)


def _transfer_process_ownership(
    process: BaseProcess,
    temporary_directory: Path,
) -> None:
    """Move an unreaped child and its directory to a non-blocking daemon reaper."""
    _detach_process_from_shutdown(process)
    ownership = _ReaperOwnership(process, temporary_directory)
    _reaper_owners.add(ownership)
    try:
        Thread(
            target=_reap_process,
            args=(ownership,),
            name="rtl-lens-pyslang-reaper",
            daemon=True,
        ).start()
    except Exception:  # noqa: BLE001,S110 - global ownership remains explicit.
        pass


def _reap_process(ownership: _ReaperOwnership) -> None:
    while _process_is_alive(ownership.process):
        try:
            ownership.process.join(_REAPER_POLL_SECONDS)
        except Exception:  # noqa: BLE001 - keep polling without busy-spinning.
            sleep(_REAPER_POLL_SECONDS)
    _safe_close_process(ownership.process)
    _cleanup_temporary_directory(ownership.temporary_directory)
    _reaper_owners.discard(ownership)


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))
