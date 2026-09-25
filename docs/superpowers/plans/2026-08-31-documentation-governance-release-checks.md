# Documentation, Governance, and Release Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare RTL Lens for understandable bilingual onboarding, safe public collaboration, and a build-only release check that has no publication capability.

**Architecture:** Human-facing Markdown is treated as a tested public interface: English is canonical, Chinese mirrors the core claims, configuration examples are parsed by the real model, documented commands are exercised through the real Typer application, and local links are resolved from disk. Governance is a separate review surface based on Apache-2.0 and Contributor Covenant 3.0. Release checking remains a read-only GitHub workflow that builds, inspects, installs, and retains short-lived artifacts without any publisher, credential, attestation, or write permission.

**Tech Stack:** Markdown, Python 3.11–3.13, pytest, Typer `CliRunner`, PyYAML, uv 0.12.7/uv_build 0.12.x, GitHub Actions, Playwright/System Chrome for one generated report screenshot.

**Spec:** `docs/superpowers/specs/2026-08-17-rtl-lens-design.md`

## Global Constraints

- Product name is `RTL Lens`; distribution is `rtl-lens`, import package is `rtl_lens`, and command is `rtl-lens`.
- Support Python `>=3.11,<3.14`; keep `rtl-lens 0.1.0.dev0` labeled as a development build until a separate release task changes it.
- License project-authored code under Apache-2.0; copy the canonical license text without inventing an ASF `NOTICE` or copyright owner.
- PySlang 11.x is installed by default and must provide useful native scans on Windows, Linux, and macOS. Verilator `>=5.040` remains optional locally and required in the pinned container/Action.
- Analysis is local and offline by default, with no telemetry, account, paid API, or LLM-generated diagnostic text.
- Do not assign an overall health score; preserve unknown diagnostic provenance and label missing curated explanations honestly.
- English is the canonical README. Simplified Chinese mirrors installation, quick start, privacy, limitations, and contribution claims.
- Document only real public commands: `scan`, `init`, `doctor`, `explain`, and `version`; `scan` has `--config`, `--fail-on`, `--json`, and `--html`, not `--format`.
- Release checks use ordinary `pull_request`, default-branch `push`, and `workflow_dispatch`, only `permissions: contents: read`, full-SHA Actions, and checkout `persist-credentials: false`.
- The release-check workflow may upload only wheel, sdist, and checksum as a seven-day CI artifact. It must not publish, release, push, deploy, attest, log in to a registry, reference a secret, or grant any write/OIDC permission.
- Follow TDD: observe each targeted test fail for the absent contract, implement the minimum document/configuration to pass, then run affected suites.
- No remote push, tag, workflow dispatch, GitHub Release, PyPI/container/Marketplace publication, security-contact PII, or external outreach is authorized by this task.

## File Structure

- `README.md`: canonical English landing page, source-checkout installation, quick starts, truthful comparison, screenshot, privacy/limitations, contribution links.
- `README.zh-CN.md`: Simplified Chinese mirror of every core claim, with the same tested command/configuration blocks.
- `docs/getting-started.md`: source-checkout onboarding and all five CLI command flows.
- `docs/configuration.md`: complete `.rtl-lens.toml` reference, precedence, paths, baselines, redaction, engines, and exit policy.
- `docs/architecture.md`: stable component/data flow and completeness boundaries.
- `docs/privacy.md`: local/offline guarantees, redaction, path authorization, uploads, and residual limitations.
- `docs/assets/report-preview.png`: real, redacted HTML report screenshot generated from the curated width-mismatch fixture.
- `tests/docs/test_documentation.py`: executable public-document contract, config parsing, command behavior, local links, screenshot, governance, forms, and template validation.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `LICENSE`, `docs/maintenance.md`: collaboration and maintenance policy.
- `.github/ISSUE_TEMPLATE/bug.yml`, `.github/ISSUE_TEMPLATE/feature.yml`, `.github/PULL_REQUEST_TEMPLATE.md`: structured public intake without confidential data.
- `.github/workflows/release-check.yml`: read-only build/install/inspect workflow.
- `tests/automation/test_release_workflow.py`: workflow security contract and real built-artifact behavior.
- `pyproject.toml`: explicit `license-files = ["LICENSE"]` package metadata.

---

### Task 1: Executable bilingual user documentation

