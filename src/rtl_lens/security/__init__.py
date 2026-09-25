"""Security boundaries shared by RTL Lens composition layers."""

from rtl_lens.security.paths import (
    resolve_baseline_path,
    resolve_output_root,
    resolve_report_destination,
    validate_atomic_destination,
)
from rtl_lens.security.redaction import RedactionPolicy, redact_report

__all__ = [
    "RedactionPolicy",
    "redact_report",
    "resolve_baseline_path",
    "resolve_output_root",
    "resolve_report_destination",
    "validate_atomic_destination",
]
