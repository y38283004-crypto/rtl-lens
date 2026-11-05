from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
ACTION_SMOKE_PATH = ROOT / ".github" / "workflows" / "action-smoke.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
ALLOWED_ACTIONS = {
    "actions/checkout",
    "actions/setup-python",
    "astral-sh/setup-uv",
    "actions/upload-artifact",
}


def test_coverage_outputs_do_not_dirty_the_worktree() -> None:
    ignored = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())

    assert {".coverage", "coverage.xml", "htmlcov/"} <= ignored


def test_ci_has_read_only_permissions_and_complete_native_matrix() -> None:
    ci = _load(CI_PATH)
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]

    assert ci["permissions"] == {"contents": "read"}
    assert set(matrix["os"]) == {"ubuntu-latest", "windows-latest", "macos-latest"}
    assert set(matrix["python-version"]) == {"3.11", "3.12", "3.13"}
    assert {"test", "quality", "browser", "package", "container"} <= set(ci["jobs"])
    for job in ci["jobs"].values():
        assert 1 <= int(job["timeout-minutes"]) <= 60
        assert "permissions" not in job


def test_workflows_pin_every_external_action_with_same_line_release_comments() -> None:
    pins: dict[str, str] = {}
    for path in (CI_PATH, ACTION_SMOKE_PATH, ROOT / ".github/workflows/release-check.yml"):
        workflow = _load(path)
        raw = path.read_text(encoding="utf-8")
        assert workflow["permissions"] == {"contents": "read"}
        assert "pull_request_target" not in workflow["on"]
        assert not re.search(r"@(?:main|master|latest)(?:\s|$)", raw)
        assert not re.search(r"(?:TOKEN|SECRET|PASSWORD|github\.token)", raw, re.IGNORECASE)
        assert not re.search(r"^\s+\w+:\s*write\s*$", raw, re.MULTILINE)
        for job in workflow["jobs"].values():
            assert 1 <= int(job["timeout-minutes"]) <= 60
            for step in job["steps"]:
                uses = step.get("uses")
                if uses is None or uses == "./":
                    continue
                assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", uses)
                action, commit = uses.split("@", maxsplit=1)
                assert action in ALLOWED_ACTIONS
                assert pins.setdefault(action, commit) == commit
                pattern = rf"uses:\s*{re.escape(uses)}\s+#\s+v\d+(?:\.\d+){{0,2}}\s*$"
                assert re.search(pattern, raw, re.MULTILINE)
                if action == "actions/checkout":
                    assert step["with"]["persist-credentials"] == "false"

    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        if "uses" in step:
            name, commit = step["uses"].split("@", maxsplit=1)
            assert pins[name] == commit


def test_ci_jobs_enforce_lock_quality_browser_package_and_container_contracts() -> None:
    ci = _load(CI_PATH)
    raw = CI_PATH.read_text(encoding="utf-8")

    assert "uv sync --locked --all-groups" in raw
    assert "pytest --ignore=tests/browser" in _runs(ci["jobs"]["test"])
    quality = _runs(ci["jobs"]["quality"])
    assert "ruff check --no-cache src tests tools" in quality
    assert "ruff format --check src tests tools" in quality
    assert "mypy src" in quality
    assert "--cov-fail-under=90" in quality
    browser = _runs(ci["jobs"]["browser"])
    assert "playwright install --with-deps chromium" in browser
    assert "pytest tests/browser" in browser
    package = _runs(ci["jobs"]["package"])
    assert "uv lock --check" in package
    assert "pytest tests/automation/test_package_contract.py" in package
    assert "uv build --no-sources" in package
    upload = next(
        step
        for step in ci["jobs"]["package"]["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload["with"]["path"] == "dist/*.whl\ndist/*.tar.gz\n"
    assert upload["with"]["if-no-files-found"] == "error"
    container = _runs(ci["jobs"]["container"])
    assert "docker build --target test" in container
    assert "test_verilator_mapping_is_emitted_only_by_the_failing_example" in container
    assert "Verilator 5.040 2025-08-30 rev v5.040" in container
    assert "io.rtl-lens.verilator.version" in container
    assert "io.rtl-lens.verilator.commit" in container
    assert "10001:10001" in container
    assert "rtl-lens:ci --help" in container
    assert "from importlib import resources" in container
    assert "resources.files('rtl_lens.knowledge')" in container
    assert "width-mismatch.yaml" in container


def test_local_action_smoke_covers_success_policy_and_usage_exit_codes() -> None:
    smoke = _load(ACTION_SMOKE_PATH)
    assert smoke["permissions"] == {"contents": "read"}
    assert set(smoke["jobs"]) == {"smoke"}
    job = smoke["jobs"]["smoke"]
    local_steps = {step["id"]: step for step in job["steps"] if step.get("uses") == "./"}
    runs = _runs(job)

    assert set(local_steps) == {"scan", "width", "invalid"}
    clean = local_steps["scan"]
    assert clean["with"]["project-path"] == "tests/action/fixtures/clean"
    assert clean["with"]["upload-report"] == "false"
    assert clean["with"]["report-format"] == "both"
    width = local_steps["width"]
    assert width["continue-on-error"] == "true"
    assert width["with"] == {
        "project-path": "tests/action/fixtures/width-mismatch",
        "fail-on": "warning",
        "report-format": "json",
        "upload-report": "false",
    }
    invalid = local_steps["invalid"]
    assert invalid["continue-on-error"] == "true"
    assert invalid["with"]["fail-on"] == "critical"
    assert invalid["with"]["upload-report"] == "false"
    assert "test -f rtl-lens-reports/report.json" in runs
    assert "test -f rtl-lens-reports/report.html" in runs
    assert 'test "$RTL_LENS_SCAN_EXIT_CODE" = "0"' in runs
    assert 'test "$RTL_LENS_SCAN_EXIT_CODE" = "1"' in runs
    assert 'test "$RTL_LENS_SCAN_EXIT_CODE" = "3"' in runs
    raw = ACTION_SMOKE_PATH.read_text(encoding="utf-8")
    assert "steps.scan.outputs.scan-exit-code" in raw
    assert "steps.width.outputs.scan-exit-code" in raw
    assert "steps.invalid.outputs.scan-exit-code" in raw
    assert "steps.width.outcome" in raw
    assert "steps.invalid.outcome" in raw


def test_dependabot_updates_uv_docker_and_actions_weekly_from_root() -> None:
    dependabot = _load(DEPENDABOT_PATH)
    updates = dependabot["updates"]

    assert dependabot["version"] == "2"
    assert {update["package-ecosystem"] for update in updates} == {
        "uv",
        "docker",
        "github-actions",
    }
    assert all(update["directory"] == "/" for update in updates)
    assert all(update["schedule"]["interval"] == "weekly" for update in updates)


def _load(path: Path) -> dict[str, object]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def _runs(job: dict[str, object]) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])