**Files:**
- Modify: `README.md`
- Create: `README.zh-CN.md`
- Create: `docs/getting-started.md`
- Create: `docs/configuration.md`
- Create: `docs/architecture.md`
- Create: `docs/privacy.md`
- Create: `docs/assets/report-preview.png`
- Create: `tests/docs/__init__.py`
- Create: `tests/docs/test_documentation.py`

**Interfaces:**
- Consumes: `rtl_lens.cli.app`, `rtl_lens.config.load_config`, `rtl_lens.models.project.ProjectConfig`, the 30 generated pages under `docs/rules/`, and the curated failing width-mismatch fixture.
- Produces: marker-delimited TOML named `rtl-lens-config-example`, exact documented command strings, a canonical navigation graph, and the user-facing claims Task 2 links from governance files.

- [ ] **Step 1: Write documentation tests that name real user-facing breaks**

Create `tests/docs/test_documentation.py` with literal expectations for:

```python
USER_DOCS = (
    Path("README.md"),
    Path("README.zh-CN.md"),
    Path("docs/getting-started.md"),
    Path("docs/configuration.md"),
    Path("docs/architecture.md"),
    Path("docs/privacy.md"),
)

CORE_COMMANDS = (
    "rtl-lens init .",
    "rtl-lens doctor .",
    "rtl-lens scan .",
    "rtl-lens explain width-mismatch",
    "rtl-lens version",
)
```

The tests must:

1. require the six files above and UTF-8 text;
2. require English headings for Installation, Quick start, Privacy, Limitations, and Contributing, with mirrored Chinese headings 安装, 快速开始, 隐私, 局限, 参与贡献;
3. require both READMEs to contain every `CORE_COMMANDS` entry, `Python >=3.11,<3.14`, `PySlang >=11,<12`, `Verilator >=5.040`, `Apache-2.0`, and a pre-release/development warning;
4. extract text between `<!-- rtl-lens-config-example:start -->` and `<!-- rtl-lens-config-example:end -->` from both READMEs, assert the blocks are byte-identical, write the block to a temporary `.rtl-lens.toml`, and validate it through `load_config`;
5. copy a minimal `top.sv` into a temporary project and exercise the real `CliRunner` commands `init`, `doctor`, `scan`, `explain width-mismatch`, and `version`, asserting their public exit codes and generated JSON/HTML files;
6. parse every relative Markdown link in `USER_DOCS`, `CONTRIBUTING.md`, and `docs/maintenance.md` when present, ignore `http:`, `https:`, `mailto:`, and same-page anchors, and assert each decoded target exists beneath the repository;
7. require `docs/assets/report-preview.png` to have the PNG signature, width at least 1000, height at least 600, and a README link;
8. reject publication claims (`pip install rtl-lens` from PyPI, a stable 0.2 release, guaranteed stars/performance, telemetry, or cloud upload) unless explicitly labeled unavailable/out of scope.

- [ ] **Step 2: Run the focused test and capture RED**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/docs/test_documentation.py -q -p no:cacheprovider
```

Expected: FAIL because the Chinese README, user guides, screenshot, and executable bilingual contract do not exist; the minimal English README also lacks installation/quick-start/limitations/contribution sections.

- [ ] **Step 3: Write the canonical English documentation and Chinese mirror**

Use these exact public facts:

- installation is from a source checkout: install uv 0.12.7, run `uv sync --locked --all-groups`, then use `uv run rtl-lens ...`; do not claim PyPI availability;
- PySlang-only quick start sets `engine_mode = "disabled"`; dual-engine local use sets `engine_mode = "auto"` or `"required"` and requires Verilator `>=5.040` on `PATH`;
- both README config blocks contain `source_roots`, `include_dirs`, `defines`, `top_modules`, `timeout`, `language`, `engine_mode`, `output_dir`, `baseline_path`, `redact_sources`, `redact_path_prefixes`, `redact_environment_variables`, `fail_on`, and `graph_display_limit` with valid literal values;
- configuration precedence is defaults < `.rtl-lens.toml`/`--config` < explicit CLI `--fail-on`;
- exit codes are 0 success, 1 policy block, 2 runtime/required engine, 3 invalid project/config, with malformed Typer syntax also using 2 before application logic;
- default `auto` may produce a partial report when optional Verilator is absent; `required` fails, and `disabled` is the portable PySlang-only path;
- scans always render terminal, JSON, and self-contained HTML; reports remain local and unredacted unless the user enables redaction;
- privacy text preserves existing absolute/relative path authorization and filesystem-TOCTOU limitation verbatim in substance;
- link `docs/rules/index.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, configuration, privacy, architecture, and maintenance instead of duplicating their full text.

