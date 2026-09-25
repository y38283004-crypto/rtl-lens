# Compatibility Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproducibly scan explicitly scoped files from ten pinned public RTL repositories and verify clean scans from both local distribution formats, without publishing or fabricating adoption.

**Architecture:** A developer-only offline script validates a TOML corpus, checks already-acquired immutable Git checkouts and license hashes, stages an exact file subset, and invokes the existing CLI in a timed subprocess. JSON observations and a Markdown table derive from validated redacted reports. Network acquisition is a separate controller step; missing inputs produce `not-run`, not an invented result.

**Tech Stack:** Existing Python 3.11–3.13, Pydantic, stdlib TOML/JSON/subprocess/tempfile, Git, uv 0.12.7, Pytest, existing RTL Lens CLI.

**Spec:** `docs/superpowers/specs/2026-08-17-rtl-lens-design.md`, especially sections 8, 10.5 and 12; master implementation plan Task 16.

## Global Constraints

- Support Python `>=3.11,<3.14` in the first public release.
- License project-authored code under Apache-2.0.
- Analysis is local and offline by default, with no telemetry, account, paid API, or LLM-generated diagnostic text.
- Do not assign an overall health score.
- Unknown diagnostics retain original engine data and are labeled as lacking a curated explanation.
- Use subprocess argument arrays with `shell=False`; bound execution time and captured output.
- Do not publish to GitHub, PyPI, a container registry, or GitHub Marketplace without a separate explicit user confirmation at the release checkpoint.
- External beta invitations, GitHub pushes, repository creation, tags on a remote, package uploads, container pushes, Marketplace listing, and promotional posts require separate user approval.
- Do not change production analysis behavior, dependencies, version, engine requirements, or existing workflow authority for this evidence task.
- Whole-repository compatibility, simulation correctness, zero false positives, timing comparisons, external beta success, and dual-engine success must not be inferred from a scoped PySlang scan.

## File and interface map

- `scripts/scan_compatibility.py`: typed manifest validation, verified-cache staging, existing CLI subprocess orchestration, sanitized observation aggregation, offline command entrypoint. No installed-package API is added.
- `tests/integration/test_compatibility_runner.py`: real temporary Git repositories and CLI scans; invalid manifests/cache/license/path cases; isolated external-failure doubles only where necessary.
- `compatibility.toml`: ten verified immutable public-source subsets, provenance and scan configuration.
- `tests/integration/test_compatibility_manifest.py`: real checked-in corpus contract independent of network/cache availability.
- `tests/e2e/test_release_candidate.py`: real wheel and sdist builds, independent environments, installed clean fixture scan from outside checkout.
- `docs/beta/compatibility.md`, `docs/beta/feedback.md`, `docs/release-checklist.md`: observed results, honest beta status, release blockers.
- `.gitignore`: ignore only new `.artifacts/` evidence output; source caches reside outside this Git source tree.
- `CHANGELOG.md`: record actual new developer verification tooling under Unreleased.

### Task 1: Offline compatibility runner

**Files:** Create `scripts/scan_compatibility.py`, `tests/integration/test_compatibility_runner.py`; modify `.gitignore` to add `.artifacts/`.

**Interfaces:** Export `ProjectSpec`, `CompatibilityManifest`, `load_manifest(path: Path) -> CompatibilityManifest`, `scan_project(project: ProjectSpec, checkout: Path, output: Path, *, engine_mode: str = "disabled") -> dict[str, object]`, and `run_manifest(manifest: CompatibilityManifest, cache_dir: Path, output: Path, *, engine_mode: str = "disabled") -> list[dict[str, object]]`. These names are the Task 2 test/runner contract. CLI options: `--manifest` (default `compatibility.toml`), `--cache-dir` (default `<system-temp>/rtl-lens-compatibility-cache`), `--output` (default `.artifacts/compatibility`), `--engine-mode` (`disabled`, `auto`, `required`; default `disabled`). No fetch option or network implementation.

