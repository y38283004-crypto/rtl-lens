"""Immutable baseline comparison for current and historical findings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from rtl_lens.diagnostics.merge import merge_findings
from rtl_lens.models.diagnostic import BaselineState, Finding
from rtl_lens.models.report import ScanReport


class BaselineComparison(BaseModel):
    """Current policy findings plus stable identities resolved from prior scans."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: tuple[Finding, ...]
    resolved_fingerprints: tuple[str, ...]


def compare_baseline(
    current: tuple[Finding, ...],
    previous: ScanReport | None,
) -> BaselineComparison:
    """Classify current findings and retain resolved identities without synthetic findings."""
    merged_current = merge_findings(current)
    current_fingerprints = {finding.fingerprint for finding in merged_current}
    previous_fingerprints = (
        {finding.fingerprint for finding in previous.findings} if previous is not None else set()
    )

    findings = tuple(
        finding.model_copy(
            update={
                "baseline_state": (
                    BaselineState.EXISTING
                    if finding.fingerprint in previous_fingerprints
                    else BaselineState.NEW
                )
            },
            deep=True,
        )
        for finding in merged_current
    )

    historical_resolved = set(previous.resolved_fingerprints) if previous is not None else set()
    resolved_fingerprints = tuple(
        sorted((historical_resolved | previous_fingerprints) - current_fingerprints)
    )
    return BaselineComparison(
        findings=findings,
        resolved_fingerprints=resolved_fingerprints,
    )
