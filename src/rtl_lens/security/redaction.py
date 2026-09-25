"""Deterministic immutable redaction for reports intended to be shared."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph
from rtl_lens.models.diagnostic import Finding, RawDiagnostic, SourceLocation
from rtl_lens.models.engine import EngineFailure, EngineRun
from rtl_lens.models.report import ScanReport


@dataclass(frozen=True)
class RedactionPolicy:
    """Explicit values that may be removed from a shareable report."""

    home: Path | None = None
    path_prefixes: tuple[Path, ...] = ()
    secret_values: tuple[str, ...] = field(default=(), repr=False)

    @classmethod
    def from_environment(
        cls,
        *,
        home: Path | None = None,
        path_prefixes: tuple[Path, ...] = (),
        variable_names: tuple[str, ...] = (),
        environment: Mapping[str, str] | None = None,
    ) -> RedactionPolicy:
        """Read only the exact, explicitly named non-empty environment values."""
        values = os.environ if environment is None else environment
        secrets = tuple(
            sorted(
                {values[name] for name in variable_names if values.get(name)},
                key=lambda value: (-len(value), value),
            )
        )
        return cls(home=home, path_prefixes=path_prefixes, secret_values=secrets)


def default_redaction_policy() -> RedactionPolicy:
    """Return the safe default used by reports already marked as redacted."""
    return RedactionPolicy(home=Path.home())


def redact_report(report: ScanReport, policy: RedactionPolicy) -> ScanReport:
    """Return a redacted copy without mutating or restructuring stable identifiers."""
    project_marker = _project_marker(policy)
    project_root = (
        None
        if report.metadata.redacted and report.metadata.project_root == project_marker
        else report.metadata.project_root
    )
    redactor = _Redactor(project_root, policy)
    redacted = report.model_copy(
        update={
            "metadata": report.metadata.model_copy(
                update={"project_root": redactor.project_marker, "redacted": True}
            ),
            "findings": tuple(_redact_finding(item, redactor) for item in report.findings),
            "engine_runs": tuple(_redact_engine_run(item, redactor) for item in report.engine_runs),
            "module_graph": _redact_graph(report.module_graph, redactor),
            "analysis_warnings": tuple(
                _redact_warning(item, redactor) for item in report.analysis_warnings
            ),
        },
        deep=True,
    )
    return ScanReport.model_validate(redacted.model_dump(mode="python"))


class _Redactor:
    def __init__(self, project_root: str | None, policy: RedactionPolicy) -> None:
        secrets = tuple(
            sorted(
                {value for value in policy.secret_values if value}, key=lambda value: -len(value)
            )
        )
        policy_path_values = (() if policy.home is None else (str(policy.home),)) + tuple(
            str(prefix) for prefix in policy.path_prefixes
        )
        path_values = (() if project_root is None else (project_root,)) + policy_path_values
        forbidden = tuple(value for value in path_values + secrets if value)
        markers: dict[str, str] = {"project": _project_marker(policy)}
        for label, preferred in (
            ("home", "<home>"),
            ("path", "<redacted-path>"),
            ("secret", "<redacted-secret>"),
        ):
            markers[label] = _safe_marker(
                preferred,
                forbidden=forbidden + tuple(markers.values()),
                label=label,
            )

        path_replacements: list[tuple[str, str, int]] = []
        if project_root is not None:
            path_replacements.append((project_root, markers["project"], 0))
        if policy.home is not None:
            path_replacements.append((str(policy.home), markers["home"], 1))
        path_replacements.extend(
            (str(prefix), markers["path"], 2) for prefix in policy.path_prefixes
        )

        unique_patterns: dict[str, tuple[re.Pattern[str], str, int, int]] = {}
        for value, replacement, priority in path_replacements:
            if not value:
                continue
            pattern = _path_pattern(value)
            key = pattern.pattern.casefold()
            current = unique_patterns.get(key)
            if current is None or priority < current[2]:
                unique_patterns[key] = (pattern, replacement, priority, len(value))
        self._paths = tuple(
            (pattern, replacement)
            for pattern, replacement, priority, length in sorted(
                unique_patterns.values(),
                key=lambda item: (-item[3], item[2], item[0].pattern.casefold()),
            )
        )
        self._secrets = secrets
        self._project_marker = markers["project"]
        self._secret_marker = markers["secret"]

    @property
    def project_marker(self) -> str:
        """Return the policy-safe marker used for project-root text."""
        return self._project_marker

    def text(self, value: str) -> str:
        redacted = value
        for pattern, replacement in self._paths:
            redacted = pattern.sub(replacement, redacted)
        for secret in self._secrets:
            redacted = redacted.replace(secret, self._secret_marker)
        return redacted

    def optional(self, value: str | None) -> str | None:
        return None if value is None else self.text(value)


def _path_pattern(value: str) -> re.Pattern[str]:
    tokens = re.split(r"([\\/]+)", value)
    expression = "".join(
        r"[\\/]+" if re.fullmatch(r"[\\/]+", token) else re.escape(token)
        for token in tokens
        if token
    )
    return re.compile(expression, flags=re.IGNORECASE)


def _project_marker(policy: RedactionPolicy) -> str:
    forbidden = (
        (() if policy.home is None else (str(policy.home),))
        + tuple(str(prefix) for prefix in policy.path_prefixes)
        + tuple(value for value in policy.secret_values if value)
    )
    return _safe_marker("<project>", forbidden=forbidden, label="project")


def _safe_marker(preferred: str, *, forbidden: tuple[str, ...], label: str) -> str:
    folded = tuple(value.casefold() for value in forbidden if value)

    def safe(candidate: str) -> bool:
        candidate_folded = candidate.casefold()
        return all(value not in candidate_folded for value in folded)

    if safe(preferred):
        return preferred
    for counter in range(1024):
        digest = hashlib.sha256(f"rtl-lens:{label}:{counter}".encode()).hexdigest()
        candidate = f"<{digest}>"
        if safe(candidate):
            return candidate
    for codepoint in range(0xE000, 0xF900):
        candidate = chr(codepoint) * 8
        if safe(candidate):
            return candidate
    raise ValueError("sensitive values exhaust the redaction marker namespace")


def _redact_location(location: SourceLocation, redactor: _Redactor) -> SourceLocation:
    return location.model_copy(update={"path": redactor.text(location.path)})


def _redact_raw(item: RawDiagnostic, redactor: _Redactor) -> RawDiagnostic:
    return item.model_copy(
        update={
            "engine_version": redactor.optional(item.engine_version),
            "original_code": redactor.text(item.original_code),
            "location": _redact_location(item.location, redactor),
            "message": redactor.text(item.message),
            "symbol": redactor.optional(item.symbol),
            "source_snippet": None,
        },
        deep=True,
    )


def _redact_finding(item: Finding, redactor: _Redactor) -> Finding:
    return item.model_copy(
        update={
            "location": _redact_location(item.location, redactor),
            "title": redactor.text(item.title),
            "message": redactor.text(item.message),
            "symbol": redactor.optional(item.symbol),
            "source_snippet": None,
            "provenance": tuple(_redact_raw(raw, redactor) for raw in item.provenance),
        },
        deep=True,
    )


def _redact_warning(item: AnalysisWarning, redactor: _Redactor) -> AnalysisWarning:
    return item.model_copy(update={"message": redactor.text(item.message)})


def _redact_graph(graph: ModuleGraph, redactor: _Redactor) -> ModuleGraph:
    nodes = tuple(sorted({redactor.text(node) for node in graph.nodes}))
    edges = tuple(
        sorted({(redactor.text(parent), redactor.text(child)) for parent, child in graph.edges})
    )
    unresolved = tuple(sorted({redactor.text(node) for node in graph.unresolved}))
    return ModuleGraph(nodes=nodes, edges=edges, unresolved=unresolved)


def _redact_engine_run(item: EngineRun, redactor: _Redactor) -> EngineRun:
    failure: EngineFailure | None = None
    if item.failure is not None:
        failure = item.failure.model_copy(update={"message": redactor.text(item.failure.message)})
    return item.model_copy(
        update={
            "version": redactor.optional(item.version),
            "diagnostics": tuple(_redact_raw(raw, redactor) for raw in item.diagnostics),
            "failure": failure,
            "module_graph": (
                None if item.module_graph is None else _redact_graph(item.module_graph, redactor)
            ),
            "analysis_warnings": tuple(
                _redact_warning(warning, redactor) for warning in item.analysis_warnings
            ),
        },
        deep=True,
    )