- [ ] **Step 4: Generate the real report screenshot**

Use a temporary project containing `src/rtl_lens/knowledge/examples/failing/width-mismatch.sv`, a validated config with `engine_mode="disabled"`, `language="zh-CN"`, and `redact_sources=true`; invoke the real local CLI to write HTML, open that local `file:` URL with Playwright using `RTL_LENS_TEST_CHROMIUM` when set, and capture a 1440×1000 full-page PNG at `docs/assets/report-preview.png`. Inspect the image and confirm it contains no absolute user/home/workspace path, token, or adversarial fixture text.

- [ ] **Step 5: Verify GREEN and documentation drift boundaries**

Run:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/docs/test_documentation.py -q -p no:cacheprovider
& '.\.venv\Scripts\python.exe' -m doctest README.md README.zh-CN.md docs/getting-started.md docs/configuration.md
& '.\.venv\Scripts\python.exe' tools/generate_rule_docs.py --check
```

Expected: all pass; the documented config validates, all five public commands are exercised, relative links resolve, and 30 generated rule pages remain unchanged.

- [ ] **Step 6: Commit the user-document interface**

```powershell
git add README.md README.zh-CN.md docs/getting-started.md docs/configuration.md docs/architecture.md docs/privacy.md docs/assets/report-preview.png tests/docs/__init__.py tests/docs/test_documentation.py
git commit -m "docs: add executable bilingual onboarding"
```

---

### Task 2: Governance, contribution, security, and maintenance policy

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `CHANGELOG.md`
- Create: `LICENSE`
- Create: `docs/maintenance.md`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/feature.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `tests/docs/test_documentation.py`

**Interfaces:**
- Consumes: Task 1 links/commands, `tools/generate_rule_docs.py --check`, existing quality commands, GitHub private vulnerability reporting UI, and official Contributor Covenant 3.0/Apache-2.0 source text.
- Produces: placeholder-free governance files and two schema-valid public Issue Forms that Task 3 packages and release checks can trust.

- [ ] **Step 1: Extend the tests before creating governance files**

Add tests that:

- require all nine files above;
- compare `LICENSE` byte-for-byte with a committed literal SHA-256 for the canonical Apache 2.0 plain-text file and require `pyproject.toml`'s `license == "Apache-2.0"`;
- require `CODE_OF_CONDUCT.md` to say `Contributor Covenant 3.0`, include the official attribution URL and CC BY-SA 4.0, contain a concrete private-reporting UI path, and contain no template customization notes, insertion markers, or unfinished-work markers;
- require `SECURITY.md` to direct vulnerabilities away from public issues and through Security → Advisories → Report a vulnerability, state that no stable version is supported yet, define what details to include, and avoid a fabricated email/response guarantee;
- require `CONTRIBUTING.md` to include setup, TDD, focused/full gates, rule YAML + failing/fixed fixtures, `tools/generate_rule_docs.py --check`, unknown-diagnostic honesty, translation review, security routing, and Apache-2.0 contribution licensing;
- require `docs/maintenance.md` to include weekly triage, monthly dependency review, 30/60/90-day routines, documented triage labels, and honest no-guarantee/no-star-scheme language;
- load both Issue Forms with `yaml.safe_load`, require unique IDs, required reproduction/problem fields, sanitized-log/IP warnings, a Code of Conduct checkbox, and no secret/contact upload field;
- require the PR template to request scope, linked issue, tests/results, public interface/report schema, docs/i18n, security/privacy, dependencies/licensing, and checklist acknowledgements;
- require `CHANGELOG.md` to follow Keep a Changelog headings with only `[Unreleased]`, and reject a fabricated released version/date.

- [ ] **Step 2: Run and observe RED**

Run the focused docs test. Expected: FAIL for each absent governance file while Task 1 user-doc assertions remain green.

- [ ] **Step 3: Add the canonical license and customized conduct policy**

Copy `https://www.apache.org/licenses/LICENSE-2.0.txt` unchanged to `LICENSE`. Adapt the official Contributor Covenant 3.0 Markdown, preserve its attribution/license, replace its reporting note with the repository's private Security → Advisories → Report a vulnerability path using a `[Conduct]` prefix, and remove the template customization note by selecting its published four-step enforcement ladder.

- [ ] **Step 4: Write contribution, security, changelog, and maintenance guides**

Keep policies operational and reversible:

