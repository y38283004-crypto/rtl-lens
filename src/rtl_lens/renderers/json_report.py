"""Deterministic and atomic JSON report output."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from rtl_lens.models.report import ScanReport
from rtl_lens.security.paths import validate_atomic_destination
from rtl_lens.security.redaction import (
    RedactionPolicy,
    default_redaction_policy,
    redact_report,
)


def write_json_report(
    report: ScanReport,
    destination: Path,
    *,
    redaction_policy: RedactionPolicy | None = None,
) -> None:
    """Serialize ``report`` as stable UTF-8 JSON and atomically replace ``destination``."""
    destination = validate_atomic_destination(destination)
    if redaction_policy is not None or report.metadata.redacted:
        report = redact_report(report, redaction_policy or default_redaction_policy())
    payload = (report.model_dump_json(indent=2) + "\n").encode("utf-8")
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
                raise OSError("failed to write JSON report")
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
