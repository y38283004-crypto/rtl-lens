"""Real engine contracts for native-code evidence in packaged examples."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from conftest import run_example

from rtl_lens.engines.pyslang_engine import PySlangEngine
from rtl_lens.engines.verilator_engine import VerilatorEngine
from rtl_lens.knowledge.schema import ExplanationEntry
from rtl_lens.knowledge.store import KnowledgeStore

requires_verilator = pytest.mark.skipif(
    shutil.which("verilator") is None,
    reason="real Verilator mapping evidence requires the pinned container",
)

LOCAL_ENTRIES = tuple(
    entry
    for entry in KnowledgeStore.load_default().entries
    if any(mapping.engine == "pyslang" for mapping in entry.engine_mappings)
)
VERILATOR_ENTRIES = tuple(
    entry
    for entry in KnowledgeStore.load_default().entries
    if any(mapping.engine == "verilator" for mapping in entry.engine_mappings)
)


def test_verilator_example_cases_cover_the_independent_oracle() -> None:
    oracle_path = Path(__file__).parents[1] / "fixtures" / "rules" / "engine-codes.json"
    expected_by_rule = json.loads(oracle_path.read_text(encoding="utf-8"))
    expected_rule_ids = {
        rule_id
        for rule_id, mappings in expected_by_rule.items()
        if any(mapping["engine"] == "verilator" for mapping in mappings)
    }

    assert {entry.rule_id for entry in VERILATOR_ENTRIES} == expected_rule_ids


@pytest.mark.parametrize("entry", LOCAL_ENTRIES, ids=lambda entry: entry.rule_id)
def test_pyslang_mapping_is_emitted_only_by_the_failing_example(
    entry: ExplanationEntry, tmp_path: Path
) -> None:
    failing = run_example(entry, "failing", tmp_path / "failing", PySlangEngine())
    fixed = run_example(entry, "fixed", tmp_path / "fixed", PySlangEngine())
    expected = {mapping.code for mapping in entry.engine_mappings if mapping.engine == "pyslang"}

    assert expected <= {diagnostic.original_code for diagnostic in failing.diagnostics}
    assert expected.isdisjoint(diagnostic.original_code for diagnostic in fixed.diagnostics)


@requires_verilator
@pytest.mark.parametrize("entry", VERILATOR_ENTRIES, ids=lambda entry: entry.rule_id)
def test_verilator_mapping_is_emitted_only_by_the_failing_example(
    entry: ExplanationEntry, tmp_path: Path
) -> None:
    failing = run_example(entry, "failing", tmp_path / "failing", VerilatorEngine())
    fixed = run_example(entry, "fixed", tmp_path / "fixed", VerilatorEngine())
    expected = {mapping.code for mapping in entry.engine_mappings if mapping.engine == "verilator"}

    assert expected <= {diagnostic.original_code for diagnostic in failing.diagnostics}
    assert expected.isdisjoint(diagnostic.original_code for diagnostic in fixed.diagnostics)
