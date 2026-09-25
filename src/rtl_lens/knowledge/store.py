"""Deterministic, offline loading for packaged explanation resources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

import yaml

from rtl_lens.knowledge.schema import ExplanationEntry, LocalizedExplanation

TARGET_RULE_IDS = frozenset(
    {
        "width-mismatch",
        "incomplete-assignment",
        "case-incomplete",
        "case-overlap",
        "unused-signal",
        "undriven-signal",
        "multiple-drivers",
        "blocking-in-sequential",
        "always-comb-order",
        "always-never",
        "ascending-range",
        "assignment-in-expression",
        "assignment-to-input",
        "blocking-and-nonblocking",
        "case-with-x",
        "case-x",
        "constant-comparison",
        "combinational-delay",
        "declaration-filename",
        "deprecated-defparam",
        "implicit-net",
        "port-width-mismatch",
        "missing-pin",
        "empty-pin-connection",
        "signedness-mismatch",
        "out-of-range-select",
        "duplicate-definition",
        "undeclared-identifier",
        "unsupported-construct",
        "timescale-mismatch",
    }
)
DEFAULT_RULE_IDS = TARGET_RULE_IDS


class KnowledgeStore:
    """Immutable index of reviewed explanation entries."""

    def __init__(self, entries: Sequence[ExplanationEntry]) -> None:
        ordered = tuple(sorted(entries, key=lambda entry: entry.rule_id))
        index: dict[str, ExplanationEntry] = {}
        engine_rules: dict[tuple[str, str], str] = {}
        for entry in ordered:
            if entry.rule_id in index:
                raise ValueError(f"duplicate rule id: {entry.rule_id}")
            index[entry.rule_id] = entry
            for mapping in entry.engine_mappings:
                native_key = (mapping.engine, mapping.code)
                existing_rule_id = engine_rules.get(native_key)
                if existing_rule_id is not None and existing_rule_id != entry.rule_id:
                    raise ValueError(
                        "native mapping "
                        f"{mapping.engine}:{mapping.code} is assigned to both "
                        f"{existing_rule_id} and {entry.rule_id}"
                    )
                engine_rules[native_key] = entry.rule_id
        self._entries = ordered
        self._index = MappingProxyType(index)
        self._engine_rules = MappingProxyType(engine_rules)

    @classmethod
    def load_default(cls) -> KnowledgeStore:
        root = resources.files("rtl_lens.knowledge")
        return cls(load_entries(root.joinpath("rules"), root.joinpath("examples")))

    @property
    def entries(self) -> tuple[ExplanationEntry, ...]:
        return self._entries

    @property
    def engine_rules(self) -> Mapping[tuple[str, str], str]:
        """Return the immutable reviewed native-code index."""
        return self._engine_rules

    def __len__(self) -> int:
        return len(self._entries)

    def get(
        self,
        rule_id: str,
        language: Literal["en", "zh-CN"],
    ) -> LocalizedExplanation | None:
        if language not in {"en", "zh-CN"}:
            raise ValueError(f"unsupported language: {language}")
        entry = self._index.get(rule_id)
        if entry is None:
            return None
        return entry.en if language == "en" else entry.zh_cn


def load_entries(
    rules_root: Traversable | Path,
    examples_root: Traversable | Path,
    *,
    require_default_ids: bool = True,
) -> tuple[ExplanationEntry, ...]:
    entries: list[ExplanationEntry] = []
    for resource in sorted(rules_root.iterdir(), key=lambda item: item.name):
        if not resource.name.endswith(".yaml") or not resource.is_file():
            continue
        payload = yaml.safe_load(resource.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise TypeError(f"knowledge rule must be a mapping: {resource.name}")
        entry = ExplanationEntry.model_validate(cast(Mapping[str, object], payload))
        entries.append(entry)

    store = KnowledgeStore(entries)
    ids = {entry.rule_id for entry in store.entries}
    if require_default_ids and ids != DEFAULT_RULE_IDS:
        raise ValueError("default knowledge base must contain the exact reviewed rule IDs")
    for entry in store.entries:
        _validate_resource(examples_root, entry.failing_example)
        _validate_resource(examples_root, entry.fixed_example)
    return store.entries


def _validate_resource(root: Traversable | Path, relative_path: str) -> None:
    resource = root.joinpath(*_pure_path_parts(relative_path))
    if not resource.is_file() or not resource.read_text(encoding="utf-8").strip():
        raise ValueError(f"example resource is missing or empty: {relative_path}")


def _pure_path_parts(relative_path: str) -> tuple[str, ...]:
    """Return validated POSIX path components without filesystem interpretation."""
    return tuple(relative_path.split("/"))
