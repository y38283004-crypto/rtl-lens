"""Pure immutable redaction contracts for shareable reports."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rtl_lens.models.project import ScanConfig
from rtl_lens.models.report import ScanReport
from rtl_lens.security.redaction import RedactionPolicy, redact_report

from .conftest import CONFIGURED_PREFIX, HOME, PROJECT, SECRET, UNMARKED


def _assert_canaries_absent(payload: str) -> None:
    folded = payload.replace("\\\\", "\\").casefold()
    assert str(HOME).casefold() not in folded
    assert str(HOME).replace("\\", "/").casefold() not in folded
    assert PROJECT.casefold() not in folded
    assert str(CONFIGURED_PREFIX).casefold() not in folded
    assert SECRET.casefold() not in folded


def test_redact_report_is_complete_immutable_and_idempotent(
    hostile_report: ScanReport,
) -> None:
    before = hostile_report.model_dump_json()
    policy = RedactionPolicy(
        home=Path(r"c:\users\alice"),
        path_prefixes=(CONFIGURED_PREFIX,),
        secret_values=(SECRET,),
    )

    redacted = redact_report(hostile_report, policy)

    _assert_canaries_absent(redacted.model_dump_json())
    assert redacted.metadata.project_root == "<project>"
    assert redacted.metadata.redacted is True
    assert redacted.findings[0].source_snippet is None
    assert redacted.findings[0].provenance[0].source_snippet is None
    assert hostile_report.model_dump_json() == before
    assert hostile_report.metadata.redacted is False
    assert redact_report(redacted, policy) == redacted
    assert redacted.schema_version == hostile_report.schema_version
    assert redacted.metadata.config_digest == hostile_report.metadata.config_digest
    assert redacted.findings[0].fingerprint == hostile_report.findings[0].fingerprint
    assert redacted.findings[0].canonical_rule == hostile_report.findings[0].canonical_rule
    assert UNMARKED in redacted.findings[0].message


def test_policy_reads_only_exact_named_nonempty_environment_values(
    hostile_report: ScanReport,
) -> None:
    environment = {
        "MARKED_SECRET": SECRET,
        "EMPTY_SECRET": "",
        "UNMARKED_SECRET": UNMARKED,
    }
    policy = RedactionPolicy.from_environment(
        home=HOME,
        path_prefixes=(CONFIGURED_PREFIX,),
        variable_names=("MARKED_SECRET", "EMPTY_SECRET", "MISSING_SECRET"),
        environment=environment,
    )

    redacted = redact_report(hostile_report, policy)

    assert SECRET not in redacted.model_dump_json()
    assert UNMARKED in redacted.model_dump_json()
    assert SECRET not in repr(policy)


def test_scan_config_accepts_deterministic_redaction_inputs() -> None:
    config = ScanConfig(
        redact_sources=True,
        redact_path_prefixes=(Path("private"), Path(r"D:\lab\private")),
        redact_environment_variables=("TOKEN", "API_KEY"),
    )

    assert config.redact_path_prefixes == (Path("private"), Path(r"D:\lab\private"))
    assert config.redact_environment_variables == ("API_KEY", "TOKEN")


@pytest.mark.parametrize("name", ["", "9TOKEN", "TOKEN-NAME", "TOKEN NAME", "A=B"])
def test_scan_config_rejects_invalid_secret_environment_names(name: str) -> None:
    with pytest.raises(ValidationError, match="environment"):
        ScanConfig(redact_environment_variables=(name,))


def test_generated_markers_never_reveal_or_reprocess_overlapping_sensitive_values(
    hostile_report: ScanReport,
) -> None:
    policy = RedactionPolicy(
        path_prefixes=(Path("redacted-path"),),
        secret_values=("redacted", "redacted-secret"),
    )
    overlapping = hostile_report.model_copy(
        update={
            "analysis_warnings": (
                hostile_report.analysis_warnings[0].model_copy(
                    update={
                        "message": "redacted-path redacted redacted-secret",
                    }
                ),
            )
        },
        deep=True,
    )

    once = redact_report(overlapping, policy)
    twice = redact_report(once, policy)
    message = once.analysis_warnings[0].message

    assert twice == once
    assert "redacted-path" not in message
    assert "redacted-secret" not in message
    assert "redacted" not in message


def test_windows_path_redaction_accepts_mixed_and_repeated_separators(
    hostile_report: ScanReport,
) -> None:
    mixed_path = r"d:/LAB\\Private/file.sv"
    finding = hostile_report.findings[0].model_copy(
        update={"message": f"generated at {mixed_path}"},
        deep=True,
    )
    report = hostile_report.model_copy(update={"findings": (finding,)}, deep=True)

    redacted = redact_report(
        report,
        RedactionPolicy(path_prefixes=(Path(r"D:\lab\private"),)),
    )

    assert redacted.findings[0].message == "generated at <redacted-path>/file.sv"


def test_project_root_label_wins_when_home_and_configured_prefix_are_identical(
    hostile_report: ScanReport,
) -> None:
    project = Path(PROJECT)
    redacted = redact_report(
        hostile_report,
        RedactionPolicy(home=project, path_prefixes=(project,)),
    )

    assert redacted.metadata.project_root == "<project>"
    assert redacted.findings[0].location.path.startswith("<project>")


def test_project_metadata_uses_a_safe_idempotent_marker_when_default_marker_is_sensitive(
    hostile_report: ScanReport,
) -> None:
    canary = "<project>"
    policy = RedactionPolicy(
        path_prefixes=(Path(canary),),
        secret_values=(canary,),
    )
    warning = hostile_report.analysis_warnings[0].model_copy(
        update={"message": f"reserved marker canary: {canary}"}
    )
    report = hostile_report.model_copy(update={"analysis_warnings": (warning,)}, deep=True)

    once = redact_report(report, policy)
    twice = redact_report(once, policy)

    assert once.metadata.project_root != canary
    assert canary not in once.metadata.project_root
    assert canary not in once.analysis_warnings[0].message
    assert twice == once
