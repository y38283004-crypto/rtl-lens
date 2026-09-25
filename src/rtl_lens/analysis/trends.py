"""Pure deterministic baseline trend normalization."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from rtl_lens.models.analysis import TrendSummary
from rtl_lens.models.diagnostic import BaselineState, Finding


def summarize_trends(
    findings: Sequence[Finding],
    resolved_fingerprints: Iterable[str],
    baseline_configured: bool,
    baseline_configuration_known: bool = False,
    comparison_complete: bool = False,
) -> TrendSummary:
    """Partition finding fingerprints into canonical baseline trend states."""
    new = {
        finding.fingerprint for finding in findings if finding.baseline_state is BaselineState.NEW
    }
    unchanged = {
        finding.fingerprint
        for finding in findings
        if finding.baseline_state is BaselineState.EXISTING
    }
    effective_comparison_complete = (
        baseline_configuration_known and baseline_configured and comparison_complete
    )
    resolved: set[str] = set()
    if effective_comparison_complete:
        resolved.update(resolved_fingerprints)
        resolved.update(
            finding.fingerprint
            for finding in findings
            if finding.baseline_state is BaselineState.RESOLVED
        )

    partitions = (new, unchanged, resolved)
    if sum(len(partition) for partition in partitions) != len(set().union(*partitions)):
        raise ValueError("a fingerprint may appear in only one trend partition")

    return TrendSummary(
        new=tuple(sorted(new)),
        unchanged=tuple(sorted(unchanged)),
        resolved=tuple(sorted(resolved)),
        baseline_configured=baseline_configured,
        baseline_configuration_known=baseline_configuration_known,
        comparison_complete=effective_comparison_complete,
    )
