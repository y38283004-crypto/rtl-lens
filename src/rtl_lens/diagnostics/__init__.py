"""Deterministic diagnostic canonicalization, merging, and baseline services."""

from rtl_lens.diagnostics.baseline import BaselineComparison, compare_baseline
from rtl_lens.diagnostics.canonical import ENGINE_RULES, canonicalize, fingerprint
from rtl_lens.diagnostics.merge import merge_findings

__all__ = [
    "ENGINE_RULES",
    "BaselineComparison",
    "canonicalize",
    "compare_baseline",
    "fingerprint",
    "merge_findings",
]
