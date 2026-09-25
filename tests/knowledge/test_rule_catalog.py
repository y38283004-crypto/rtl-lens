"""Catalog contracts for reviewed native diagnostic mappings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

from rtl_lens.knowledge.schema import RuleId
from rtl_lens.knowledge.store import DEFAULT_RULE_IDS, TARGET_RULE_IDS, KnowledgeStore

EXPECTED_CANONICAL_RULE_IDS = {
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
}


def test_schema_declares_exact_target_rule_ids() -> None:
    assert set(get_args(RuleId)) == EXPECTED_CANONICAL_RULE_IDS
    assert TARGET_RULE_IDS == frozenset(EXPECTED_CANONICAL_RULE_IDS)


def test_default_catalog_contains_exactly_the_approved_thirty() -> None:
    store = KnowledgeStore.load_default()

    assert {entry.rule_id for entry in store.entries} == TARGET_RULE_IDS
    assert len(store.entries) == 30


def test_installed_catalog_matches_the_independent_severity_oracle() -> None:
    oracle_path = Path(__file__).parents[1] / "fixtures" / "rules" / "severities.json"
    expected_by_rule = json.loads(oracle_path.read_text(encoding="utf-8"))
    store = KnowledgeStore.load_default()

    assert set(expected_by_rule) == TARGET_RULE_IDS
    assert {entry.rule_id: entry.severity for entry in store.entries} == expected_by_rule


def test_installed_catalog_matches_the_independent_native_code_oracle() -> None:
    oracle_path = Path(__file__).parents[1] / "fixtures" / "rules" / "engine-codes.json"
    expected_by_rule = json.loads(oracle_path.read_text(encoding="utf-8"))
    store = KnowledgeStore.load_default()

    assert set(expected_by_rule) == DEFAULT_RULE_IDS
    assert {
        entry.rule_id: [mapping.model_dump() for mapping in entry.engine_mappings]
        for entry in store.entries
    } == expected_by_rule
    assert store.engine_rules == {
        (mapping["engine"], mapping["code"]): rule_id
        for rule_id, mappings in expected_by_rule.items()
        for mapping in mappings
    }
