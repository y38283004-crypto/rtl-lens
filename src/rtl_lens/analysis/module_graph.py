"""Pure deterministic normalization of PySlang-shaped module syntax JSON."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet

from rtl_lens.models.analysis import ModuleGraph


def build_module_graph(
    syntax_payloads: Sequence[Mapping[str, object]],
    defined_modules: AbstractSet[str],
) -> ModuleGraph:
    """Build a canonical module graph from untrusted JSON-like syntax payloads."""
    edges: set[tuple[str, str]] = set()
    parents: set[str] = set()
    for payload in syntax_payloads:
        _walk(payload, parent=None, parents=parents, edges=edges)

    definitions = {name for name in defined_modules if _is_name(name)}
    referenced = {child for _, child in edges}
    nodes = definitions | parents | referenced
    return ModuleGraph(
        nodes=tuple(sorted(nodes)),
        edges=tuple(sorted(edges)),
        unresolved=tuple(sorted(referenced - definitions)),
    )


def _walk(
    value: object,
    *,
    parent: str | None,
    parents: set[str],
    edges: set[tuple[str, str]],
) -> None:
    if isinstance(value, Mapping):
        _walk_mapping(value, parent=parent, parents=parents, edges=edges)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _walk(item, parent=parent, parents=parents, edges=edges)


def _walk_mapping(
    value: Mapping[object, object],
    *,
    parent: str | None,
    parents: set[str],
    edges: set[tuple[str, str]],
) -> None:
    kind = value.get("kind")
    next_parent = parent
    if kind == "ModuleDeclaration":
        next_parent = _module_name(value)
        if next_parent is not None:
            parents.add(next_parent)
    elif kind == "HierarchyInstantiation" and parent is not None:
        child = _nested_text(value.get("type"))
        if child is not None:
            edges.add((parent, child))

    for nested in value.values():
        _walk(nested, parent=next_parent, parents=parents, edges=edges)


def _module_name(value: Mapping[object, object]) -> str | None:
    return _nested_text(value.get("header"), "name")


def _nested_text(value: object, *path: str) -> str | None:
    current = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    if not isinstance(current, Mapping):
        return None
    text = current.get("text")
    return text if _is_name(text) else None


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value)
