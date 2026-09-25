"""Canonical diagnostic rules and stable finding fingerprints."""

from __future__ import annotations

import json
import posixpath
from collections.abc import Mapping
from hashlib import sha256
from typing import Final

from rtl_lens.knowledge.store import TARGET_RULE_IDS, KnowledgeStore
from rtl_lens.models.diagnostic import Finding, RawDiagnostic, SourceLocation

ENGINE_RULES: Final[Mapping[tuple[str, str], str]] = KnowledgeStore.load_default().engine_rules

_KNOWN_RULES = TARGET_RULE_IDS
_UNKNOWN_PREFIX = "engine-native:"


def canonicalize(raw: RawDiagnostic) -> Finding:
    """Convert one native engine diagnostic into an immutable canonical finding."""
    canonical_rule = ENGINE_RULES.get(
        (raw.engine, raw.original_code),
        f"{_UNKNOWN_PREFIX}{raw.engine}:{raw.original_code}",
    )
    finding = Finding(
        fingerprint="",
        canonical_rule=canonical_rule,
        severity=raw.severity,
        location=_normalized_location(raw.location),
        title=_title(canonical_rule, raw.original_code),
        message=raw.message,
        symbol=raw.symbol,
        source_snippet=raw.source_snippet,
        provenance=(raw,),
    )
    return finding.model_copy(update={"fingerprint": fingerprint(finding)})


def fingerprint(finding: Finding) -> str:
    """Return the stable identity digest for a canonical or engine-native finding."""
    payload: dict[str, object] = {
        "canonical_rule": finding.canonical_rule,
        "path": _normalize_path(finding.location.path),
        "line": finding.location.line,
        "column": finding.location.column,
        "symbol": finding.symbol,
    }
    if finding.canonical_rule not in _KNOWN_RULES:
        engine, original_code, message = _unknown_fields(finding)
        payload.update(
            {
                "engine": engine,
                "original_code": original_code,
                "message_digest": sha256(_normalize_message(message).encode("utf-8")).hexdigest(),
            }
        )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(serialized).hexdigest()


def _normalized_location(location: SourceLocation) -> SourceLocation:
    return location.model_copy(update={"path": _normalize_path(location.path)})


def _normalize_path(path: str) -> str:
    candidate = path.replace("\\", "/")
    if not candidate or candidate.startswith("/") or (len(candidate) >= 2 and candidate[1] == ":"):
        raise ValueError(f"diagnostic path must be repository-relative: {path!r}")

    normalized = posixpath.normpath(candidate)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise ValueError(f"diagnostic path must be repository-relative: {path!r}")
    return normalized


def _unknown_fields(finding: Finding) -> tuple[str, str, str]:
    if not finding.provenance:
        return "", finding.canonical_rule, finding.message
    native = min(
        finding.provenance,
        key=lambda item: (
            item.engine,
            item.original_code,
            _normalize_message(item.message),
        ),
    )
    return native.engine, native.original_code, native.message


def _normalize_message(message: str) -> str:
    return " ".join(message.split())


def _title(canonical_rule: str, original_code: str) -> str:
    if canonical_rule.startswith(_UNKNOWN_PREFIX):
        return original_code
    return canonical_rule.replace("-", " ").capitalize()
