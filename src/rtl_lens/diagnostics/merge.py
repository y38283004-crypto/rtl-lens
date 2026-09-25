"""Deterministic aggregation of equivalent canonical findings."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from rtl_lens.models.diagnostic import Finding, RawDiagnostic, Severity

_SEVERITY_ORDER = {
    Severity.ERROR: 0,
    Severity.WARNING: 1,
    Severity.INFO: 2,
}


def merge_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Merge identical finding identities and preserve every distinct native diagnostic."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.fingerprint].append(finding)

    merged = [_merge_group(group) for group in grouped.values()]
    return tuple(sorted(merged, key=_finding_sort_key))


def _merge_group(group: list[Finding]) -> Finding:
    representative = min(
        group,
        key=lambda finding: (
            _SEVERITY_ORDER[finding.severity],
            finding.model_dump_json(),
        ),
    )
    provenance_by_json: dict[str, RawDiagnostic] = {}
    for finding in group:
        for native in finding.provenance:
            provenance_by_json.setdefault(native.model_dump_json(), native)
    provenance = tuple(sorted(provenance_by_json.values(), key=_provenance_sort_key))
    return representative.model_copy(update={"provenance": provenance}, deep=True)


def _finding_sort_key(finding: Finding) -> tuple[int, str, int, int, str]:
    return (
        _SEVERITY_ORDER[finding.severity],
        finding.location.path,
        finding.location.line,
        finding.location.column,
        finding.fingerprint,
    )


def _provenance_sort_key(native: RawDiagnostic) -> tuple[object, ...]:
    location = native.location
    return (
        native.engine,
        native.original_code,
        native.engine_version or "",
        native.severity.value,
        location.path,
        location.line,
        location.column,
        location.end_line or 0,
        location.end_column or 0,
        native.symbol or "",
        native.message,
        native.source_snippet or "",
        native.model_dump_json(),
    )
