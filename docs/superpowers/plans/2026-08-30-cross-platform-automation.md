# Cross-Platform Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver locally verified package artifacts, a reproducible Verilator 5.040 container, a secure opt-in-upload composite Action, and read-only cross-platform CI definitions.

**Architecture:** A universal uv lock and uv-built wheel/sdist form the package boundary. A multi-stage Linux image compiles the exact Verilator commit and installs the wheel into a small runtime image; a separate test target runs real Verilator mapping evidence. A composite Action calls a shell-safe host wrapper that builds/runs the image with `--network=none`, while workflows independently cover the nine native PySlang matrix combinations, browser output, packaging, the container, and the local Action.

**Tech Stack:** Python 3.11–3.13, uv 0.12.7, uv_build 0.12.x, pytest, PyYAML, Bash, Docker, GitHub Actions, Dependabot, Verilator 5.040.

**Spec:** `docs/superpowers/specs/2026-08-17-rtl-lens-design.md`

## Global Constraints

- Product/distribution/import/command names remain `RTL Lens` / `rtl-lens` / `rtl_lens` / `rtl-lens`.
- Supported Python remains `>=3.11,<3.14`; the native matrix is Ubuntu, Windows, and macOS across 3.11, 3.12, and 3.13.
- Local Verilator compatibility remains `>=5.040`; the reproducible container pins exactly tag `v5.040`, commit `51cdf52d0f3a3e59b51fd87762646a851e9f4aff`.
- Every workflow has only `contents: read`; no repository token or ambient secret is passed into the analyzer container.
- `upload-report` defaults to the string `"false"`; upload occurs only for exact string `"true"`.
- Action inputs enter shell commands only through quoted environment variables and Bash arrays; never interpolate `${{ inputs.* }}` into a `run` program.
- The container is offline at scan time (`--network=none`) and uses no `latest` image tag or floating Verilator ref.
- Preserve CLI exit codes 0/1/2/3 and the real `scan --json PATH --html PATH` interface; do not invent `scan --format`.
- Do not push, dispatch workflows, upload images/packages, publish, or list the Action without separate user approval.
- Host absence of Docker or additional Python interpreters is recorded as unverified, never converted into a pass.

---

### Task 0: Normalize the existing Python formatting baseline

**Files:**
- Modify mechanically: `src/rtl_lens/engines/base.py`
- Modify mechanically: `src/rtl_lens/project.py`
- Modify mechanically: `tests/contract/test_engine_contract.py`
- Modify mechanically: `tests/fixtures/bin/fake_verilator.py`
- Modify mechanically: `tests/unit/test_sarif.py`
- Modify mechanically: `tests/unit/test_verilator_engine.py`

**Interfaces:**
- Consumes: the already classified six-file Ruff formatting debt from Task 13.
- Produces: a clean `ruff format --check src tests tools` baseline without changing runtime behavior; historical Markdown plan files remain outside this Python-only CI gate.

- [ ] **Step 1: Reconfirm the exact formatter delta**

Run `ruff format --check src tests tools` and require that only the six files listed above fail. If the set differs, stop and re-audit before formatting.

- [ ] **Step 2: Apply only the deterministic formatter rewrite**

Run `ruff format` against the six explicit paths, inspect the diff, and reject semantic or unrelated changes.

- [ ] **Step 3: Verify behavior and commit the baseline**

Run the full suite plus `ruff check --no-cache src tests`, `ruff format --check src tests tools`, and mypy. Commit only the six mechanical files:

```powershell
git add src/rtl_lens/engines/base.py src/rtl_lens/project.py tests/contract/test_engine_contract.py tests/fixtures/bin/fake_verilator.py tests/unit/test_sarif.py tests/unit/test_verilator_engine.py
git commit -m "style: normalize Python formatting baseline"
```

---

### Task 1: Lock and verify the distributable package

