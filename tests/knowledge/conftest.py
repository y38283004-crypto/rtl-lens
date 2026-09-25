"""Shared real-adapter fixtures for packaged rule examples."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import Literal

from rtl_lens.engines.base import AnalysisEngine
from rtl_lens.knowledge.schema import ExplanationEntry
from rtl_lens.models.engine import EngineRequest, EngineRun
from rtl_lens.models.project import ResolvedProject


def run_example(
    entry: ExplanationEntry,
    variant: Literal["failing", "fixed"],
    root: Path,
    engine: AnalysisEngine,
) -> EngineRun:
    """Copy one packaged source into an isolated project and run the real adapter."""
    relative_path = entry.failing_example if variant == "failing" else entry.fixed_example
    source_resource = resources.files("rtl_lens.knowledge").joinpath("examples", relative_path)
    root.mkdir(parents=True)
    destination = root / Path(relative_path).name
    with resources.as_file(source_resource) as source_path:
        shutil.copyfile(source_path, destination)
    project = ResolvedProject(root=root, sources=(Path(destination.name),))
    return engine.run(EngineRequest(project=project, timeout_seconds=10))
