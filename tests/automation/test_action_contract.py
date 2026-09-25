from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[2]
ACTION_PATH = ROOT / "action.yml"
ENTRYPOINT = ROOT / "scripts" / "action-entrypoint.sh"
UPLOAD_ARTIFACT = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"


def test_action_metadata_has_stable_inputs_outputs_and_composite_runtime() -> None:
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    defaults = {
        "project-path": ".",
        "config-path": "",
        "fail-on": "error",
        "report-format": "both",
        "upload-report": "false",
        "artifact-name": "rtl-lens-report",
    }

    assert {
        name: definition["default"] for name, definition in action["inputs"].items()
    } == defaults
    assert set(action["outputs"]) == {"report-paths", "scan-exit-code"}
    assert action["outputs"]["report-paths"]["value"] == "${{ steps.scan.outputs.report-paths }}"
    assert action["outputs"]["scan-exit-code"]["value"] == (
        "${{ steps.scan.outputs.scan-exit-code }}"
    )
    assert action["runs"]["using"] == "composite"


def test_action_upload_is_exact_opt_in_and_uses_a_full_commit_pin() -> None:
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]
    upload = next(step for step in steps if step.get("uses") == UPLOAD_ARTIFACT)
    propagate = steps[-1]

    assert "always()" in upload["if"]
    assert "inputs.upload-report == 'true'" in upload["if"]
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["path"] == "${{ steps.scan.outputs.report-paths }}"
    assert re.fullmatch(r"actions/upload-artifact@[0-9a-f]{40}", upload["uses"])
    assert "always()" in propagate["if"]
    assert propagate["env"]["RTL_LENS_SCAN_EXIT_CODE"] == (
        "${{ steps.scan.outputs.scan-exit-code }}"
    )
    assert propagate["run"] == 'exit "${RTL_LENS_SCAN_EXIT_CODE:-2}"'


def test_action_run_programs_do_not_interpolate_inputs_or_forward_credentials() -> None:
    action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]
    scan = next(step for step in steps if step.get("id") == "scan")

    assert scan["run"] == '"$GITHUB_ACTION_PATH/scripts/action-entrypoint.sh"'
    assert scan["shell"] == "bash"
    assert set(scan["env"]) == {
        "RTL_LENS_INPUT_PROJECT_PATH",
        "RTL_LENS_INPUT_CONFIG_PATH",
        "RTL_LENS_INPUT_FAIL_ON",
        "RTL_LENS_INPUT_REPORT_FORMAT",
        "RTL_LENS_INPUT_UPLOAD_REPORT",
    }
    for step in steps:
        assert "${{ inputs." not in step.get("run", "")
        environment = step.get("env", {})
        serialized = "\n".join(f"{key}={value}" for key, value in environment.items())
        assert not re.search(r"(?:TOKEN|SECRET|PASSWORD|github\.token)", serialized, re.IGNORECASE)


@pytest.mark.parametrize("value", ["json", "html", "both"])
def test_entrypoint_accepts_only_documented_report_formats(value: str) -> None:
    script = ENTRYPOINT.read_text(encoding="utf-8")

    assert re.search(rf"json\|html\|both\).*{value}", script, re.DOTALL)


def test_entrypoint_is_shell_safe_offline_and_preserves_cli_outputs() -> None:
    script = ENTRYPOINT.read_text(encoding="utf-8")

    assert "docker_args=(" in script
    assert "scan_args=(" in script
    assert 'docker "${docker_args[@]}" "$image_name" "${scan_args[@]}"' in script
    for option in (
        "--network=none",
        "--user",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
    ):
        assert option in script
    assert 'realpath -e -- "$GITHUB_WORKSPACE"' in script
    assert 'realpath -e -- "$GITHUB_ACTION_PATH"' in script
    assert '--volume "$workspace:/workspace:ro"' in script
    assert '--volume "$report_dir:/workspace/rtl-lens-reports:rw"' in script
    assert "/workspace/.git" in script
    assert "/dev/null" in script
    assert 'docker build --target release --tag "$image_name" "$action_path"' in script
    assert "report-paths<<RTL_LENS_REPORT_PATHS" in script
    assert "scan-exit-code=%s" in script
    assert "RTL_LENS_INPUT_FAIL_ON" in script and "error|warning|info" in script
    assert "RTL_LENS_INPUT_UPLOAD_REPORT" in script and "true|false" in script
    assert "${{" not in script
    assert not re.search(r"\beval\b|\bbash\s+-c\b|\bsh\s+-c\b", script)