**Files:**
- Create: `src/rtl_lens/py.typed`
- Create: `tests/automation/__init__.py`
- Create: `tests/automation/test_package_contract.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: existing PEP 621 project metadata and packaged Jinja/YAML/SystemVerilog resources.
- Produces: uv `0.12.7` required-version contract, `uv_build>=0.12.7,<0.13`, a refreshed universal `uv.lock`, and wheel/sdist files whose resource contents are asserted.

- [ ] **Step 1: Write the failing package-contract tests**

Create `tests/automation/test_package_contract.py` with a TOML assertion that requires:

```python
def test_project_pins_the_supported_uv_build_line() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["build-system"] == {
        "requires": ["uv_build>=0.12.7,<0.13"],
        "build-backend": "uv_build",
    }
    assert project["tool"]["uv"]["required-version"] == "==0.12.7"
    assert Path("src/rtl_lens/py.typed").is_file()
```

Add a uv-gated real build test. It must call `uv build --no-sources --out-dir <tmp>` and assert one wheel plus one sdist. Inspect both archives and require at least:

```python
required_runtime_suffixes = {
    "rtl_lens/py.typed",
    "rtl_lens/renderers/assets/report.html.j2",
    "rtl_lens/renderers/assets/report.css",
    "rtl_lens/renderers/assets/report.js",
    "rtl_lens/knowledge/rules/width-mismatch.yaml",
    "rtl_lens/knowledge/examples/failing/width-mismatch.sv",
    "rtl_lens/knowledge/examples/fixed/width-mismatch.sv",
}
```

The only allowed skip is `pytest.skip("uv is required for the package artifact contract")` when `shutil.which("uv")` is absent; CI must provision uv before this test.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/automation/test_package_contract.py -q -p no:cacheprovider
```

Expected RED: the existing backend upper bound is `<0.12`, `[tool.uv].required-version` is absent, and `py.typed` is absent. The build test may be the single documented uv-host skip before provisioning.

- [ ] **Step 3: Implement the package metadata contract**

Change `pyproject.toml` to:

```toml
[build-system]
requires = ["uv_build>=0.12.7,<0.13"]
build-backend = "uv_build"

[tool.uv]
required-version = "==0.12.7"
```

Add the PEP 561 marker. Install uv 0.12.7 into the project venv from its official PyPI distribution, run `uv lock`, then run `uv lock --check` and confirm only the expected backend/lock metadata changed.

- [ ] **Step 4: Verify artifacts and existing package behavior**

Run:

```powershell
uv lock --check
uv build --no-sources
.\.venv\Scripts\python.exe -m pytest tests/automation/test_package_contract.py tests/unit/test_knowledge.py tests/browser/test_html_report.py -q -p no:cacheprovider
```

Set `RTL_LENS_TEST_CHROMIUM` to the system Chrome path for the browser file. Expected: two artifacts under `dist/`, package contract PASS without skip, resources load, browser tests pass.

- [ ] **Step 5: Commit the package boundary**

```powershell
git add pyproject.toml uv.lock src/rtl_lens/py.typed tests/automation
git commit -m "build: lock distributable package artifacts"
```

---

### Task 2: Specify and implement the pinned Verilator container

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `tests/action/fixtures/clean/.rtl-lens.toml`
- Create: `tests/action/fixtures/clean/clean.sv`
- Create: `tests/action/fixtures/width-mismatch/.rtl-lens.toml`
- Create: `tests/action/fixtures/width-mismatch/width_mismatch.sv`
- Create: `tests/automation/test_container_contract.py`

**Interfaces:**
- Consumes: Task 1 wheel build, `rtl-lens scan`, existing real-adapter rule tests, and public CLI exit codes.
- Produces: Docker stages `verilator-build`, `package-build`, `runtime`, `test`, and final `release`; default image entrypoint `rtl-lens`; exact label `io.rtl-lens.verilator.version=5.040`.

- [ ] **Step 1: Write failing static and fixture contracts**

Create tests that require:

