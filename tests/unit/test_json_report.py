"""Behavior tests for stable, atomic JSON report output."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import pytest

from rtl_lens.models.analysis import AnalysisWarning, ModuleGraph, TrendSummary
from rtl_lens.models.report import ScanReport
from rtl_lens.renderers import json_report
from rtl_lens.renderers.json_report import write_json_report

FIXTURE = Path(__file__).parents[1] / "fixtures" / "reports" / "width-report.json"


def _sample_report() -> ScanReport:
    return ScanReport.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def _assert_no_score_fields(value: Any) -> None:
    if isinstance(value, dict):
        assert not {"health_score", "overall_score", "score"}.intersection(value)
        for child in value.values():
            _assert_no_score_fields(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_score_fields(child)


def test_json_report_emits_stable_schema_and_repeatable_utf8_bytes(tmp_path: Path) -> None:
    report = _sample_report()
    destination = tmp_path / "report.json"

    write_json_report(report, destination)
    first = destination.read_bytes()
    write_json_report(report, destination)

    assert destination.read_bytes() == first
    assert first == (report.model_dump_json(indent=2) + "\n").encode("utf-8")
    payload = json.loads(first)
    assert payload["schema_version"] == "1.0"
    assert payload["findings"][0]["canonical_rule"] == "width-mismatch"
    assert "芯片" in first.decode("utf-8")
    _assert_no_score_fields(payload)


def test_json_report_keeps_complete_graph_trends_and_warnings_without_display_cap(
    tmp_path: Path,
) -> None:
    hostile = '</script><script id="json-owned">window.__jsonOwned=1</script>'
    edges = tuple(
        sorted(
            [(f"parent-{index:03d}", f"child-{index:03d}") for index in range(205)]
            + [("hostile-parent", hostile)]
        )
    )
    isolated = 'isolated-</script><script id="isolated-owned"></script>'
    nodes = tuple(sorted({name for edge in edges for name in edge} | {isolated}))
    report = _sample_report().model_copy(
        update={
            "module_graph": ModuleGraph(
                nodes=nodes,
                edges=edges,
                unresolved=(hostile,),
            ),
            "trends": TrendSummary(
                new=("new-fingerprint",),
                unchanged=("unchanged-fingerprint",),
                resolved=("resolved-fingerprint",),
                baseline_configuration_known=True,
                baseline_configured=True,
                comparison_complete=True,
            ),
            "analysis_warnings": (
                AnalysisWarning(kind="module_graph", message="hostile warning <unsafe>"),
            ),
        }
    )
    destination = tmp_path / "report.json"

    write_json_report(report, destination)
    first = destination.read_bytes()
    write_json_report(report, destination)

    assert destination.read_bytes() == first
    payload = json.loads(first)
    assert payload["module_graph"]["nodes"] == list(nodes)
    assert payload["module_graph"]["edges"] == [list(edge) for edge in edges]
    assert len(payload["module_graph"]["edges"]) == 206
    assert payload["module_graph"]["unresolved"] == [hostile]
    assert payload["trends"] == {
        "new": ["new-fingerprint"],
        "unchanged": ["unchanged-fingerprint"],
        "resolved": ["resolved-fingerprint"],
        "baseline_configured": True,
        "baseline_configuration_known": True,
        "comparison_complete": True,
    }
    assert payload["analysis_warnings"] == [
        {"kind": "module_graph", "message": "hostile warning <unsafe>"}
    ]


def test_json_report_atomically_replaces_destination_without_temp_residue(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "report.json"
    destination.write_text("old report", encoding="utf-8")

    write_json_report(_sample_report(), destination)

    assert json.loads(destination.read_text(encoding="utf-8"))["schema_version"] == "1.0"
    assert set(tmp_path.iterdir()) == {destination}


def test_json_report_replace_failure_preserves_destination_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.json"
    original = b"old report"
    destination.write_bytes(original)

    def fail_replace(source: str | Path, target: str | Path) -> None:
        temporary = Path(source)
        assert temporary.parent == destination.parent
        assert Path(target) == destination
        assert temporary.read_text(encoding="utf-8").endswith("\n")
        raise OSError("replace failed")

    monkeypatch.setattr(json_report.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_json_report(_sample_report(), destination)

    assert destination.read_bytes() == original
    assert set(tmp_path.iterdir()) == {destination}


def test_json_report_uses_unique_same_directory_temps_for_concurrent_writers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.json"
    real_replace = json_report.os.replace
    barrier = Barrier(2)
    lock = Lock()
    temporary_paths: list[Path] = []

    def synchronized_replace(source: str | Path, target: str | Path) -> None:
        with lock:
            temporary_paths.append(Path(source))
        barrier.wait(timeout=5)
        # Windows may reject two simultaneous replacements of one destination.
        # Serialize only the native replace after both unique source paths exist.
        with lock:
            real_replace(source, target)

    monkeypatch.setattr(json_report.os, "replace", synchronized_replace)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(write_json_report, _sample_report(), destination) for _ in range(2)
        ]
        for future in futures:
            future.result(timeout=10)

    assert len(set(temporary_paths)) == 2
    assert all(path.parent == destination.parent for path in temporary_paths)
    assert ScanReport.model_validate_json(destination.read_text(encoding="utf-8"))
    assert set(tmp_path.iterdir()) == {destination}


def test_json_report_fsyncs_and_closes_before_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.json"
    events: list[tuple[str, int | None]] = []
    descriptor: int | None = None
    real_write = json_report.os.write
    real_fsync = json_report.os.fsync
    real_close = json_report.os.close
    real_replace = json_report.os.replace

    def observed_write(fd: int, data: bytes | bytearray | memoryview) -> int:
        nonlocal descriptor
        descriptor = fd
        events.append(("write", fd))
        return real_write(fd, data)

    def observed_fsync(fd: int) -> None:
        events.append(("fsync", fd))
        real_fsync(fd)

    def observed_close(fd: int) -> None:
        events.append(("close", fd))
        real_close(fd)

    def observed_replace(source: str | Path, target: str | Path) -> None:
        events.append(("replace", None))
        assert descriptor is not None
        with pytest.raises(OSError):
            json_report.os.fstat(descriptor)
        real_replace(source, target)

    monkeypatch.setattr(json_report.os, "write", observed_write)
    monkeypatch.setattr(json_report.os, "fsync", observed_fsync)
    monkeypatch.setattr(json_report.os, "close", observed_close)
    monkeypatch.setattr(json_report.os, "replace", observed_replace)

    write_json_report(_sample_report(), destination)

    names = [name for name, _ in events]
    assert names.index("write") < names.index("fsync") < names.index("close")
    assert names.index("close") < names.index("replace")


@pytest.mark.parametrize("operation", ["write", "fsync"])
def test_json_report_write_failures_preserve_destination_and_clean_temp(
    operation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "report.json"
    original = b"old report"
    destination.write_bytes(original)

    def fail_operation(*args: object) -> None:
        del args
        raise OSError(f"{operation} failed")

    monkeypatch.setattr(json_report.os, operation, fail_operation)

    with pytest.raises(OSError, match=rf"{operation} failed"):
        write_json_report(_sample_report(), destination)

    assert destination.read_bytes() == original
    assert set(tmp_path.iterdir()) == {destination}
