"""Deterministic orchestration for analysis-engine scans."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from rtl_lens.analysis.trends import summarize_trends
from rtl_lens.config import config_digest
from rtl_lens.diagnostics import canonicalize, compare_baseline, merge_findings
from rtl_lens.engines.base import AnalysisEngine
from rtl_lens.knowledge import KnowledgeStore
from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph
from rtl_lens.models.diagnostic import BaselineState, Finding, Severity
from rtl_lens.models.engine import EngineFailure, EngineRequest, EngineRun, EngineState
from rtl_lens.models.project import EngineMode, ProjectConfig, ResolvedProject
from rtl_lens.models.report import ScanMetadata, ScanReport, ScanState
from rtl_lens.security.paths import resolve_baseline_path

_SEVERITY_RANK = {
    Severity.INFO: 1,
    Severity.WARNING: 2,
    Severity.ERROR: 3,
}


class ScanOutcome(BaseModel):
    """A complete report paired with its process-level policy status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report: ScanReport
    exit_code: int


class ScanService:
    """Run configured engines and assemble their immutable scan report."""

    def __init__(
        self,
        engines: Sequence[AnalysisEngine],
        *,
        clock: Callable[[], datetime] | None = None,
        knowledge_store: KnowledgeStore | None = None,
    ) -> None:
        self._engines = tuple(engines)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._knowledge_store = knowledge_store or KnowledgeStore.load_default()

    def scan(self, project: ResolvedProject, config: ProjectConfig) -> ScanOutcome:
        """Run every requested engine independently and evaluate scan policy."""
        started_at = self._clock()
        engines = _selected_engines(self._engines, config)
        requested = tuple(engine.name for engine in engines)
        try:
            baseline = preflight_scan_configuration(project, config)
        except Exception:  # noqa: BLE001 - invalid baseline is a configuration outcome.
            finished_at = self._clock()
            return _configuration_failure_outcome(
                project, config, requested, started_at, finished_at
            )

        runs: list[EngineRun] = []
        for engine in engines:
            required = _is_required(engine.name, config)
            runs.append(
                _run_engine(
                    engine,
                    EngineRequest(project=project, timeout_seconds=config.scan.timeout),
                    required=required,
                )
            )

        completed = tuple(run.engine for run in runs if run.state is EngineState.COMPLETED)
        required_failure = any(
            run.state is not EngineState.COMPLETED
            and run.failure is not None
            and run.failure.required
            for run in runs
        )
        if required_failure or not completed:
            scan_state = ScanState.FAILED
        elif len(completed) == len(requested):
            scan_state = ScanState.COMPLETE
        else:
            scan_state = ScanState.PARTIAL
        canonical = (
            canonicalize(diagnostic)
            for run in runs
            if run.state is EngineState.COMPLETED
            for diagnostic in run.diagnostics
        )
        comparison = compare_baseline(merge_findings(canonical), baseline)
        comparison_complete = _baseline_comparison_is_complete(
            baseline,
            requested=requested,
            completed=completed,
            scan_state=scan_state,
        )
        resolved_fingerprints = comparison.resolved_fingerprints if comparison_complete else ()
        findings = tuple(
            _prepare_finding(finding, config, self._knowledge_store)
            for finding in comparison.findings
        )
        module_graph = _select_module_graph(runs)
        analysis_warnings = _collect_analysis_warnings(runs)
        trends = summarize_trends(
            findings,
            resolved_fingerprints,
            baseline_configured=config.scan.baseline_path is not None,
            baseline_configuration_known=True,
            comparison_complete=comparison_complete,
        )
        finished_at = self._clock()
        report = ScanReport(
            schema_version="1.0",
            metadata=ScanMetadata(
                project_root=str(project.root),
                started_at=started_at,
                duration_ms=_duration_ms(started_at, finished_at),
                requested_engines=requested,
                completed_engines=completed,
                config_digest=config_digest(config),
                redacted=config.scan.redact_sources,
                scan_state=scan_state,
                source_count=len(project.sources),
            ),
            findings=findings,
            engine_runs=tuple(runs),
            resolved_fingerprints=resolved_fingerprints,
            module_graph=module_graph,
            trends=trends,
            analysis_warnings=analysis_warnings,
        )
        threshold = _SEVERITY_RANK[config.scan.fail_on]
        blocking = any(
            finding.baseline_state is BaselineState.NEW
            and _SEVERITY_RANK[finding.severity] >= threshold
            for finding in findings
        )
        exit_code = 2 if required_failure else 1 if blocking else 0
        return ScanOutcome(report=report, exit_code=exit_code)


def _baseline_comparison_is_complete(
    baseline: ScanReport | None,
    *,
    requested: tuple[str, ...],
    completed: tuple[str, ...],
    scan_state: ScanState,
) -> bool:
    if baseline is None or scan_state is not ScanState.COMPLETE:
        return False
    if baseline.metadata.scan_state is not ScanState.COMPLETE:
        return False
    current_requested = frozenset(requested)
    current_completed = frozenset(completed)
    baseline_requested = frozenset(baseline.metadata.requested_engines)
    baseline_completed = frozenset(baseline.metadata.completed_engines)
    return current_requested == current_completed == baseline_requested == baseline_completed