```python
VERILATOR_VERSION = "5.040"
VERILATOR_TAG = "v5.040"
VERILATOR_COMMIT = "51cdf52d0f3a3e59b51fd87762646a851e9f4aff"

def test_container_pins_verilator_and_has_no_latest_or_secret_arguments() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert f"ARG VERILATOR_VERSION={VERILATOR_VERSION}" in dockerfile
    assert f"ARG VERILATOR_TAG={VERILATOR_TAG}" in dockerfile
    assert f"ARG VERILATOR_COMMIT={VERILATOR_COMMIT}" in dockerfile
    assert "git checkout --detach \"$VERILATOR_COMMIT\"" in dockerfile
    assert 'io.rtl-lens.verilator.version="$VERILATOR_VERSION"' in dockerfile
    assert "latest" not in dockerfile.casefold()
    assert not re.search(r"ARG\s+.*(?:TOKEN|SECRET|PASSWORD)", dockerfile, re.IGNORECASE)
```

Also assert named multi-stage targets, exec-form entrypoint, non-root final user, apt list cleanup, `.git`/venv/cache/dist/planning exclusions, and two isolated required-engine fixtures: one clean module and one deterministic width mismatch. Keeping them in separate scan roots prevents the clean Action smoke test from accidentally scanning the failing module.

- [ ] **Step 2: Run the container tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/automation/test_container_contract.py -q -p no:cacheprovider
```

Expected RED: Dockerfile, ignore file, and fixture do not exist.

- [ ] **Step 3: Implement the multi-stage image**

Use the explicit base `python:3.12.13-slim-bookworm`. The build stage installs only the official v5.040 build prerequisites, clones the official repository, checks out the exact commit, verifies `git describe --exact-match --tags` equals `v5.040`, builds, installs, and verifies the full native version line.

The package stage installs uv 0.12.7 and runs `uv build --no-sources`. The runtime stage installs only runtime libraries, copies `/usr/local` from the Verilator build and the wheel from the package stage, installs the wheel, creates a non-root `rtl-lens` user, sets OCI source/version plus exact Verilator labels, and uses:

```dockerfile
ENTRYPOINT ["rtl-lens"]
CMD ["--help"]
```

The `test` target derives from runtime, installs only pytest, copies `tests/`, `src/`, and the project metadata needed for test collection, then runs the 27 real Verilator mapping cases. The last `release` stage derives from runtime so the default build excludes test tools.

- [ ] **Step 4: Verify static contracts and classify the runtime gate**

Run the static tests. If Docker is available, additionally run:

```bash
docker build --target test --build-arg VERILATOR_VERSION=5.040 --build-arg VERILATOR_TAG=v5.040 --build-arg VERILATOR_COMMIT=51cdf52d0f3a3e59b51fd87762646a851e9f4aff -t rtl-lens:test .
docker run --rm --network=none --entrypoint python rtl-lens:test -m pytest tests/knowledge/test_rule_examples.py -q -p no:cacheprovider
docker build --target release -t rtl-lens:ci .
docker run --rm --network=none --entrypoint verilator rtl-lens:ci --version
docker inspect --format '{{ index .Config.Labels "io.rtl-lens.verilator.version" }}' rtl-lens:ci
```

Expected native version: `Verilator 5.040 2025-08-30 rev v5.040`; expected label: `5.040`. If Docker is absent, record these exact commands as not-run and keep the container runtime gate open.

- [ ] **Step 5: Commit the container contract**

```powershell
git add Dockerfile .dockerignore tests/action tests/automation/test_container_contract.py
git commit -m "build: pin the Verilator analysis container"
```

---

### Task 3: Build the shell-safe composite Action

**Files:**
- Create: `action.yml`
- Create: `scripts/action-entrypoint.sh`
- Create: `tests/automation/test_action_contract.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 2 default release image, `rtl-lens scan PATH --config PATH --fail-on LEVEL --json PATH --html PATH`.
- Produces: inputs `project-path`, `config-path`, `fail-on`, `report-format`, `upload-report`, `artifact-name`; outputs `report-paths`, `scan-exit-code`; retained reports under `rtl-lens-reports/`.

- [ ] **Step 1: Write failing Action metadata and shell-safety tests**

Require exact defaults:

