"""Behavior tests for immutable deterministic baseline comparison."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rtl_lens.diagnostics.baseline import BaselineComparison, compare_baseline
from rtl_lens.diagnostics.canonical import canonicalize
from rtl_lens.models.diagnostic import (
    BaselineState,
    Finding,
    RawDiagnostic,
    Severity,
    SourceLocation,
)
from rtl_lens.models.report import ScanMetadata, ScanReport


def _finding(code: str, path: str, line: int = 1) -> Finding:
    return canonicalize(
        RawDiagnostic(
            engine="verilator",
            original_code=code,
            severity=Severity.WARNING,
            location=SourceLocation(path=path, line=line, column=1),
            message=code,
        )
    )


def _report(
    findings: tuple[Finding, ...] = (),
    resolved_fingerprints: tuple[str, ...] = (),
) -> ScanReport:
    return ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=".",
            started_at=datetime(2026, 8, 17, tzinfo=UTC),
            duration_ms=1,
            requested_engines=("verilator",),
            completed_engines=("verilator",),
            config_digest="0" * 64,
            redacted=False,
        ),
        findings=findings,
        resolved_fingerprints=resolved_fingerprints,
    )


@pytest.mark.parametrize("previous", [None, _report()])
def test_missing_or_empty_baseline_marks_all_current_findings_new(
    previous: ScanReport | None,
) -> None:
    current = (_finding("WIDTH", "b.sv"), _finding("LATCH", "a.sv"))

    comparison = compare_baseline(current, previous)

    assert {finding.baseline_state for finding in comparison.findings} == {BaselineState.NEW}
    assert comparison.resolved_fingerprints == ()


def test_baseline_marks_matches_existing_and_retains_prior_only_fingerprints() -> None:
    existing = _finding("WIDTH", "existing.sv")
    new = _finding("LATCH", "new.sv")
    resolved = _finding("UNDRIVEN", "resolved.sv")
    previous = _report(
        (resolved, existing),
        resolved_fingerprints=("f" * 64, "a" * 64, "f" * 64),
    )

    comparison = compare_baseline((new, existing), previous)

    states = {finding.fingerprint: finding.baseline_state for finding in comparison.findings}
    assert states == {
        existing.fingerprint: BaselineState.EXISTING,
        new.fingerprint: BaselineState.NEW,
    }
    assert comparison.resolved_fingerprints == tuple(
        sorted(("a" * 64, "f" * 64, resolved.fingerprint))
    )


def test_resurfaced_historical_fingerprint_is_new_and_not_resolved() -> None:
    resurfaced = _finding("WIDTH", "resurfaced.sv")
    previous = _report(resolved_fingerprints=(resurfaced.fingerprint,))

    comparison = compare_baseline((resurfaced,), previous)

    assert comparison.findings[0].baseline_state is BaselineState.NEW
    assert comparison.resolved_fingerprints == ()


def test_duplicate_and_reordered_inputs_produce_identical_comparison_json() -> None:
    first = _finding("WIDTH", "b.sv")
    second = _finding("LATCH", "a.sv")
    previous_a = _report((first, first), (second.fingerprint, second.fingerprint))
    previous_b = _report((first,), (second.fingerprint,))

    left = compare_baseline((second, first, first), previous_a)
    right = compare_baseline((first, second), previous_b)

    assert left.model_dump_json() == right.model_dump_json()
    assert len(left.findings) == 2


def test_compare_baseline_does_not_mutate_current_or_previous_models() -> None:
    current = (_finding("WIDTH", "current.sv"),)
    previous = _report((_finding("LATCH", "previous.sv"),))
    current_before = current[0].model_dump_json()
    previous_before = previous.model_dump_json()

    compare_baseline(current, previous)

    assert current[0].model_dump_json() == current_before
    assert previous.model_dump_json() == previous_before


def test_baseline_comparison_is_frozen_and_round_trips_json() -> None:
    comparison = compare_baseline((_finding("WIDTH", "current.sv"),), None)

    round_tripped = BaselineComparison.model_validate_json(comparison.model_dump_json())

    assert round_tripped == comparison
    with pytest.raises(ValidationError):
        comparison.findings = ()  # type: ignore[misc]
