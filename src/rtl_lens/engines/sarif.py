"""Conservative ingestion of Verilator's SARIF 2.1.0 diagnostics."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path, PureWindowsPath
from typing import NoReturn
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from rtl_lens.models.diagnostic import RawDiagnostic, Severity, SourceLocation

_DIAGNOSTIC_LIMIT = 10_000
_DIAGNOSTIC_MESSAGE_LIMIT = 4_096
_TRUNCATION_MARKER = "[truncated by rtl-lens]"


class SarifAdapterError(Exception):
    """A structured SARIF ingestion failure safe for the engine boundary."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def parse_verilator_sarif(
    payload: Mapping[str, object],
    root: Path,
) -> tuple[RawDiagnostic, ...]:
    """Validate and translate one Verilator SARIF payload under ``root``."""
    document = _mapping(payload, "SARIF document")
    if _string(document, "version") != "2.1.0":
        _malformed("SARIF version must be '2.1.0'")
    runs = _list(document, "runs")
    if not runs:
        _malformed("SARIF runs must contain a Verilator run")

    resolved_root = root.resolve()
    diagnostics: list[RawDiagnostic] = []
    for run_index, run_value in enumerate(runs):
        run = _mapping(run_value, f"runs[{run_index}]")
        tool = _mapping(_required(run, "tool"), f"runs[{run_index}].tool")
        driver = _mapping(
            _required(tool, "driver"),
            f"runs[{run_index}].tool.driver",
        )
        driver_name = _string(driver, "name")
        if driver_name.casefold() != "verilator":
            _malformed(f"runs[{run_index}].tool.driver.name must be Verilator")
        engine_version = _string(driver, "version")
        results = _list(run, "results")

        for result_index, result_value in enumerate(results):
            if len(diagnostics) == _DIAGNOSTIC_LIMIT:
                raise SarifAdapterError(
                    "diagnostic_limit_exceeded",
                    f"Verilator SARIF exceeded {_DIAGNOSTIC_LIMIT} diagnostics",
                )
            field = f"runs[{run_index}].results[{result_index}]"
            result = _mapping(result_value, field)
            rule_id = _string(result, "ruleId")
            level = _string(result, "level")
            message = _mapping(_required(result, "message"), f"{field}.message")
            message_text = _bounded_message(_string(message, "text"))
            locations = _list(result, "locations")
            if not locations:
                _malformed(f"{field}.locations must contain a physical location")
            location = _mapping(locations[0], f"{field}.locations[0]")
            physical = _mapping(
                _required(location, "physicalLocation"),
                f"{field}.locations[0].physicalLocation",
            )
            artifact = _mapping(
                _required(physical, "artifactLocation"),
                f"{field}.locations[0].physicalLocation.artifactLocation",
            )
            region = _mapping(
                _required(physical, "region"),
                f"{field}.locations[0].physicalLocation.region",
            )
            relative_path = _repository_relative_uri(
                _string(artifact, "uri"),
                resolved_root,
            )
            diagnostics.append(
                RawDiagnostic(
                    engine="verilator",
                    engine_version=engine_version,
                    original_code=rule_id,
                    severity=_severity(level),
                    location=SourceLocation(
                        path=relative_path,
                        line=_positive_int(region, "startLine"),
                        column=_positive_int(region, "startColumn"),
                    ),
                    message=message_text,
                )
            )
    return tuple(diagnostics)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _malformed(f"{field} must be an object")
    return value


def _list(container: Mapping[str, object], field: str) -> list[object]:
    value = _required(container, field)
    if not isinstance(value, list):
        _malformed(f"{field} must be an array")
    return value


def _required(container: Mapping[str, object], field: str) -> object:
    if field not in container:
        _malformed(f"missing required SARIF field: {field}")
    return container[field]


def _string(container: Mapping[str, object], field: str) -> str:
    value = _required(container, field)
    if not isinstance(value, str) or not value:
        _malformed(f"SARIF field {field} must be a non-empty string")
    return value


def _positive_int(container: Mapping[str, object], field: str) -> int:
    value = _required(container, field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _malformed(f"SARIF field {field} must be a positive integer")
    return value


def _severity(level: str) -> Severity:
    if level == "error":
        return Severity.ERROR
    if level == "warning":
        return Severity.WARNING
    if level in {"note", "none"}:
        return Severity.INFO
    _malformed(f"unsupported SARIF result level: {level}")


def _repository_relative_uri(uri: str, root: Path) -> str:
    parsed = urlsplit(uri)
    if parsed.query or parsed.fragment:
        _path_escape(uri)

    if parsed.scheme.casefold() == "file":
        if parsed.netloc not in {"", "localhost"}:
            _path_escape(uri)
        path_text = url2pathname(unquote(parsed.path))
        candidate = Path(path_text)
    elif parsed.scheme:
        if len(parsed.scheme) != 1 or not PureWindowsPath(uri).is_absolute():
            _path_escape(uri)
        if os.name != "nt":
            _path_escape(uri)
        candidate = Path(uri)
    else:
        path_text = unquote(parsed.path)
        if not path_text:
            _path_escape(uri)
        windows_path = PureWindowsPath(path_text)
        if windows_path.is_absolute() and os.name != "nt":
            _path_escape(uri)
        candidate = Path(path_text)

    if not candidate.is_absolute():
        candidate = root / Path(str(candidate).replace("\\", "/"))
    resolved_candidate = candidate.resolve()
    if not resolved_candidate.is_relative_to(root):
        _path_escape(uri)
    return resolved_candidate.relative_to(root).as_posix()


def _bounded_message(message: str) -> str:
    if len(message) <= _DIAGNOSTIC_MESSAGE_LIMIT:
        return message
    prefix_length = _DIAGNOSTIC_MESSAGE_LIMIT - len(_TRUNCATION_MARKER)
    return message[:prefix_length] + _TRUNCATION_MARKER


def _malformed(message: str) -> NoReturn:
    raise SarifAdapterError("malformed_sarif", message)


def _path_escape(uri: str) -> NoReturn:
    raise SarifAdapterError(
        "path_escape",
        f"SARIF artifact URI must resolve beneath the project root: {uri!r}",
    )
