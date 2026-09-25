"""Behavior tests for canonical diagnostic identity and fingerprints."""

from __future__ import annotations

import pytest

from rtl_lens.diagnostics.canonical import ENGINE_RULES, canonicalize, fingerprint
from rtl_lens.knowledge.store import KnowledgeStore
from rtl_lens.models.diagnostic import RawDiagnostic, Severity, SourceLocation


def _raw(
    engine: str,
    code: str,
    path: str = "rtl/alu.sv",
    line: int = 42,
    column: int = 9,
    message: str = "width mismatch",
    *,
    symbol: str | None = "alu_result",
) -> RawDiagnostic:
    return RawDiagnostic(
        engine=engine,
        engine_version="fixture",
        original_code=code,
        severity=Severity.WARNING,
        location=SourceLocation(path=path, line=line, column=column),
        message=message,
        symbol=symbol,
    )


@pytest.mark.parametrize(
    ("code", "canonical_rule"),
    [
        ("WIDTH", "width-mismatch"),
        ("LATCH", "incomplete-assignment"),
        ("CASEINCOMPLETE", "case-incomplete"),
        ("CASEOVERLAP", "case-overlap"),
        ("UNUSEDSIGNAL", "unused-signal"),
        ("UNDRIVEN", "undriven-signal"),
        ("MULTIDRIVEN", "multiple-drivers"),
        ("BLKSEQ", "blocking-in-sequential"),
        ("ALWCOMBORDER", "always-comb-order"),
        ("ALWNEVER", "always-never"),
        ("ASCRANGE", "ascending-range"),
        ("ASSIGNEQEXPR", "assignment-in-expression"),
    ],
)
def test_verilator_mapping_contains_exact_approved_first_batch_pairs(
    code: str, canonical_rule: str
) -> None:
    assert ENGINE_RULES[("verilator", code)] == canonical_rule
    assert canonicalize(_raw("verilator", code)).canonical_rule == canonical_rule


def test_engine_rules_equal_the_validated_default_store() -> None:
    assert ENGINE_RULES == KnowledgeStore.load_default().engine_rules


def test_verilator_width_codes_are_not_reassigned_to_port_width() -> None:
    assert ENGINE_RULES[("verilator", "WIDTHTRUNC")] == "width-mismatch"
    assert not any(
        engine == "verilator" and rule_id == "port-width-mismatch"
        for (engine, _code), rule_id in ENGINE_RULES.items()
    )


def test_fallback_codes_are_pinned_to_pyslang_11() -> None:
    assert ENGINE_RULES[("pyslang", "DiagCode(UndeclaredIdentifier)")] == ("undeclared-identifier")
    assert ENGINE_RULES[("pyslang", "DiagCode(MissingTimeScale)")] == ("timescale-mismatch")


def test_fixture_proven_pyslang_constant_conversion_maps_to_width_mismatch() -> None:
    finding = canonicalize(_raw("pyslang", "constant-conversion"))

    assert finding.canonical_rule == "width-mismatch"


def test_unproven_pyslang_identifier_remains_engine_native_and_distinct() -> None:
    unproven = canonicalize(_raw("pyslang", "WidthTruncate"))
    proven = canonicalize(_raw("pyslang", "constant-conversion"))

    assert "pyslang" in unproven.canonical_rule
    assert "WidthTruncate" in unproven.canonical_rule
    assert unproven.canonical_rule != proven.canonical_rule
    assert unproven.fingerprint != proven.fingerprint


def test_known_rule_fingerprint_ignores_native_message_wording() -> None:
    first = canonicalize(_raw("verilator", "WIDTH", message="old wording"))
    second = canonicalize(_raw("verilator", "WIDTH", message="new wording"))

    assert fingerprint(first) == fingerprint(second)


def test_known_rule_fingerprint_includes_symbol() -> None:
    first = canonicalize(_raw("verilator", "WIDTH", symbol="lhs"))
    second = canonicalize(_raw("verilator", "WIDTH", symbol="rhs"))

    assert fingerprint(first) != fingerprint(second)


def test_unknown_rule_fingerprint_normalizes_message_whitespace() -> None:
    first = canonicalize(_raw("pyslang", "future-rule", message="alpha\n beta\tvalue"))
    second = canonicalize(_raw("pyslang", "future-rule", message=" alpha beta value "))

    assert fingerprint(first) == fingerprint(second)


def test_unknown_rule_fingerprint_distinguishes_long_messages_with_shared_prefix() -> None:
    prefix = "same diagnostic detail " * 300
    first = canonicalize(_raw("pyslang", "future-rule", message=prefix + "first"))
    second = canonicalize(_raw("pyslang", "future-rule", message=prefix + "second"))

    assert fingerprint(first) != fingerprint(second)


def test_canonicalize_normalizes_repository_relative_posix_path() -> None:
    raw = _raw("verilator", "WIDTH", path=r"rtl\.\blocks\..\alu.sv")

    finding = canonicalize(raw)

    assert finding.location.path == "rtl/alu.sv"
    assert finding.provenance == (raw,)
    assert finding.provenance[0].location.path == r"rtl\.\blocks\..\alu.sv"


@pytest.mark.parametrize("path", ["../outside.sv", "/outside.sv", "C:/outside.sv"])
def test_canonicalize_rejects_non_repository_relative_path(path: str) -> None:
    with pytest.raises(ValueError, match="repository-relative"):
        canonicalize(_raw("verilator", "WIDTH", path=path))
