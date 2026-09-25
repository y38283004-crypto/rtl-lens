"""Secure, self-contained HTML report generation."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from jinja2 import Environment, PackageLoader, select_autoescape

from rtl_lens.knowledge.schema import LocalizedExplanation
from rtl_lens.knowledge.store import KnowledgeStore
from rtl_lens.models.diagnostic import BaselineState, Severity
from rtl_lens.models.report import ScanReport
from rtl_lens.security.paths import validate_atomic_destination
from rtl_lens.security.redaction import RedactionPolicy, default_redaction_policy, redact_report

_ENVIRONMENT = Environment(
    loader=PackageLoader("rtl_lens", "renderers/assets"),
    autoescape=select_autoescape(
        enabled_extensions=("html", "j2"),
        default_for_string=True,
        default=True,
    ),
)

_ComparisonMode = Literal["unknown", "uncompared", "incomplete", "complete"]


def write_html_report(
    report: ScanReport,
    destination: Path,
    *,
    graph_display_limit: int = 200,
    redaction_policy: RedactionPolicy | None = None,
) -> None:
    """Render ``report`` to one offline HTML file and atomically replace ``destination``."""
    destination = validate_atomic_destination(destination)
    if redaction_policy is not None or report.metadata.redacted:
        report = redact_report(report, redaction_policy or default_redaction_policy())
    html = render_html_report(report, graph_display_limit=graph_display_limit)
    _write_atomic((html + "\n").encode("utf-8"), destination)


def render_shareable_html(
    report: ScanReport,
    *,
    home: Path | None = None,
    path_prefixes: tuple[Path, ...] = (),
    secret_values: tuple[str, ...] = (),
    graph_display_limit: int = 200,
) -> str:
    """Render a self-contained HTML report after explicit immutable redaction."""
    policy = RedactionPolicy(
        home=Path.home() if home is None else home,
        path_prefixes=path_prefixes,
        secret_values=secret_values,
    )
    return render_html_report(
        redact_report(report, policy), graph_display_limit=graph_display_limit
    )


def render_html_report(report: ScanReport, *, graph_display_limit: int = 200) -> str:
    """Render a report to a self-contained HTML string without changing it."""
    if not 1 <= graph_display_limit <= 2000:
        raise ValueError("graph_display_limit must be between 1 and 2000")
    try:
        knowledge_store = KnowledgeStore.load_default()
    except Exception:  # noqa: BLE001 - optional knowledge must not break report output
        knowledge_store = None
    engine_names = tuple(
        sorted(
            {run.engine for run in report.engine_runs}
            | {item.engine for finding in report.findings for item in finding.provenance}
        )
    )
    engine_tokens = {name: f"engine-{index}" for index, name in enumerate(engine_names)}
    comparison_mode = _comparison_mode(report)
    comparison_presentations = {
        state: _finding_comparison(state, mode=comparison_mode) for state in BaselineState
    }
    findings = tuple(
        {
            "finding": finding,
            "engines": tuple(
                engine_tokens[name] for name in sorted({item.engine for item in finding.provenance})
            ),
            "explanation": _get_explanation(knowledge_store, finding.explanation_id),
            "comparison": comparison_presentations[finding.baseline_state],
        }
        for finding in report.findings
    )
    engine_options = tuple({"token": engine_tokens[name], "name": name} for name in engine_names)
    comparison_options = _comparison_options(
        report,
        presentations=comparison_presentations,
    )
    severity_counts = {
        severity.value: sum(finding.severity is severity for finding in report.findings)
        for severity in Severity
    }
    findings_by_fingerprint = {finding.fingerprint: finding for finding in report.findings}
    trend_context = _trend_context(
        report,
        mode=comparison_mode,
        findings_by_fingerprint=findings_by_fingerprint,
    )
    unresolved = frozenset(report.module_graph.unresolved)
    displayed_edges = report.module_graph.edges[:graph_display_limit]
    relationship_rows = tuple(
        {
            "parent": parent,
            "child": child,
            "unresolved": child in unresolved,
            "search": f"{parent} {child}",
        }
        for parent, child in displayed_edges
    )
    html = _ENVIRONMENT.get_template("report.html.j2").render(
        report=report,
        report_data=report.model_dump(mode="json"),
        findings=findings,
        engine_options=engine_options,
        comparison_options=comparison_options,
        severity_counts=severity_counts,
        analysis_warnings=tuple(
            sorted(report.analysis_warnings, key=lambda warning: (warning.kind, warning.message))
        ),
        **trend_context,
        relationship_rows=relationship_rows,
        displayed_relationship_count=len(displayed_edges),
        total_relationship_count=len(report.module_graph.edges),
    )
    return html


def _comparison_mode(report: ScanReport) -> _ComparisonMode:
    if not report.trends.baseline_configuration_known:
        return "unknown"
    if not report.trends.baseline_configured:
        return "uncompared"
    if report.trends.comparison_complete:
        return "complete"
    return "incomplete"


def _finding_comparison(
    state: BaselineState,
    *,
    mode: _ComparisonMode,
) -> dict[str, str]:
    if mode == "unknown":
        return {"token": "comparison-status-unknown", "label": "CURRENT / STATUS UNKNOWN"}
    if mode == "uncompared":
        return {"token": "comparison-uncompared", "label": "CURRENT / UNCOMPARED"}
    if mode == "incomplete":
        if state is BaselineState.NEW:
            return {"token": "comparison-unmatched", "label": "CURRENT / UNMATCHED"}
        if state is BaselineState.EXISTING:
            return {"token": "comparison-matched", "label": "CURRENT / MATCHED"}
        return {"token": "comparison-status-unknown", "label": "CURRENT / STATUS UNKNOWN"}
    if state is BaselineState.NEW:
        return {"token": "comparison-new", "label": "NEW"}
    if state is BaselineState.EXISTING:
        return {"token": "comparison-unchanged", "label": "UNCHANGED"}
    return {"token": "comparison-resolved", "label": "RESOLVED"}


def _comparison_options(
    report: ScanReport,
    *,
    presentations: Mapping[BaselineState, dict[str, str]],
) -> tuple[dict[str, str], ...]:
    present_states = {finding.baseline_state for finding in report.findings}
    seen_tokens: set[str] = set()
    options: list[dict[str, str]] = []
    for state in BaselineState:
        if state not in present_states:
            continue
        presentation = presentations[state]
        if presentation["token"] in seen_tokens:
            continue
        seen_tokens.add(presentation["token"])
        options.append(presentation)
    return tuple(options)


def _trend_context(
    report: ScanReport,
    *,
    mode: _ComparisonMode,
    findings_by_fingerprint: Mapping[str, object],
) -> dict[str, object]:
    def entries(fingerprints: tuple[str, ...]) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "fingerprint": fingerprint,
                "finding": findings_by_fingerprint.get(fingerprint),
            }
            for fingerprint in fingerprints
        )

    if mode == "unknown":
        current = tuple(finding.fingerprint for finding in report.findings)
        return {
            "trend_intro_title": "Baseline configuration status unknown.",
            "trend_intro_message": (
                "This legacy report does not record whether a baseline was configured; "
                "comparison and resolution status cannot be evaluated."
            ),
            "trend_summary_cards": (
                {
                    "value": f"{len(current)} current / status unknown",
                    "meaning": "Legacy baseline configuration status unavailable",
                },
                {
                    "value": "Resolution unavailable",
                    "meaning": "Baseline configuration status unknown",
                },
            ),
            "trend_groups": (
                {
                    "slug": "current-status-unknown",
                    "label": "CURRENT / STATUS UNKNOWN",
                    "summary": f"{len(current)} CURRENT / STATUS UNKNOWN",
                    "meaning": "Legacy baseline configuration status is unavailable.",
                    "entries": entries(current),
                },
                {
                    "slug": "resolution",
                    "label": "RESOLUTION",
                    "summary": "Resolution unavailable",
                    "meaning": "Baseline configuration status is unknown for this legacy report.",
                    "entries": (),
                },
            ),
        }

    if mode == "uncompared":
        current = tuple(finding.fingerprint for finding in report.findings)
        return {
            "trend_intro_title": "No baseline configured.",
            "trend_intro_message": (
                "Current findings are not compared with a baseline; resolution cannot be evaluated."
            ),
            "trend_summary_cards": (
                {
                    "value": f"{len(current)} current / uncompared",
                    "meaning": "Not compared with a baseline",
                },
                {
                    "value": "Resolution unavailable",
                    "meaning": "No baseline configured",
                },
            ),
            "trend_groups": (
                {
                    "slug": "current-uncompared",
                    "label": "CURRENT / UNCOMPARED",
                    "summary": f"{len(current)} CURRENT / UNCOMPARED",
                    "meaning": "Current findings are not compared with a baseline.",
                    "entries": entries(current),
                },
                {
                    "slug": "resolution",
                    "label": "RESOLUTION",
                    "summary": "Resolution unavailable",
                    "meaning": "No baseline was configured for an absence comparison.",
                    "entries": (),
                },
            ),
        }

    if mode == "complete":
        resolved_count = len(report.trends.resolved)
        return {
            "trend_intro_title": "Comparison complete.",
            "trend_intro_message": (
                "Baseline configured. Both reports have complete, compatible engine coverage."
            ),
            "trend_summary_cards": (
                {
                    "value": f"{len(report.trends.new)} new",
                    "meaning": "Not in configured baseline",
                },
                {
                    "value": f"{len(report.trends.unchanged)} unchanged",
                    "meaning": "Present in both reports",
                },
                {
                    "value": (
                        f"{resolved_count} resolved "
                        f"{'fingerprint' if resolved_count == 1 else 'fingerprints'}"
                    ),
                    "meaning": "No longer present",
                },
            ),
            "trend_groups": (
                {
                    "slug": "new",
                    "label": "NEW",
                    "summary": f"{len(report.trends.new)} NEW",
                    "meaning": "Present in this scan and absent from the configured baseline.",
                    "entries": entries(report.trends.new),
                },
                {
                    "slug": "unchanged",
                    "label": "UNCHANGED",
                    "summary": f"{len(report.trends.unchanged)} UNCHANGED",
                    "meaning": "Present in both this scan and the configured baseline.",
                    "entries": entries(report.trends.unchanged),
                },
                {
                    "slug": "resolved",
                    "label": "RESOLVED",
                    "summary": f"{resolved_count} RESOLVED",
                    "meaning": (
                        "Present in the configured baseline and no longer present in this scan."
                    ),
                    "entries": entries(report.trends.resolved),
                },
            ),
        }

    return {
        "trend_intro_title": "Comparison unavailable or incomplete.",
        "trend_intro_message": (
            "A baseline was configured, but complete compatible engine coverage was unavailable. "
            "Resolution claims are withheld."
        ),
        "trend_summary_cards": (
            {
                "value": f"{len(report.trends.new)} current / unmatched",
                "meaning": "Available baseline data only",
            },
            {
                "value": f"{len(report.trends.unchanged)} current / matched",
                "meaning": "Present in loaded baseline data",
            },
            {
                "value": "Resolution unavailable",
                "meaning": "Comparison incomplete",
            },
        ),
        "trend_groups": (
            {
                "slug": "current-unmatched",
                "label": "CURRENT / UNMATCHED",
                "summary": f"{len(report.trends.new)} CURRENT / UNMATCHED",
                "meaning": (
                    "Current findings not matched in the available baseline data; "
                    "the comparison is incomplete."
                ),
                "entries": entries(report.trends.new),
            },
            {
                "slug": "current-matched",
                "label": "CURRENT / MATCHED",
                "summary": f"{len(report.trends.unchanged)} CURRENT / MATCHED",
                "meaning": "Current findings also present in the loaded baseline data.",
                "entries": entries(report.trends.unchanged),
            },
            {
                "slug": "resolution",
                "label": "RESOLUTION",
                "summary": "Resolution unavailable",
                "meaning": "Prior-only findings are withheld because engine coverage is incomplete.",
                "entries": (),
            },
        ),
    }


def _get_explanation(
    knowledge_store: KnowledgeStore | None,
    explanation_id: str | None,
) -> dict[str, LocalizedExplanation] | None:
    if knowledge_store is None or explanation_id is None:
        return None
    try:
        english = knowledge_store.get(explanation_id, "en")
        chinese = knowledge_store.get(explanation_id, "zh-CN")
    except Exception:  # noqa: BLE001 - optional knowledge must not break report output
        return None
    if english is None or chinese is None:
        return None
    return {"en": english, "zh_cn": chinese}


def _write_atomic(payload: bytes, destination: Path) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(descriptor, remaining)
            if written == 0:
                raise OSError("failed to write HTML report")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, destination)
    except BaseException:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary.unlink(missing_ok=True)
        raise
