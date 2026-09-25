"""Behavior tests for immutable deterministic module relationship graphs."""

from __future__ import annotations

from time import perf_counter

import pytest
from pydantic import ValidationError

from rtl_lens.analysis.module_graph import build_module_graph
from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph, TrendSummary


def test_module_graph_is_sorted_unique_and_preserves_unresolved() -> None:
    payload = {
        "kind": "CompilationUnit",
        "members": [
            {
                "kind": "ModuleDeclaration",
                "header": {"name": {"text": "top"}},
                "members": [
                    {"kind": "HierarchyInstantiation", "type": {"text": "alu"}},
                    {"kind": "HierarchyInstantiation", "type": {"text": "missing_ip"}},
                    {"kind": "HierarchyInstantiation", "type": {"text": "alu"}},
                ],
            }
        ],
    }

    graph = build_module_graph((payload,), frozenset({"top", "alu"}))

    assert graph.nodes == ("alu", "missing_ip", "top")
    assert graph.edges == (("top", "alu"), ("top", "missing_ip"))
    assert graph.unresolved == ("missing_ip",)


def test_module_graph_walks_nested_mappings_and_sequences() -> None:
    payload = {
        "kind": "ModuleDeclaration",
        "header": {"name": {"text": "top"}},
        "members": [
            {
                "kind": "GenerateBlock",
                "branches": [
                    {"kind": "HierarchyInstantiation", "type": {"text": "nested"}},
                    {"kind": "HierarchyInstantiation", "type": {"text": "second"}},
                ],
            }
        ],
    }

    graph = build_module_graph((payload,), frozenset({"top", "nested", "second"}))

    assert graph.edges == (("top", "nested"), ("top", "second"))


def test_module_graph_ignores_malformed_or_non_string_tokens() -> None:
    payload = {
        "kind": "CompilationUnit",
        "members": [
            {
                "kind": "ModuleDeclaration",
                "header": {"name": {"text": 42}},
                "members": [{"kind": "HierarchyInstantiation", "type": {"text": "ignored"}}],
            },
            {
                "kind": "ModuleDeclaration",
                "header": {"name": {"text": "top"}},
                "members": [
                    {"kind": "HierarchyInstantiation", "type": {"text": None}},
                    {"kind": "HierarchyInstantiation", "type": {"text": ["child"]}},
                    {"kind": "HierarchyInstantiation", "type": {"text": "child"}},
                ],
            },
            "not-a-syntax-mapping",
        ],
    }

    graph = build_module_graph((payload,), frozenset({"top", 3}))  # type: ignore[arg-type]

    assert graph.nodes == ("child", "top")
    assert graph.edges == (("top", "child"),)
    assert graph.unresolved == ("child",)


def test_module_graph_deduplicates_declarations_and_empty_projects_are_stable() -> None:
    declaration = {
        "kind": "ModuleDeclaration",
        "header": {"name": {"text": "top"}},
        "members": [{"kind": "HierarchyInstantiation", "type": {"text": "child"}}],
    }

    graph = build_module_graph((declaration, declaration), frozenset({"top", "child"}))

    assert graph.nodes == ("child", "top")
    assert graph.edges == (("top", "child"),)
    assert graph.unresolved == ()
    assert build_module_graph((), frozenset()).model_dump_json() == (
        '{"nodes":[],"edges":[],"unresolved":[]}'
    )


def test_module_graph_serialization_is_identical_for_reversed_inputs() -> None:
    left = {
        "kind": "ModuleDeclaration",
        "header": {"name": {"text": "left"}},
        "members": [{"kind": "HierarchyInstantiation", "type": {"text": "child"}}],
    }
    right = {
        "kind": "ModuleDeclaration",
        "header": {"name": {"text": "right"}},
        "members": [{"kind": "HierarchyInstantiation", "type": {"text": "child"}}],
    }

    forward = build_module_graph((left, right), frozenset({"right", "child", "left"}))
    reversed_graph = build_module_graph((right, left), frozenset({"left", "child", "right"}))

    assert forward.model_dump_json() == reversed_graph.model_dump_json()


def test_analysis_models_are_frozen_strict_and_canonical() -> None:
    graph = ModuleGraph(nodes=("child", "top"), edges=(("top", "child"),))
    warning = AnalysisWarning(kind="  semantic  ", message="  unavailable module  ")

    assert warning.kind == "semantic"
    assert warning.message == "unavailable module"
    with pytest.raises(ValidationError):
        graph.nodes = ()  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ModuleGraph(nodes=("top", "child"))
    with pytest.raises(ValidationError):
        ModuleGraph(nodes=("child", "child"))
    with pytest.raises(ValidationError):
        ModuleGraph(nodes=("top",), edges=(("top", "child"),))
    with pytest.raises(ValidationError):
        AnalysisWarning(kind="warning", message="message", extra="value")
    with pytest.raises(ValidationError):
        AnalysisWarning(kind="   ", message="message")
    with pytest.raises(ValidationError):
        TrendSummary(new=("second", "first"))
    with pytest.raises(ValidationError):
        TrendSummary(new=("same",), resolved=("same",))


def test_large_graph_validation_fits_the_minimum_worker_deadline_budget() -> None:
    """Endpoint validation must stay linear enough for the one-second worker budget."""
    nodes = tuple(f"node-{index:05d}" for index in range(15_000))
    edges = tuple((nodes[index], nodes[index + 1]) for index in range(len(nodes) - 1))

    started_at = perf_counter()
    graph = ModuleGraph(nodes=nodes, edges=edges, unresolved=nodes)
    elapsed = perf_counter() - started_at

    assert graph.edges[-1] == ("node-14998", "node-14999")
    assert elapsed < 1.0, f"large graph validation took {elapsed:.3f}s"