def _is_required(engine_name: str, config: ProjectConfig) -> bool:
    return engine_name != "verilator" or config.scan.engine_mode is EngineMode.REQUIRED


def _selected_engines(
    engines: Sequence[AnalysisEngine], config: ProjectConfig
) -> tuple[AnalysisEngine, ...]:
    return tuple(
        engine
        for engine in sorted(engines, key=lambda candidate: candidate.name)
        if not (engine.name == "verilator" and config.scan.engine_mode is EngineMode.DISABLED)
    )


def _run_engine(
    engine: AnalysisEngine,
    request: EngineRequest,
    *,
    required: bool,
) -> EngineRun:
    try:
        if not engine.available():
            return EngineRun.unavailable(engine.name, required=required)
        run = engine.run(request)
    except Exception as error:  # noqa: BLE001 - one adapter cannot abort later engines.
        return EngineRun(
            engine=engine.name,
            state=EngineState.FAILED,
            failure=EngineFailure(
                kind=type(error).__name__,
                message=_bounded_error_message(error),
                required=required,
            ),
        )
    if run.state is not EngineState.COMPLETED and run.failure is None:
        return run.model_copy(
            update={
                "failure": EngineFailure(
                    kind="engine_failure",
                    message=_bounded_message(
                        f"{run.engine} returned {run.state.value} without failure metadata"
                    ),
                    required=required,
                )
            }
        )
    if run.failure is None or run.failure.required is required:
        return run
    return run.model_copy(update={"failure": run.failure.model_copy(update={"required": required})})


def _select_module_graph(runs: Sequence[EngineRun]) -> ModuleGraph:
    for run in runs:
        if (
            run.engine == "pyslang"
            and run.state is EngineState.COMPLETED
            and run.module_graph is not None
        ):
            return run.module_graph
    return ModuleGraph()


def _collect_analysis_warnings(
    runs: Sequence[EngineRun],
) -> tuple[AnalysisWarning, ...]:
    ordered = sorted(
        (
            (run.engine, warning.kind, warning.message, warning)
            for run in runs
            for warning in run.analysis_warnings
        ),
        key=lambda item: item[:3],
    )
    return tuple(item[3] for item in ordered)


def _bounded_error_message(error: Exception) -> str:
    try:
        message = str(error).strip() or type(error).__name__
    except Exception:  # noqa: BLE001 - failure formatting must be total.
        message = f"{type(error).__name__} (message unavailable)"
    return _bounded_message(message)


def _bounded_message(message: str) -> str:
    return message[:500]


def _load_baseline(project: ResolvedProject, config: ProjectConfig) -> ScanReport | None:
    configured = config.scan.baseline_path
    if configured is None:
        return None
    path = resolve_baseline_path(project.root, config.scan.output_dir, configured)
    return _read_baseline(path)


def preflight_scan_configuration(
    project: ResolvedProject, config: ProjectConfig
) -> ScanReport | None:
    """Validate scan-only configuration before loading runtime analyzers."""
    if config.scan.language not in {"en", "zh-CN"}:
        raise ValueError(f"unsupported language: {config.scan.language}")
    return _load_baseline(project, config)


def _read_baseline(path: Path) -> ScanReport:
    limit = 16 * 1024 * 1024
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("baseline is missing or exceeds the size limit")
    with path.open("rb") as baseline_file:
        payload = baseline_file.read(limit + 1)
    if len(payload) > limit:
        raise ValueError("baseline exceeds the size limit")
    return ScanReport.model_validate_json(payload)


def _configuration_failure_outcome(
    project: ResolvedProject,
    config: ProjectConfig,
    requested: tuple[str, ...],
    started_at: datetime,
    finished_at: datetime,
) -> ScanOutcome:
    report = ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=str(project.root),
            started_at=started_at,
            duration_ms=_duration_ms(started_at, finished_at),
            requested_engines=requested,
            completed_engines=(),
            config_digest=config_digest(config),
            redacted=config.scan.redact_sources,
            scan_state=ScanState.FAILED,
            source_count=len(project.sources),
        ),
        findings=(),
        module_graph=ModuleGraph(),
        trends=summarize_trends(
            (),
            (),
            baseline_configured=config.scan.baseline_path is not None,
            baseline_configuration_known=True,
        ),
        analysis_warnings=(),
    )
    return ScanOutcome(report=report, exit_code=3)


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _enrich_finding(
    finding: Finding,
    config: ProjectConfig,
    knowledge_store: KnowledgeStore,
) -> Finding:
    language = cast(Literal["en", "zh-CN"], config.scan.language)
    if knowledge_store.get(finding.canonical_rule, language) is None:
        return finding
    return finding.model_copy(update={"explanation_id": finding.canonical_rule}, deep=True)


def _prepare_finding(
    finding: Finding,
    config: ProjectConfig,
    knowledge_store: KnowledgeStore,
) -> Finding:
    enriched = _enrich_finding(finding, config, knowledge_store)
    if not config.scan.redact_sources:
        return enriched
    provenance = tuple(
        diagnostic.model_copy(update={"source_snippet": None}) for diagnostic in enriched.provenance
    )
    return enriched.model_copy(update={"source_snippet": None, "provenance": provenance}, deep=True)