- [ ] **Step 1: Add RED behavior tests before implementation.** Use real Git initialized in `tmp_path` with command-local user identity and hooks disabled; no changes to user Git config. Define a minimal module `module top; endmodule`, MIT license fixture, and obtain its actual commit. Fixture manifest shape:

```toml
schema_version = 1
[[projects]]
id = "tiny-core"
repository = "https://github.com/example/tiny-core"
commit = "1111111111111111111111111111111111111111"
license = "MIT"
license_file = "LICENSE"
license_sha256 = "2222222222222222222222222222222222222222222222222222222222222222"
attribution = "Tiny Core contributors"
scope = "Standalone top module; no simulation or whole-repository claim."
files = ["rtl/top.sv"]
top_files = ["rtl/top.sv"]
include_dirs = []
defines = []
top_modules = ["top"]
expected_scan_state = "complete"
```

Replace commit/license digest in test data with values of the actual test fixture, not in expected outcome assertions. Tests import the script using importlib if `scripts` is not importable. Illustrative behavioral checks:

```python
def test_cached_clean_fixture_produces_redacted_complete_scan(tmp_path):
    project, checkout = make_committed_fixture(tmp_path)
    output = tmp_path / "observations"
    result = scan_project(project, checkout, output)
    assert result["status"] == "complete"
    assert result["exit_code"] == 0
    assert result["diagnostic_count"] == 0
    assert result["unknown_count"] == 0
    assert result["redacted"] is True
    assert result["source_count"] == 1
    assert not (checkout / ".rtl-lens.toml").exists()
    assert str(tmp_path) not in (output / "result.json").read_text()
```

`make_committed_fixture` belongs only in the test file. Add independently derived tests for a real error-producing fixture (policy exit 1 remains a completed observation), missing cache (`not-run`, counts `null`), tampered selected file/license (no scan), mismatched HEAD, malformed SHA/repository/license ID, duplicate IDs, unsafe POSIX/Windows paths including traversal/absolute/drive/UNC/backslash, missing top file, non-positive or oversized resource use, and subprocess timeout/missing/malformed report (no stale success). Test empty output or existing nonempty output refusal so a failed rerun never reuses old reports. Test generated aggregate JSON/Markdown identity, count, redaction, and missing-result semantics with real outputs.

- [ ] **Step 2: Run RED.** `python -m pytest tests/integration/test_compatibility_runner.py -q -p no:cacheprovider`. Capture the expected missing-runner failure without calling it a passing gate.

