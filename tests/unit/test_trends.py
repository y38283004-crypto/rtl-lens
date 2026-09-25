"""Behavior tests for deterministic baseline trend summaries."""

from __future__ import annotations

import pytest

from rtl_lens.analysis.trends import summarize_trends
from rtl_lens.models.diagnostic import BaselineState, Finding, Severity, SourceLocation


def finding(fingerprint: str, *, baseline_state: BaselineState) -> Finding:
    """Create a real normalized finding with the requested baseline state."""
    return Finding(
        fingerprint=fingerprint,
        canonical_rule="width-mismatch",
        severity=Severity.WARNING,
        location=SourceLocation(path="top.sv", line=1, column=1),
        title="Width mismatch",
        baseline_state=baseline_state,
    )


def test_trends_partition_new_unchanged_and_resolved() -> None:
    findings = (
        finding("b", baseline_state=BaselineState.EXISTING),
        finding("a", baseline_state=BaselineState.NEW),
    )

    summary = summarize_trends(
        findings,
        resolved_fingerprints=("d", "c", "c"),
        baseline_configuration_known=True,
        baseline_configured=True,
        comparison_complete=True,
    )

    assert summary.new == ("a",)
    assert summary.unchanged == ("b",)
    assert summary.resolved == ("c", "d")
    assert summary.baseline_configuration_known is True
    assert summary.baseline_configured is True
    assert summary.comparison_complete is True


def test_trends_keep_current_findings_new_when_no_baseline_is_configured() -> None:
    summary = summarize_trends(
        (finding("current", baseline_state=BaselineState.NEW),),
        resolved_fingerprints=(),
        baseline_configuration_known=True,
        baseline_configured=False,
    )

    assert summary.new == ("current",)
    assert summary.unchanged == ()
    assert summary.resolved == ()
    assert summary.baseline_configuration_known is True
    assert summary.baseline_configured is False


def test_empty_trends_are_serializable_and_deterministic() -> None:
    summary = summarize_trends((), resolved_fingerprints=(), baseline_configured=False)

    assert summary.model_dump_json() == (
        '{"new":[],"unchanged":[],"resolved":[],"baseline_configured":false,'
        '"baseline_configuration_known":false,'
        '"comparison_complete":false}'
    )


def test_incomplete_comparison_withholds_resolved_partition() -> None:
    summary = summarize_trends(
        (finding("matched", baseline_state=BaselineState.EXISTING),),
        resolved_fingerprints=("prior-only",),
        baseline_configuration_known=True,
        baseline_configured=True,
        comparison_complete=False,
    )

    assert summary.unchanged == ("matched",)
    assert summary.resolved == ()
    assert summary.comparison_complete is False


def test_legacy_builder_call_cannot_claim_complete_or_resolved_without_known_status() -> None:
    summary = summarize_trends(
        (),
        resolved_fingerprints=("prior-only",),
        baseline_configured=True,
        comparison_complete=True,
    )

    assert summary.baseline_configuration_known is False
    assert summary.comparison_complete is False
    assert summary.resolved == ()


def test_trend_serialization_is_input_order_independent() -> None:
    new = finding("new", baseline_state=BaselineState.NEW)
    existing = finding("existing", baseline_state=BaselineState.EXISTING)

    forward = summarize_trends(
        (new, existing),
        resolved_fingerprints=("resolved-b", "resolved-a"),
        baseline_configured=True,
    )
    reverse = summarize_trends(
        (existing, new),
        resolved_fingerprints=("resolved-a", "resolved-b"),
        baseline_configured=True,
    )

    assert forward.model_dump_json() == reverse.model_dump_json()


def test_trends_reject_overlapping_fingerprints() -> None:
    with pytest.raises(ValueError, match="only one trend partition"):
        summarize_trends(
            (
                finding("duplicated", baseline_state=BaselineState.NEW),
                finding("duplicated", baseline_state=BaselineState.EXISTING),
            ),
            resolved_fingerprints=(),
            baseline_configured=True,
        )
    with pytest.raises(ValueError, match="only one trend partition"):
        summarize_trends(
            (finding("duplicated", baseline_state=BaselineState.NEW),),
            resolved_fingerprints=("duplicated",),
            baseline_configuration_known=True,
            baseline_configured=True,
            comparison_complete=True,
        )