- no personal email or unavailable repository URL;
- no SLA guarantee; use review targets only in `docs/maintenance.md`;
- security and conduct reports never go to public issue forms;
- triage labels are documented proposals and not claimed to exist before repository setup;
- `[Unreleased]` describes the current development capabilities without claiming a release;
- 30 days: weekly issue review and dependency/security intake; 60 days: documentation/rule translation and false-positive review; 90 days: compatibility evidence, stale dependency/CI review, and release-readiness decision;
- no buying, exchanging, botting, or coercing stars; adoption evidence and successful scans are primary.

- [ ] **Step 5: Add GitHub forms and PR template**

The bug form covers defects and false positives and requires version, OS, Python, engine versions, minimal sanitized RTL, config, command, expected/actual behavior, and reproduction. The feature form covers features and rule requests and requires problem, desired result, alternatives, evidence/source for diagnostic rules, and willingness to contribute. Both include private-reporting warnings and a required Code of Conduct checkbox. Do not auto-assign nonexistent labels or use a placeholder repository URL.

- [ ] **Step 6: Verify GREEN and commit governance**

Run the focused docs test, doctest command, rule-doc drift check, Ruff check/format over `tests`, and YAML parsing. Then commit:

```powershell
git add CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md CHANGELOG.md LICENSE docs/maintenance.md .github/ISSUE_TEMPLATE/bug.yml .github/ISSUE_TEMPLATE/feature.yml .github/PULL_REQUEST_TEMPLATE.md tests/docs/test_documentation.py
git commit -m "docs: establish public project governance"
```

---

### Task 3: Build-only release workflow and installable artifact evidence

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/automation/test_package_contract.py`
- Create: `.github/workflows/release-check.yml`
- Create: `tests/automation/test_release_workflow.py`

**Interfaces:**
- Consumes: Task 2 `LICENSE`, Task 1 docs tests/doctests, Task 14 immutable Action pins and uv 0.12.7, `uv build --no-sources`, console entry point `rtl-lens`, and packaged knowledge/resource files.
- Produces: wheel/sdist containing the Apache license and a release-check workflow structurally incapable of publication.

- [ ] **Step 1: Write package and workflow tests first**

Extend the package contract to build wheel/sdist and assert:

- `[project].license-files` in `pyproject.toml` is exactly `["LICENSE"]`;
- wheel `METADATA` has `License-Expression: Apache-2.0` and `License-File: LICENSE`;
- wheel contains `.dist-info/licenses/LICENSE` with the canonical bytes;
- sdist contains top-level `LICENSE`, `README.md`, `pyproject.toml`, and all existing runtime resources;
- exactly one wheel and one sdist are produced.

Create `tests/automation/test_release_workflow.py` that parses YAML with `yaml.BaseLoader` and asserts:

```python
assert workflow["permissions"] == {"contents": "read"}
assert set(workflow["on"]) == {"pull_request", "push", "workflow_dispatch"}
```

It must also require:

- default-branch-only `push` (use the repository's verified default branch `branches: [master]`, not tags or release events);
- no `pull_request_target`, `workflow_run`, `release`, environment, secrets, token, registry, deploy, attestation, publish, `gh release`, `docker push/login`, or write permission;
- checkout/setup-python/setup-uv/upload-artifact at the exact Task 14 SHAs and same-line release comments;
- checkout `persist-credentials: false`, uv `0.12.7`, `uv lock --check`, locked sync, docs tests, doctest, `uv build --no-sources`, archive/package test, two clean install roots (wheel and sdist), `uv pip check`, CLI/resource commands from outside the checkout, local SHA-256 generation, and artifact upload with explicit files, `if-no-files-found: error`, `retention-days: 7`, and no hidden files;
- artifact name contains `${{ github.sha }}` only as a declarative `with` value, never interpolated into a shell program.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
& '.\.venv\Scripts\uv.exe' run python -m pytest tests/automation/test_package_contract.py tests/automation/test_release_workflow.py -q -p no:cacheprovider
```

Expected: workflow tests fail because `release-check.yml` is absent, and the static package contract fails because `[project].license-files` is not yet explicit. Artifact-level license assertions may already pass through build-backend defaults, so they are not the sole RED signal.

- [ ] **Step 3: Make license packaging explicit**

Add this PEP 639 field under `[project]` without changing version or dependencies:

```toml
license = "Apache-2.0"
license-files = ["LICENSE"]
```