```python
assert action["inputs"]["project-path"]["default"] == "."
assert action["inputs"]["config-path"]["default"] == ""
assert action["inputs"]["fail-on"]["default"] == "error"
assert action["inputs"]["report-format"]["default"] == "both"
assert action["inputs"]["upload-report"]["default"] == "false"
assert action["inputs"]["artifact-name"]["default"] == "rtl-lens-report"
assert action["runs"]["using"] == "composite"
```

Assert the upload step uses `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7`, has `if-no-files-found: error`, and is conditioned on exact `inputs.upload-report == 'true'` plus `always()`. Assert no `${{ inputs.` token appears in any `run` string, no token/secret environment is forwarded, and the shell script contains Bash arrays, `--network=none`, `--user`, quoted path validation, and no `eval`/`bash -c`/`sh -c`.

Add parameterized static cases for report formats `json`, `html`, `both` and invalid input rejection. If Bash is present, require `bash -n scripts/action-entrypoint.sh` to pass.

- [ ] **Step 2: Run the Action contracts and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/automation/test_action_contract.py -q -p no:cacheprovider
```

Expected RED: metadata and entrypoint are absent.

- [ ] **Step 3: Implement the composite Action and host wrapper**

The composite scan step maps each `${{ inputs.* }}` into step `env`, then invokes only:

```yaml
run: '"$GITHUB_ACTION_PATH/scripts/action-entrypoint.sh"'
shell: bash
```

The wrapper must:

1. require Linux, Docker, `GITHUB_WORKSPACE`, `GITHUB_ACTION_PATH`, and `GITHUB_OUTPUT`;
2. accept only fail levels `error|warning|info`, formats `json|html|both`, and upload strings `true|false`;
3. canonicalize project/config paths and require them beneath the workspace;
4. build the local release target without passing credentials;
5. create `rtl-lens-reports/`, mount only the workspace, run as the host uid/gid with `HOME=/tmp/rtl-lens-home`, and disable container networking;
6. construct the CLI invocation as an array and capture its exact exit code;
7. remove the unselected report for `json` or `html`, then write multiline `report-paths` and numeric `scan-exit-code` outputs.

The upload step consumes the explicit report paths only when opted in. A final `always()` shell step exits with the recorded scan code, so upload cannot turn CLI 1/2/3 into success. Add `rtl-lens-reports/` to `.gitignore`.

- [ ] **Step 4: Verify Action contracts and non-Docker syntax gates**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/automation/test_action_contract.py tests/e2e/test_cli_exit_codes.py -q -p no:cacheprovider
bash -n scripts/action-entrypoint.sh
```

If Docker is available, invoke the wrapper against the clean fixture with upload false and verify JSON/HTML outputs; invoke the width fixture with fail-on warning and verify exit 1 plus retained reports.

- [ ] **Step 5: Commit the reusable Action**

```powershell
git add action.yml scripts/action-entrypoint.sh .gitignore tests/automation/test_action_contract.py
git commit -m "ci: add the offline RTL Lens action"
```

---

### Task 4: Wire read-only workflows and dependency maintenance

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/action-smoke.yml`
- Create: `.github/dependabot.yml`
- Create: `tests/automation/test_ci_contract.py`

**Interfaces:**
- Consumes: Tasks 1–3 package, container, Action, fixture, and exact upstream Action pins.
- Produces: nine native matrix jobs, Ubuntu quality/browser/package/container jobs, local Action smoke, and weekly uv/Docker/Action update proposals.

- [ ] **Step 1: Write failing workflow and Dependabot contracts**

Load YAML with `yaml.BaseLoader` so the workflow `on` key remains a string. Assert:

```python
assert ci["permissions"] == {"contents": "read"}
assert set(ci["jobs"]["test"]["strategy"]["matrix"]["os"]) == {
    "ubuntu-latest", "windows-latest", "macos-latest"
}
assert set(ci["jobs"]["test"]["strategy"]["matrix"]["python-version"]) == {
    "3.11", "3.12", "3.13"
}
assert set(update["package-ecosystem"] for update in dependabot["updates"]) == {
    "uv", "docker", "github-actions"
}
```

Require full 40-character pins plus same-line release comments for checkout v7, setup-python v7, setup-uv v10.0.1, and upload-artifact v7. Reject `@main`, `@master`, `@latest`, `pull_request_target`, write permissions, token forwarding, unbounded workflow timeouts, and ignored lock changes.

Require jobs for `quality`, `browser`, `package`, and `container`; container must run the 27 Verilator examples and assert version/label. Require action smoke to use `uses: ./`, keep upload false, and verify both local output files.

- [ ] **Step 2: Run workflow tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/automation/test_ci_contract.py -q -p no:cacheprovider
```

