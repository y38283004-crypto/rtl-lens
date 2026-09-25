"""Validate the checked-in corpus without fetching sources or requiring a cache."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "compatibility_corpus_runner", ROOT / "scripts/scan_compatibility.py"
)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def test_corpus_has_ten_distinct_pinned_attributed_repository_scopes() -> None:
    manifest = RUNNER.load_manifest(ROOT / "compatibility.toml")

    assert len(manifest.projects) == 10
    assert len({project.repository for project in manifest.projects}) == 10
    assert {project.id for project in manifest.projects} == {
        "picorv32",
        "verilog-uart",
        "verilog-i2c",
        "verilog-axis",
        "verilog-axi",
        "verilog-ethernet",
        "aes",
        "sha256",
        "sha512",
        "chacha",
    }
    assert sum(len(project.files) for project in manifest.projects) == 28
    assert all(project.top_modules for project in manifest.projects)
    # Hashes, safe paths, attribution, scope and top-file membership are validated
    # by the real loader; network availability is not part of this corpus contract.