Run `uv lock --check`; if project metadata changes the lock representation, run `uv lock` once, inspect the diff, and include only the required metadata change.

- [ ] **Step 4: Implement the release-check workflow**

Use one Ubuntu job with a 30-minute timeout. Steps, in order:

1. immutable checkout with credential persistence disabled;
2. Python 3.12 setup;
3. setup-uv 0.12.7 with `uv.lock` cache;
4. `uv lock --check` and `uv sync --locked --all-groups`;
5. docs test, release/package test, doctest, and generated-rule drift check;
6. `uv build --no-sources`;
7. create `.release-check/wheel` and `.release-check/sdist`, install the matching local artifact into each via explicit `uv pip install --python`, and run `uv pip check`;
8. from a temporary directory outside `${{ github.workspace }}`, run each installed `rtl-lens --help`/`version` and a Python resource assertion for `rtl_lens.knowledge/rules/width-mismatch.yaml`;
9. generate `dist/SHA256SUMS` using a Python one-liner that sorts filenames and hashes bytes (no platform-specific `sha256sum` dependency);
10. upload only `dist/*.whl`, `dist/*.tar.gz`, and `dist/SHA256SUMS` as `rtl-lens-release-check-${{ github.sha }}` for seven days.

- [ ] **Step 5: Verify actual artifact behavior and workflow policy**

Run the focused tests, `uv lock --check`, `uv build --no-sources`, and a local target-directory wheel smoke that proves `rtl_lens.__file__` and the width rule come from the built artifact. Do not dispatch the workflow or upload anything remotely.

- [ ] **Step 6: Commit release checks**

```powershell
git add pyproject.toml uv.lock tests/automation/test_package_contract.py tests/automation/test_release_workflow.py .github/workflows/release-check.yml
git commit -m "ci: add non-publishing release checks"
```

---

### Task 4: Task 15 completion gate and independent review

**Files:**
- Modify only files required by valid review findings.

**Interfaces:**
- Consumes: Tasks 1–3 commits, Task 14 completion commit `ece27a0`, and the Task 15 official-source research note.
- Produces: Task 15 Spec PASS, Quality APPROVED, zero open Critical/Important findings, and an explicit no-publication handoff to Task 16.

- [ ] **Step 1: Run the fresh completion gate**

Run:

```powershell
& '.\.venv\Scripts\uv.exe' lock --check
& '.\.venv\Scripts\python.exe' -m pytest tests/docs tests/automation -q -p no:cacheprovider
& '.\.venv\Scripts\python.exe' -m doctest README.md README.zh-CN.md docs/getting-started.md docs/configuration.md
& '.\.venv\Scripts\python.exe' tools/generate_rule_docs.py --check
& '.\.venv\Scripts\python.exe' -m ruff check --no-cache src tests tools
& '.\.venv\Scripts\python.exe' -m ruff format --check src tests tools
& '.\.venv\Scripts\python.exe' -m mypy src
& '.\.venv\Scripts\python.exe' -m pytest --ignore=tests/browser --cov=rtl_lens --cov-report=term-missing --cov-fail-under=90 -q -p no:cacheprovider
$env:RTL_LENS_TEST_CHROMIUM='C:\Program Files\Google\Chrome\Application\chrome.exe'; & '.\.venv\Scripts\python.exe' -m pytest tests/browser -q -p no:cacheprovider
& '.\.venv\Scripts\uv.exe' build --no-sources
```

Classify absent Docker/browser/symlink capabilities honestly; never turn a not-run gate into a pass.

- [ ] **Step 2: Review documentation as a public interface**

Review every install/command/config/version/engine/privacy/exit claim against the actual CLI and model; compare English/Chinese core claims; inspect the screenshot; verify no absolute machine path, private data, placeholder, fake repository URL, broken relative link, unsupported performance claim, health score, star guarantee, or publication instruction.

- [ ] **Step 3: Obtain task-scoped and whole-range reviews**

Each implementation task requires Spec PASS and Quality APPROVED before the next task. The final reviewer reads `ece27a0..HEAD` and the official-source note, checks package metadata, workflow authority, confidential reporting, Contributor Covenant customization, bilingual parity, executable examples, and remote-action boundaries.

- [ ] **Step 4: Close locally and stop before publication**

Task 15 closes only after all valid Critical/Important findings are fixed and re-reviewed. Present local commits/evidence; do not push, tag, dispatch, publish, or create external contacts. Task 16 owns compatibility evidence and the local release candidate.
