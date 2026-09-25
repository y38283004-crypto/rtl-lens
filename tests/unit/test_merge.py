"""Behavior tests for deterministic multi-engine finding merge."""

from __future__ import annotations

from itertools import permutations

from rtl_lens.diagnostics.canonical import canonicalize
from rtl_lens.diagnostics.merge import merge_findings
from rtl_lens.models.diagnostic import RawDiagnostic, Severity, SourceLocation


def _raw(
    engine: str,
    code: str,
    path: str = "rtl/alu.sv",
    line: int = 42,
    column: int = 9,
    message: str = "width mismatch",
    *,
    severity: Severity = Severity.WARNING,
    symbol: str | None = "alu_result",
) -> RawDiagnostic:
    return RawDiagnostic(
        engine=engine,
        engine_version="fixture",
        original_code=code,
        severity=severity,
        location=SourceLocation(path=path, line=line, column=column),
        message=message,
        symbol=symbol,
    )


def test_two_engines_merge_same_fixture_proven_width_issue() -> None:
    slang = _raw("pyslang", "constant-conversion")
    verilator = _raw("verilator", "WIDTH")

    merged = merge_findings([canonicalize(slang), canonicalize(verilator)])

    assert len(merged) == 1
    assert merged[0].canonical_rule == "width-mismatch"
    assert {item.engine for item in merged[0].provenance} == {
        "pyslang",
        "verilator",
    }


def test_known_findings_with_different_symbols_do_not_merge() -> None:
    lhs = canonicalize(_raw("verilator", "WIDTH", symbol="lhs"))
    rhs = canonicalize(_raw("pyslang", "constant-conversion", symbol="rhs"))

    assert len(merge_findings([lhs, rhs])) == 2


def test_unknown_findings_with_different_native_codes_do_not_merge() -> None:
    first = canonicalize(_raw("pyslang", "future-a"))
    second = canonicalize(_raw("pyslang", "future-b"))

    assert len(merge_findings([first, second])) == 2


def test_unknown_findings_with_different_messages_do_not_merge() -> None:
    first = canonicalize(_raw("pyslang", "future-rule", message="first meaning"))
    second = canonicalize(_raw("pyslang", "future-rule", message="second meaning"))

    assert len(merge_findings([first, second])) == 2


def test_merge_deduplicates_only_identical_native_provenance() -> None:
    raw = _raw("verilator", "WIDTH")
    finding = canonicalize(raw)

    merged = merge_findings([finding, finding])

    assert len(merged) == 1
    assert merged[0].provenance == (raw,)


def test_merge_chooses_stable_representative_values_and_preserves_native_data() -> None:
    warning = canonicalize(
        _raw(
            "verilator",
            "WIDTH",
            message="zeta wording",
            severity=Severity.WARNING,
        )
    ).model_copy(update={"title": "Zeta title", "source_snippet": "zeta"})
    error = canonicalize(
        _raw(
            "pyslang",
            "constant-conversion",
            message="alpha wording",
            severity=Severity.ERROR,
        )
    ).model_copy(update={"title": "Alpha title", "source_snippet": "alpha"})

    results = [merge_findings(order) for order in permutations((warning, error))]

    assert results[0] == results[1]
    representative = results[0][0]
    assert representative.severity is Severity.ERROR
    assert representative.title == "Alpha title"
    assert representative.message == "alpha wording"
    assert representative.source_snippet == "alpha"
    assert representative.provenance == tuple(
        sorted(
            (warning.provenance[0], error.provenance[0]),
            key=lambda item: item.engine,
        )
    )


def test_merge_sorts_by_severity_path_location_and_fingerprint() -> None:
    findings = (
        canonicalize(_raw("verilator", "LATCH", path="z.sv", line=9, severity=Severity.INFO)),
        canonicalize(_raw("verilator", "UNDRIVEN", path="b.sv", line=5, severity=Severity.ERROR)),
        canonicalize(_raw("verilator", "WIDTH", path="a.sv", line=8, severity=Severity.WARNING)),
        canonicalize(_raw("verilator", "WIDTH", path="a.sv", line=2, severity=Severity.WARNING)),
    )

    merged = merge_findings(reversed(findings))

    assert [finding.severity for finding in merged] == [
        Severity.ERROR,
        Severity.WARNING,
        Severity.WARNING,
        Severity.INFO,
    ]
    assert [(finding.location.path, finding.location.line) for finding in merged] == [
        ("b.sv", 5),
        ("a.sv", 2),
        ("a.sv", 8),
        ("z.sv", 9),
    ]


def test_merge_json_is_identical_for_every_input_order() -> None:
    findings = (
        canonicalize(_raw("verilator", "WIDTH", message="verilator wording")),
        canonicalize(_raw("pyslang", "constant-conversion", message="pyslang wording")),
        canonicalize(_raw("verilator", "LATCH", path="rtl/control.sv")),
    )

    snapshots = {
        "[" + ",".join(item.model_dump_json() for item in merge_findings(order)) + "]"
        for order in permutations(findings)
    }

    assert len(snapshots) == 1


def test_merge_json_is_identical_when_optional_provenance_values_are_none_or_empty() -> None:
    finding = canonicalize(_raw("verilator", "WIDTH"))
    native = finding.provenance[0]
    none_values = native.model_copy(
        update={"engine_version": None, "symbol": None, "source_snippet": None}
    )
    empty_values = native.model_copy(
        update={"engine_version": "", "symbol": "", "source_snippet": ""}
    )

    snapshots = {
        merge_findings((finding.model_copy(update={"provenance": order}),))[0].model_dump_json()
        for order in permutations((none_values, empty_values))
    }

    assert len(snapshots) == 1


def test_merge_accepts_empty_iterable() -> None:
    assert merge_findings(()) == ()


def test_merge_does_not_mutate_frozen_input() -> None:
    finding = canonicalize(_raw("verilator", "WIDTH"))
    before = finding.model_dump_json()

    merge_findings([finding, finding])

    assert finding.model_dump_json() == before
