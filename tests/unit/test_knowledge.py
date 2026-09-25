"""Behavior tests for the packaged bilingual knowledge base."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest
from pydantic import ValidationError
from yaml import YAMLError

from rtl_lens.knowledge.schema import EngineMapping, ExplanationEntry
from rtl_lens.knowledge.store import KnowledgeStore, load_entries

RULE_IDS = (
    "always-comb-order",
    "always-never",
    "ascending-range",
    "assignment-in-expression",
    "assignment-to-input",
    "blocking-and-nonblocking",
    "blocking-in-sequential",
    "case-incomplete",
    "case-overlap",
    "case-with-x",
    "case-x",
    "combinational-delay",
    "constant-comparison",
    "declaration-filename",
    "deprecated-defparam",
    "duplicate-definition",
    "empty-pin-connection",
    "implicit-net",
    "incomplete-assignment",
    "missing-pin",
    "multiple-drivers",
    "out-of-range-select",
    "port-width-mismatch",
    "signedness-mismatch",
    "timescale-mismatch",
    "undeclared-identifier",
    "undriven-signal",
    "unsupported-construct",
    "unused-signal",
    "width-mismatch",
)


@pytest.fixture
def sample_entries() -> tuple[ExplanationEntry, ExplanationEntry]:
    entries = KnowledgeStore.load_default().entries
    return entries[0], entries[1]


def test_default_store_is_complete_bilingual_and_deterministic() -> None:
    first = KnowledgeStore.load_default()
    second = KnowledgeStore.load_default()

    assert len(first) == 30
    assert tuple(entry.rule_id for entry in first.entries) == RULE_IDS
    assert first.entries == second.entries
    for entry in first.entries:
        for localized in (entry.en, entry.zh_cn):
            assert all(
                len(value) >= 8
                for value in (localized.title, localized.cause, localized.risk, localized.fix)
            )
        assert any("\u4e00" <= char <= "\u9fff" for char in entry.zh_cn.cause)
        assert entry.en != entry.zh_cn
        assert entry.references


def test_lookup_language_and_unknown_behavior() -> None:
    store = KnowledgeStore.load_default()

    assert store.get("width-mismatch", "en") == store.entries[-1].en
    assert store.get("width-mismatch", "zh-CN") == store.entries[-1].zh_cn
    assert store.get("not-known", "en") is None
    with pytest.raises(ValueError, match="language"):
        store.get("width-mismatch", "fr")  # type: ignore[arg-type]


def test_entries_are_frozen_and_forbid_unknown_fields() -> None:
    entry = KnowledgeStore.load_default().entries[0]
    with pytest.raises(ValidationError):
        entry.rule_id = "width-mismatch"  # type: ignore[misc]
    payload = entry.model_dump(by_alias=True)
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        ExplanationEntry.model_validate(payload)


def test_entry_requires_mapping_or_research_note() -> None:
    payload = KnowledgeStore.load_default().entries[0].model_dump(by_alias=True)
    payload.pop("engine_mappings")

    with pytest.raises(ValidationError, match="mapping"):
        ExplanationEntry.model_validate(payload)

    payload["mapping_note"] = "No stable native code is available yet."
    assert ExplanationEntry.model_validate(payload).mapping_note == payload["mapping_note"]


def test_entry_rejects_duplicate_or_unsorted_native_mappings() -> None:
    payload = KnowledgeStore.load_default().entries[-1].model_dump(by_alias=True)
    duplicate = {
        "engine": "pyslang",
        "code": "constant-conversion",
        "verification": "local",
    }
    payload["engine_mappings"] = [duplicate, duplicate]
    with pytest.raises(ValidationError, match="duplicate native mapping"):
        ExplanationEntry.model_validate(payload)

    payload["engine_mappings"] = [
        {"engine": "verilator", "code": "WIDTH", "verification": "container"},
        duplicate,
    ]
    with pytest.raises(ValidationError, match="sorted"):
        ExplanationEntry.model_validate(payload)


def test_engine_mapping_rejects_control_characters() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        EngineMapping(engine="pyslang", code="width\nexpand", verification="local")


def test_store_rejects_conflicting_native_mapping(
    sample_entries: tuple[ExplanationEntry, ExplanationEntry],
) -> None:
    first, second = sample_entries
    duplicate = EngineMapping(engine="verilator", code="WIDTH", verification="container")

    with pytest.raises(ValueError, match="native mapping"):
        KnowledgeStore(
            (
                first.model_copy(update={"engine_mappings": (duplicate,)}),
                second.model_copy(update={"engine_mappings": (duplicate,)}),
            )
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("failing_example", "failing//width-mismatch.sv"),
        ("failing_example", "failing/./width-mismatch.sv"),
        ("fixed_example", "failing/width-mismatch.sv"),
    ],
)
def test_example_paths_preserve_their_role_and_reject_collapsed_components(
    field: str, value: str
) -> None:
    payload = KnowledgeStore.load_default().entries[-1].model_dump(by_alias=True)
    payload[field] = value

    with pytest.raises(ValidationError, match="example path"):
        ExplanationEntry.model_validate(payload)


def test_packaged_examples_are_addressable_distinct_and_coherent() -> None:
    example_root = resources.files("rtl_lens.knowledge").joinpath("examples")
    expected: set[str] = set()
    for entry in KnowledgeStore.load_default().entries:
        expected.update((entry.failing_example, entry.fixed_example))
        failing = example_root.joinpath(entry.failing_example)
        fixed = example_root.joinpath(entry.fixed_example)
        assert failing.is_file() and fixed.is_file()
        failing_text = failing.read_text(encoding="utf-8")
        fixed_text = fixed.read_text(encoding="utf-8")
        assert failing_text != fixed_text
        for text in (failing_text, fixed_text):
            assert "module " in text
            assert "endmodule" in text
    assert len(expected) == 60


def test_loader_rejects_duplicate_ids_and_escaping_examples(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    examples = tmp_path / "examples"
    rules.mkdir()
    examples.mkdir()
    valid = """