Expected RED: `.github` automation files do not exist.

- [ ] **Step 3: Implement the workflows and Dependabot configuration**

Use these immutable Action pins on the same line as their tag comments:

```yaml
uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7
uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
```

Every job gets an explicit timeout and inherits top-level `permissions: {contents: read}`. The matrix provisions the selected Python plus uv 0.12.7, performs `uv sync --locked --all-groups`, and runs all non-browser tests. Quality runs Ruff, format, mypy, and the 90% coverage gate. Browser installs Playwright Chromium and runs the five browser tests. Package runs lock check, artifact tests, and `uv build --no-sources`, then uploads only `dist/*.whl` and `dist/*.tar.gz`. Container builds/runs both test and release targets and asserts the exact native version and image label.

The action-smoke workflow invokes the local Action against the clean fixture with default upload false, then checks `rtl-lens-reports/report.json` and `.html`. Dependabot checks `uv`, `docker`, and `github-actions` weekly at `/`.

- [ ] **Step 4: Run focused and local CI-equivalent gates**

Run:

```powershell
uv lock --check
uv run pytest tests/automation -q -p no:cacheprovider
uv run ruff check --no-cache src tests tools
uv run ruff format --check src tests tools
uv run mypy src
uv run pytest --cov=rtl_lens --cov-report=term-missing --cov-fail-under=90 -q -p no:cacheprovider
uv build --no-sources
git diff --check
```

Set system Chrome for the full controller run. Docker commands remain additionally required on a Docker-capable host; do not close the runtime container gate locally if Docker remains unavailable.

- [ ] **Step 5: Commit the workflow layer**

```powershell
git add .github tests/automation/test_ci_contract.py
git commit -m "ci: verify platforms and package the analyzer action"
```

---

### Task 5: Full-range verification and independent review

**Files:**
- Modify only review-required Task 14 files.
- Update: `.planning/task14-automation/task_plan.md`, `findings.md`, `progress.md` (ignored local state).

**Interfaces:**
- Consumes: all Task 14 commits and Task 13 completion commit `46be47e`.
- Produces: controller evidence, honest not-run ledger, and final review verdict.

- [ ] **Step 1: Run the fresh controller completion gate**

Run automation, package build, security/performance, browser with system Chrome, full pytest, Ruff, mypy, scoped formatter, coverage, and diff checks from clean status. Record every skip by exact reason.

- [ ] **Step 2: Run available Docker gates or preserve the blocker**

If Docker is still absent, record all exact unrun build/test/action-smoke commands and leave runtime validation pending for a Docker/GitHub host. Static YAML/Dockerfile tests may pass but cannot replace this evidence.

- [ ] **Step 3: Obtain task-scoped and full-range reviews**

Review each commit after its controller gate. The final fresh reviewer reads `46be47e..HEAD` and checks package contents, lock determinism, Action input injection, path confinement, token isolation, exit-code preservation, upload opt-in, full Action SHAs, matrix completeness, container pin/version/labels, non-root behavior, no latest tag, workflow permissions, skip honesty, and remote-action boundaries.

- [ ] **Step 4: Close only when findings and required evidence are resolved**

Task 14 requires Spec PASS, Quality APPROVED, zero open Critical/Important findings, and no falsely claimed runtime gate. No remote push or workflow execution is part of closure.
