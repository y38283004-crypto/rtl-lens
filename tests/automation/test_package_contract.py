from __future__ import annotations

import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
REQUIRED_RUNTIME_SUFFIXES = {
    "rtl_lens/py.typed",
    "rtl_lens/renderers/assets/report.html.j2",
    "rtl_lens/renderers/assets/report.css",
    "rtl_lens/renderers/assets/report.js",
    "rtl_lens/knowledge/rules/width-mismatch.yaml",
    "rtl_lens/knowledge/examples/failing/width-mismatch.sv",
    "rtl_lens/knowledge/examples/fixed/width-mismatch.sv",
}


def test_project_pins_the_supported_uv_build_line() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ignored_paths = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert project["build-system"] == {
        "requires": ["uv_build>=0.12.7,<0.13"],
        "build-backend": "uv_build",
    }
    assert project["tool"]["uv"]["required-version"] == "==0.12.7"
    assert (ROOT / "src" / "rtl_lens" / "py.typed").is_file()
    assert "dist/" in ignored_paths


def test_project_explicitly_packages_the_apache_license() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"].get("license-files") == ["LICENSE"]


def test_uv_build_contains_runtime_resources(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the package artifact contract")

    completed = subprocess.run(
        [uv, "build", "--no-sources", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

    wheels = list(tmp_path.glob("*.whl"))
    sdists = list(tmp_path.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1
    assert REQUIRED_RUNTIME_SUFFIXES <= _wheel_suffixes(wheels[0])
    assert REQUIRED_RUNTIME_SUFFIXES <= _sdist_suffixes(sdists[0])
    canonical_license = (ROOT / "LICENSE").read_bytes()
    with zipfile.ZipFile(wheels[0]) as archive:
        metadata_paths = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        assert len(metadata_paths) == 1
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
        assert metadata["License-Expression"] == "Apache-2.0"
        assert metadata.get_all("License-File") == ["LICENSE"]
        dist_info = metadata_paths[0].removesuffix("METADATA")
        assert archive.read(f"{dist_info}licenses/LICENSE") == canonical_license
    with tarfile.open(sdists[0], mode="r:gz") as archive:
        files = {member.name for member in archive.getmembers() if member.isfile()}
        roots = {name.split("/")[0] for name in files}
        assert len(roots) == 1
        prefix = roots.pop()
        assert {f"{prefix}/{name}" for name in ("LICENSE", "README.md", "pyproject.toml")} <= files
        license_file = archive.extractfile(f"{prefix}/LICENSE")
        assert license_file is not None
        assert license_file.read() == canonical_license


def _wheel_suffixes(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as archive:
        return {_runtime_suffix(member) for member in archive.namelist()}


def _sdist_suffixes(path: Path) -> set[str]:
    with tarfile.open(path, mode="r:gz") as archive:
        return {_runtime_suffix(member.name) for member in archive.getmembers() if member.isfile()}


def _runtime_suffix(member: str) -> str:
    normalized = member.replace("\\", "/")
    marker = "rtl_lens/"
    position = normalized.find(marker)
    return normalized[position:] if position >= 0 else normalized