def test_entrypoint_has_valid_bash_syntax_when_bash_is_available() -> None:
    bash = _find_working_bash()
    if bash is None:
        pytest.skip("bash is required for the Action syntax contract")

    completed = subprocess.run(
        [bash, "-n", ENTRYPOINT.as_posix()],
        capture_output=True,
        check=False,
    )
    output = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
    assert completed.returncode == 0, output


@pytest.mark.parametrize(
    ("scan_exit", "report_format", "expected_reports"),
    [
        (0, "json", {"report.json"}),
        (1, "html", {"report.html"}),
        (0, "both", {"report.json", "report.html"}),
        (2, "both", set()),
    ],
)
def test_entrypoint_functionally_preserves_exit_and_report_format(
    tmp_path: Path,
    scan_exit: int,
    report_format: str,
    expected_reports: set[str],
) -> None:
    result = _run_entrypoint(
        tmp_path,
        scan_exit=scan_exit,
        report_format=report_format,
        create_reports=scan_exit <= 1,
    )

    assert result["returncode"] == 0, result["stderr"]
    assert _output_value(result["outputs"], "scan-exit-code") == str(scan_exit), result
    assert {path.name for path in result["report_dir"].glob("report.*")} == expected_reports
    assert {Path(path).name for path in _output_paths(result["outputs"])} == expected_reports
    assert "ARG=--network=none" in result["docker_log"]
    assert "ARG=--read-only" in result["docker_log"]
    assert ":/workspace:ro" in result["docker_log"]
    assert ":/workspace/rtl-lens-reports:rw" in result["docker_log"]
    assert "ARG=/workspace/.git:rw,noexec,nosuid,nodev,size=64k,mode=700" in result["docker_log"]
    assert "credential-canary" not in result["docker_log"]
    assert "credential-canary" not in result["outputs"]


@pytest.mark.parametrize(
    ("fail_on", "report_format", "upload_report"),
    [
        ("critical", "both", "false"),
        ("error", "xml", "false"),
        ("error", "both", "TRUE"),
    ],
)
def test_entrypoint_functionally_rejects_invalid_inputs_before_docker(
    tmp_path: Path,
    fail_on: str,
    report_format: str,
    upload_report: str,
) -> None:
    result = _run_entrypoint(
        tmp_path,
        fail_on=fail_on,
        report_format=report_format,
        upload_report=upload_report,
    )

    assert result["returncode"] == 0
    assert _output_value(result["outputs"], "scan-exit-code") == "3"
    assert result["docker_log"] == ""


def test_entrypoint_functionally_rejects_project_path_escape(tmp_path: Path) -> None:
    (tmp_path / "outside").mkdir()

    result = _run_entrypoint(tmp_path, project_input="../outside")

    assert _output_value(result["outputs"], "scan-exit-code") == "3"
    assert result["docker_log"] == ""


def test_entrypoint_functionally_rejects_symlinked_report_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside-reports"
    outside.mkdir()
    try:
        result = _run_entrypoint(tmp_path, report_symlink_target=outside)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable on this platform/account: {error}")

    assert _output_value(result["outputs"], "scan-exit-code") == "3"
    assert result["docker_log"] == ""


def test_entrypoint_masks_file_form_git_metadata(tmp_path: Path) -> None:
    result = _run_entrypoint(tmp_path, git_metadata_kind="file", scan_exit=0, create_reports=True)

    assert _output_value(result["outputs"], "scan-exit-code") == "0"
    assert "ARG=type=bind,source=/dev/null,target=/workspace/.git,readonly" in result["docker_log"]
    assert "credential-canary" not in result["docker_log"]