- [ ] **Step 3: Implement manifest and cache boundary.** Pydantic models use `extra="forbid"`; schema version exactly 1; 1–10 unique projects; IDs match `[a-z0-9][a-z0-9-]{0,63}`; full lowercase SHA40 and license SHA256; GitHub HTTPS owner/repository URLs without credentials, queries, fragments or option-like segments; allow `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `Apache-2.0`, `CC0-1.0` only. Require nonempty attribution/scope, 1–200 unique relative files (`.v`, `.sv`, `.vh`, `.svh`), nonempty top_files subset of HDL source files, canonical relative include directories (`.` permitted), expected state `complete` or `partial`. For paths reject absolute, empty, `..`, backslash, drive/colon and control characters. Limit manifest bytes to 1 MiB, each staged source/license to 2 MiB, total selected sources to 32 MiB; validate limits before copying.

Cache layout is `<cache-dir>/<id>/<commit>/`. Reject cache/source root or output overlap and symlink escape. Verify checkout HEAD equals manifest commit using Git with shell disabled, command timeout and bounded output; selected license/source files must be regular contained files with bytes matching their Git blob at the pinned commit, not merely a claimed HEAD. Verify license SHA256 as well. The controller owns fetch/checkout verification; the runner never modifies the checkout or trusts its configuration file. No upstream executable, Makefile, hook, shell script, dependency installer, or submodule is executed. Never clean or reset an existing cache.

- [ ] **Step 4: Implement staged scan and evidence.** Each scan creates a private temporary staging directory, copies only verified files preserving their relative names, and writes its own config. Configure source_roots `["."]`, manifest include/define/top values, timeout 30, explicit chosen engine mode, `redact_sources=true`, and fixed local output names. Invoke `[sys.executable, "-m", "rtl_lens.cli", "scan", str(stage)]` with `shell=False`, stdin/stdout/stderr redirected to DEVNULL and outer timeout 90 seconds. No unbounded pipe capture. Record `perf_counter` elapsed separately from reported engine durations. Always clean only the owned temporary staging directory.

Before copying outputs, require a fresh JSON report <=16 MiB validated as `ScanReport` and `metadata.redacted=True`, plus HTML <=32 MiB. Preserve only redacted reports in output. No raw subprocess errors, staging paths, environment values, or unreviewed stdout/stderr belong in aggregate output. Use bounded fixed failure kinds; engine failure details can remain in validated redacted reports. Result fields: `id`, `repository`, `commit`, `license`, `license_sha256`, `scope`, `files`, `top_files`, `expected_scan_state`, `engine_mode`, `status` (`complete`, `partial`, `failed`, `not-run`), `exit_code`, `elapsed_ms`, `diagnostic_count`, `unknown_count`, `source_count`, `redacted`, `requested_engines`, `completed_engines`, `tool_versions` (Python/RTL Lens/engine versions), and `failures` (list of fixed kinds). Unknown count is findings without curated explanation (`engine-native:` canonical identity); preserve original details in reports. Unavailable counts and redaction are null, never fabricated zeros/true. Completed report with policy exit 1 remains complete; runtime/config/missing/invalid report is failed; absent cache/Git is not-run. An empty source report is failed, never compatibility evidence.

Write `result.json` plus optional `report.json`/`report.html` per project; `run_manifest` writes aggregate `results.json` and `summary.md` with one row per project. Refuse existing nonempty or unsafe output directories to prevent stale reuse or destructive overwrites. Validate aggregate output/cache separation before any write. CLI exit 0 only if all observations complete; partial/failed/not-run returns 1, invalid invocation/manifest/output returns 2. Markdown includes the warning that complete means analysis completed, not clean RTL. Escape manifest-derived table values.

- [ ] **Step 5: GREEN and commit.** Run focused runner tests and Ruff on the two new Python files, existing nonbrowser regression once, then commit only Task 1 files as `feat: add offline compatibility evidence runner`. Write report with commands and actual RED/GREEN output; independent task review follows.

### Task 2: Verified corpus and observations

**Files:** Create `compatibility.toml`, `tests/integration/test_compatibility_manifest.py`, `docs/beta/compatibility.md`. Consume the primary-source research note and Task 1 interfaces.

- [ ] **Step 1: RED corpus contract.** Load the real manifest and assert exactly ten unique HTTPS repositories/IDs, pinned SHA40, allowed license with hash, intended top files included, and declared scope/expected state. Expected initial failure: manifest missing, not network failure.

```python
def test_corpus_is_pinned_scoped_and_attributed():
    manifest = load_manifest(ROOT / "compatibility.toml")
    assert len(manifest.projects) == 10
    assert len({project.repository for project in manifest.projects}) == 10
    assert all(project.top_files and project.attribution and project.scope
               for project in manifest.projects)
