from __future__ import annotations

import re
from pathlib import Path

import pytest

from rtl_lens.config import load_config
from rtl_lens.models.project import EngineMode
from rtl_lens.project import resolve_project

ROOT = Path(__file__).parents[2]
DOCKERFILE = ROOT / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"
VERILATOR_VERSION = "5.040"
VERILATOR_TAG = "v5.040"
VERILATOR_COMMIT = "51cdf52d0f3a3e59b51fd87762646a851e9f4aff"
EXPECTED_NATIVE_VERSION = "Verilator 5.040 2025-08-30 rev v5.040"


def test_container_pins_verilator_and_has_no_latest_or_secret_arguments() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "ARG PYTHON_IMAGE=python:3.12.13-slim-bookworm" in dockerfile
    assert f"ARG VERILATOR_VERSION={VERILATOR_VERSION}" in dockerfile
    assert f"ARG VERILATOR_TAG={VERILATOR_TAG}" in dockerfile
    assert f"ARG VERILATOR_COMMIT={VERILATOR_COMMIT}" in dockerfile
    assert 'git checkout --detach "$VERILATOR_COMMIT"' in dockerfile
    assert 'test "$(git rev-parse HEAD)" = "$VERILATOR_COMMIT"' in dockerfile
    assert 'test "$(git describe --exact-match --tags HEAD)" = "$VERILATOR_TAG"' in dockerfile
    assert EXPECTED_NATIVE_VERSION in dockerfile
    assert 'io.rtl-lens.verilator.version="$VERILATOR_VERSION"' in dockerfile
    assert 'io.rtl-lens.verilator.commit="$VERILATOR_COMMIT"' in dockerfile
    assert "latest" not in dockerfile.casefold()
    assert not re.search(
        r"^ARG\s+.*(?:TOKEN|SECRET|PASSWORD)", dockerfile, re.IGNORECASE | re.MULTILINE
    )


def test_container_has_lean_release_and_explicit_test_targets() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    for stage in ("verilator-build", "package-build", "runtime", "test", "release"):
        assert re.search(rf"^FROM\s+\S+\s+AS\s+{stage}$", dockerfile, re.MULTILINE)
    assert 'python -m pip install --no-cache-dir "uv==$UV_VERSION"' in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "uv build --no-sources --out-dir /dist" in dockerfile
    assert (
        "uv pip install --python /opt/rtl-lens/.venv/bin/python --no-deps /dist/*.whl" in dockerfile
    )
    assert "--no-editable" not in dockerfile
    assert "./configure --prefix=/opt/verilator" in dockerfile
    assert "COPY --from=verilator-build /opt/verilator /opt/verilator" in dockerfile
    assert "COPY --from=verilator-build /usr/local /usr/local" not in dockerfile
    assert "COPY --from=package-build /opt/rtl-lens/.venv /opt/rtl-lens/.venv" in dockerfile
    assert 'ENV PATH="/opt/rtl-lens/.venv/bin:/opt/verilator/bin:$PATH"' in dockerfile
    runtime = dockerfile.split("FROM ${PYTHON_IMAGE} AS runtime", maxsplit=1)[1].split(
        "FROM runtime AS test", maxsplit=1
    )[0]
    assert "pip install" not in runtime
    assert "USER 10001:10001" in dockerfile
    assert 'ENTRYPOINT ["rtl-lens"]' in dockerfile
    assert 'CMD ["--help"]' in dockerfile
    assert dockerfile.rstrip().endswith("FROM runtime AS release")
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile


def test_docker_context_excludes_repository_and_generated_state() -> None:
    ignored = set(DOCKERIGNORE.read_text(encoding="utf-8").splitlines())

    assert {
        ".git",
        ".planning",
        ".superpowers",
        ".venv",
        ".worktrees",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "rtl-lens-reports",
    } <= ignored


@pytest.mark.parametrize("name", ["clean", "width-mismatch"])
def test_action_fixture_requires_verilator_and_is_isolated(name: str) -> None:
    fixture = ROOT / "tests" / "action" / "fixtures" / name
    config = load_config(fixture)
    project = resolve_project(fixture, config)

    assert config.scan.engine_mode is EngineMode.REQUIRED
    assert len(project.sources) == 1
    assert project.sources[0].suffix == ".sv"


def test_clean_and_width_mismatch_fixtures_are_separate_scan_roots() -> None:
    clean = ROOT / "tests" / "action" / "fixtures" / "clean" / "clean.sv"
    mismatch = ROOT / "tests" / "action" / "fixtures" / "width-mismatch" / "width_mismatch.sv"

    assert "module clean" in clean.read_text(encoding="utf-8")
    assert "assign narrow_value = wide_value;" in mismatch.read_text(encoding="utf-8")
    assert clean.parent != mismatch.parent