def _run_entrypoint(
    tmp_path: Path,
    *,
    scan_exit: int = 0,
    report_format: str = "both",
    fail_on: str = "error",
    upload_report: str = "false",
    project_input: str = "project",
    create_reports: bool = False,
    report_symlink_target: Path | None = None,
    git_metadata_kind: str = "directory",
) -> dict[str, object]:
    bash = _find_working_bash()
    if bash is None:
        pytest.skip("bash is required for the Action functional contract")

    workspace = tmp_path / "workspace"
    project = workspace / "project"
    project.mkdir(parents=True)
    (project / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
    git_metadata = workspace / ".git"
    if git_metadata_kind == "directory":
        git_metadata.mkdir()
        (git_metadata / "config").write_text("credential-canary\n", encoding="utf-8")
    else:
        git_metadata.write_text("gitdir: credential-canary\n", encoding="utf-8")

    report_dir = workspace / "rtl-lens-reports"
    if report_symlink_target is not None:
        report_dir.symlink_to(report_symlink_target, target_is_directory=True)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    _write_executable(fake_bin / "uname", "#!/usr/bin/env bash\nprintf 'Linux\\n'\n")
    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -u
{
  printf 'CALL\\n'
  for argument in "$@"; do
    printf 'ARG=%s\\n' "$argument"
  done
} >>"$FAKE_DOCKER_LOG"
case "${1:-}" in
  build)
    exit "${FAKE_DOCKER_BUILD_EXIT:-0}"
    ;;
  run)
    if [[ ${FAKE_CREATE_REPORTS:-false} == true ]]; then
      mkdir -p -- "$FAKE_REPORT_DIR"
      printf '{"status":"fake"}\\n' >"$FAKE_REPORT_DIR/report.json"
      printf '<!doctype html><title>fake</title>\\n' >"$FAKE_REPORT_DIR/report.html"
    fi
    exit "${FAKE_SCAN_EXIT:-0}"
    ;;
esac
exit 2
""",
    )

    output_path = tmp_path / "github-output"
    docker_log = tmp_path / "docker.log"
    environment = os.environ.copy()
    environment.update(
        {
            "GITHUB_WORKSPACE": _bash_path(bash, workspace),
            "GITHUB_ACTION_PATH": _bash_path(bash, ROOT),
            "GITHUB_OUTPUT": _bash_path(bash, output_path),
            "RTL_LENS_INPUT_PROJECT_PATH": project_input,
            "RTL_LENS_INPUT_CONFIG_PATH": "",
            "RTL_LENS_INPUT_FAIL_ON": fail_on,
            "RTL_LENS_INPUT_REPORT_FORMAT": report_format,
            "RTL_LENS_INPUT_UPLOAD_REPORT": upload_report,
            "FAKE_DOCKER_LOG": _bash_path(bash, docker_log),
            "FAKE_REPORT_DIR": _bash_path(bash, report_dir),
            "FAKE_SCAN_EXIT": str(scan_exit),
            "FAKE_CREATE_REPORTS": str(create_reports).lower(),
        }
    )
    completed = subprocess.run(
        [
            bash,
            "-c",
            'export PATH="$1:/usr/bin:/bin"; exec bash "$2"',
            "--",
            _bash_path(bash, fake_bin),
            ENTRYPOINT.as_posix(),
        ],
        cwd=workspace,
        env=environment,
        capture_output=True,
        check=False,
    )

    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", errors="replace"),
        "stderr": completed.stderr.decode("utf-8", errors="replace"),
        "outputs": output_path.read_text(encoding="utf-8") if output_path.is_file() else "",
        "docker_log": docker_log.read_text(encoding="utf-8") if docker_log.is_file() else "",
        "report_dir": report_dir,
    }


def _write_executable(path: Path, content: str) -> None:
    path.write_bytes(content.encode("utf-8"))
    path.chmod(0o755)


def _bash_path(bash: str, path: Path) -> str:
    if os.name != "nt":
        return str(path)
    completed = subprocess.run(
        [bash, "-lc", 'cygpath -u "$1"', "--", str(path)],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _output_value(outputs: object, name: str) -> str:
    assert isinstance(outputs, str)
    prefix = f"{name}="
    return next(
        line.removeprefix(prefix) for line in outputs.splitlines() if line.startswith(prefix)
    )


def _output_paths(outputs: object) -> tuple[str, ...]:
    assert isinstance(outputs, str)
    lines = outputs.splitlines()
    start = lines.index("report-paths<<RTL_LENS_REPORT_PATHS") + 1
    end = lines.index("RTL_LENS_REPORT_PATHS", start)
    return tuple(lines[start:end])


def _find_working_bash() -> str | None:
    candidates = (
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    )
    for candidate in candidates:
        if candidate is None or not Path(candidate).is_file():
            continue
        probe = subprocess.run([candidate, "--version"], capture_output=True, check=False)
        if probe.returncode == 0:
            return candidate
    return None