schema_version: "1.0"
rule_id: width-mismatch
severity: error
en: {title: Width error, cause: Widths are different, risk: Data can be truncated, fix: Make widths explicit}
zh-CN: {title: 位宽错误说明, cause: 两侧位宽并不一致, risk: 数据可能发生截断, fix: 请明确统一信号位宽}
failing_example: failing/width-mismatch.sv
fixed_example: fixed/width-mismatch.sv
references: [https://example.invalid/reference]
review_status: reviewed
mapping_note: Test data has no asserted native mapping.
"""
    (rules / "a.yaml").write_text(valid, encoding="utf-8")
    (rules / "b.yaml").write_text(valid, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_entries(rules, examples, require_default_ids=False)

    (rules / "b.yaml").unlink()
    (rules / "a.yaml").write_text(valid.replace("failing/", "../"), encoding="utf-8")
    with pytest.raises((ValueError, ValidationError), match="path|relative|example"):
        load_entries(rules, examples, require_default_ids=False)


def test_loader_rejects_malformed_yaml_and_missing_translation(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    examples = tmp_path / "examples"
    rules.mkdir()
    examples.mkdir()

    (rules / "broken.yaml").write_text("en: [unterminated", encoding="utf-8")
    with pytest.raises(YAMLError):
        load_entries(rules, examples, require_default_ids=False)

    (rules / "broken.yaml").write_text(
        """
schema_version: "1.0"
rule_id: width-mismatch
severity: error
en: {title: Width error, cause: Widths are different, risk: Data can be truncated, fix: Make widths explicit}
failing_example: failing/width-mismatch.sv
fixed_example: fixed/width-mismatch.sv
references: [https://example.invalid/reference]
review_status: reviewed
mapping_note: Test data has no asserted native mapping.
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="zh-CN"):
        load_entries(rules, examples, require_default_ids=False)


def test_loader_rejects_missing_examples_and_incomplete_default_ids(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    examples = tmp_path / "examples"
    rules.mkdir()
    examples.mkdir()
    (rules / "width-mismatch.yaml").write_text(
        """
schema_version: "1.0"
rule_id: width-mismatch
severity: error
en: {title: Width error, cause: Widths are different, risk: Data can be truncated, fix: Make widths explicit}
zh-CN: {title: 位宽错误说明, cause: 两侧位宽并不一致, risk: 数据可能发生截断, fix: 请明确统一信号位宽}
failing_example: failing/width-mismatch.sv
fixed_example: fixed/width-mismatch.sv
references: [https://example.invalid/reference]
review_status: reviewed
mapping_note: Test data has no asserted native mapping.
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="example"):
        load_entries(rules, examples, require_default_ids=False)

    (examples / "failing").mkdir()
    (examples / "fixed").mkdir()
    for kind in ("failing", "fixed"):
        (examples / kind / "width-mismatch.sv").write_text(
            "module width_mismatch; endmodule\n", encoding="utf-8"
        )
    with pytest.raises(ValueError, match="rule IDs"):
        load_entries(rules, examples, require_default_ids=True)
