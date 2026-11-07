from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github/workflows/release-check.yml"


def _load() -> dict:
    assert WORKFLOW.is_file(), "build-only release-check workflow is missing"
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_release_checks_have_only_read_only_unprivileged_triggers() -> None:
    workflow = _load()
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["on"] == {
        "pull_request": "",
        "push": {"branches": ["main"]},
        "workflow_dispatch": "",
    }
    assert len(workflow["jobs"]) == 1
    job = next(iter(workflow["jobs"].values()))
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == "30"
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "pull_request_target",
        "workflow_run",
        "environment:",
        "secrets",
        "token",
        "registry",
        "deploy",
        "attest",
        "publish",
        "gh release",
        "docker push",
        "docker login",
        "git push",
        "git tag",
        ": write",
        "release:",
    ):
        assert forbidden not in text.lower()
    assert "permissions" not in job


def test_release_checks_pin_actions_and_limit_uploaded_files() -> None:
    workflow = _load()
    steps = next(iter(workflow["jobs"].values()))["steps"]
    actions = [step for step in steps if "uses" in step]
    assert [step["uses"].split("@")[0] for step in actions] == [
        "actions/checkout",
        "actions/setup-python",
        "astral-sh/setup-uv",
        "actions/upload-artifact",
    ]
    text = WORKFLOW.read_text(encoding="utf-8")
    for step in actions:
        assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", step["uses"])
        assert re.search(
            rf"uses: {re.escape(step['uses'])} # v\d+(?:\.\d+){{0,2}}$", text, re.MULTILINE
        )
    assert actions[0]["with"] == {"persist-credentials": "false"}
    assert actions[1]["with"] == {"python-version": "3.12"}
    assert actions[2]["with"] == {
        "version": "0.13.7",
        "enable-cache": "true",
        "cache-dependency-glob": "uv.lock",
    }
    assert actions[3]["with"] == {
        "name": "rtl-lens-release-check-${{ github.sha }}",
        "path": "dist/*.whl\ndist/*.tar.gz\ndist/SHA256SUMS\n",
        "if-no-files-found": "error",
        "retention-days": "7",
        "include-hidden-files": "false",
    }
    assert text.count("${{ github.sha }}") == 1
    assert all("${{" not in step["run"] for step in steps if "run" in step)


def test_release_checks_build_and_smoke_both_installed_artifacts() -> None:
    workflow = _load()
    steps = next(iter(workflow["jobs"].values()))["steps"]
    scripts = [step["run"] for step in steps if "run" in step]
    combined = "\n".join(scripts)
    required = [
        "uv lock --check",
        "uv sync --locked --all-groups",
        "tests/docs",
        "tests/automation/test_package_contract.py",
        "tests/automation/test_release_workflow.py",
        "python -m doctest README.md README.zh-CN.md docs/getting-started.md docs/configuration.md",
        "tools/generate_rule_docs.py --check",
        "uv build --no-sources",
        "uv venv .release-check/wheel",
        "uv venv .release-check/sdist",
        "uv pip install --python .release-check/wheel/bin/python dist/*.whl",
        "uv pip install --python .release-check/sdist/bin/python dist/*.tar.gz",
        "uv pip check --python .release-check/wheel/bin/python",
        "uv pip check --python .release-check/sdist/bin/python",
        'cd "$(mktemp -d)"',
        "for kind in wheel sdist",
        '"$root/.release-check/$kind/bin/rtl-lens" --help',
        '"$root/.release-check/$kind/bin/rtl-lens" version',
        '"$root/.release-check/$kind/bin/python" -I -c',
        "rtl_lens.__file__",
        "sys.prefix",
        "rtl_lens.knowledge",
        "width-mismatch.yaml",
        "read_text",
        "hashlib.sha256",
        "sorted(",
        "read_bytes()",
        "SHA256SUMS",
    ]
    for command in required:
        assert command in combined, f"missing release evidence: {command}"
    assert combined.index("uv lock --check") < combined.index("uv build --no-sources")
    assert combined.index("uv build --no-sources") < combined.index("uv pip install")
    assert combined.index("uv pip install") < combined.index('cd "$(mktemp -d)"')
    assert combined.index('cd "$(mktemp -d)"') < combined.index("hashlib.sha256")
    assert "actions/upload-artifact@" in steps[-1]["uses"]