```

- [ ] **Step 2: Verify and pin.** Controller retrieves each researched HTTPS repository into an external cache with Git init + `fetch --depth=1 <url> <sha>` + detached checkout. Use command-local hooks disabled, no submodules or upstream builds, and no credentials. Existing caches are verified/reused, never reset or deleted. Verify exact HEAD, source bytes/paths, license text and SHA256, and record immutable source links. Only then add the ten manifest entries. If source access fails, record not-run and retain the open gate instead of substituting fake identifiers.
- [ ] **Step 3: Scan.** Run `python scripts/scan_compatibility.py --manifest compatibility.toml --cache-dir <verified-external-cache> --output .artifacts/compatibility/<unique-run-id>`. Read every result including failures and unknowns. Run repeated verification only for diagnosed runner problems or explicitly changed scan scope; don't remove adverse results to improve the table.
- [ ] **Step 4: Publish local evidence document.** `docs/beta/compatibility.md` records the date, exact tool versions and command, immutable repository/commit/license/top-file links, explicit file-subset boundaries, source/diagnostic/unknown counts, elapsed observations, engine state, failure kinds and redaction. Reference generated local reports without committing upstream sources or report dumps; include commands to recreate cache and scans. Do not imply 10 whole projects or dual engines passed from portable subsets. Initial observations remain part of the record if scope is corrected.
- [ ] **Step 5: GREEN and commit.** Run manifest + runner tests, inspect Git status for accidental upstream/report additions, and commit Task 2 files as `test: record pinned RTL compatibility observations`. Independent review checks source provenance and result honesty.

### Task 3: Installed release-candidate scans and honest release checklist

**Files:** Create `tests/e2e/test_release_candidate.py`, `docs/beta/feedback.md`, `docs/release-checklist.md`; modify `CHANGELOG.md` Unreleased only.

**Interfaces:** Existing `uv build --no-sources`, installed `rtl-lens` console entrypoint, ScanReport JSON schema, Task 2 observed compatibility evidence. No version bump or publication credentials.

- [ ] **Step 1: RED clean installed scan check.** Write a regression test building wheel+sdist to a temporary directory, making separate environments, installing each local artifact, checking dependency consistency, then invoking installed CLI on a clean `module top; endmodule` project outside source checkout. Prove import originates in each environment using Python `-I`. Configure PySlang-only/redaction explicitly. Independently assert exit0, requested/completed `["pyslang"]`, source_count1, complete state, findings empty, redacted true, valid self-contained HTML. Do not demand a fake RED when existing packaging already satisfies new test; document initial green as expanded evidence, not a fixed defect.
- [ ] **Step 2: Execute actual artifact tests.** Use current interpreter/uv executables and bounded subprocess timeouts; skip only when uv genuinely absent, but controller must run with uv available. Resolve executable paths separately for Windows/POSIX. Dependencies may use configured caches/network for installation, but scan execution is local. Limit subprocess error output and avoid leaking machine paths in public docs. No unit-test mock can substitute for these installed scans.
- [ ] **Step 3: Record truthful beta and release status.** Feedback document states zero external beta attempts collected and invitations pending separate approval; include an opt-in template for platform/tool versions, installation/scan result, friction, consent to share a redacted reproduction, no star requirement and no private RTL upload. Checklist distinguishes local passed/failed/not-run from remote checks, Docker/pinned Verilator, ten external users, private security reporting setup, demo/case studies, package-name availability and publication approval. Do not mark a release ready while mandatory external/platform gates remain unmet. Add actual evidence tooling to Unreleased changelog.
- [ ] **Step 4: Verify and commit.** Run installed-artifact tests, docs/link tests, runner/manifest tests, lint/format on `src tests tools scripts`, mypy src, full nonbrowser coverage>=90, browser suite with actual browser, lock/build/checksums. Detect Docker/Verilator capabilities; absent tools are explicit not-run gates. Commit Task 3 files as `test: verify installed release candidate scans`.
- [ ] **Step 5: Final independent review and handoff.** Review Task 16 range from its recorded base to HEAD, address material findings with one consolidated fix wave, and report local evidence plus pending external release requirements. Stop before invitations, push, remote tag, workflow dispatch, or publication. Preserve the development worktree and reproducibility records.

## Preflight decisions

- Exact staged file subsets avoid changing product discovery to support file lists. Cost if wrong: broaden the manifest scopes and repeat observations, without changing the scanner API.
- Network acquisition is separate from the offline runner; cache absence means not-run. Cost if wrong: add an explicitly opted-in acquisition helper later; ordinary analysis remains offline.
- Portable observations use PySlang-only mode and cannot close the dual-engine release gate. Cost if wrong: run the same pinned inputs with required Verilator in a supported environment.
- Installed-scan test may be green on first execution because packaging already exists; truthful initial evidence takes precedence over inventing a failing production change.
