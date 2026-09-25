# RTL Lens Task 13 Security, Privacy, and Bounded-Resource Implementation Plan

> **Execution contract:** Execute task by task with strict RED/GREEN tests, a scoped local commit, and an independent read-only review before advancing. Do not push, publish, upload, add telemetry, or contact external parties.

**Goal:** Close RTL Lens's remaining local attack surfaces while preserving offline, immutable, deterministic report behavior.

**Architecture:** Add `rtl_lens.security` helpers for resolved destinations and pure report redaction. Keep path authorization in CLI/service composition, atomic replacement in renderers, and replace Verilator's post-hoc `capture_output` checks with a shell-free runner that drains both streams concurrently into fixed-size buffers. Preserve the existing project/SARIF symlink checks and Jinja autoescape.

**Binding research:** `docs/superpowers/research/2026-08-29-task13-security-hardening.md`

**Starting commit:** `9c9e39e`

## Cross-task rulings

1. Modify the actual adapter `src/rtl_lens/engines/verilator_engine.py`; the master plan's `verilator.py` path is stale.
2. A relative `scan.output_dir` is project-confined; an absolute output root is explicit user authorization.
3. Relative `--json`, `--html`, and `scan.baseline_path` values resolve beneath the configured output root. Resolved escape is a configuration error; explicit absolute destinations remain allowed.
4. Direct writers reject an existing leaf symlink. Full root authorization remains outside generic writers.
5. `scan.redact_sources=true` marks a report shareable. Shareable serialization redacts every user/tool-controlled text field, automatically treats the report project root as `<project>`, removes snippets, and never mutates the frozen input model. RTL Lens-owned enums, hashes, fingerprints, canonical IDs, timestamps, and schema versions remain unchanged.
6. Configuration names exact environment variables whose values are secret. Values are never guessed, persisted, hashed, logged, or returned in errors.
7. Existing distinct Verilator failure kinds remain stable.
8. The 500-diagnostic/five-second limit is a regression ceiling, not a benchmark claim.

## Task 1: Resolve and enforce destination boundaries

**Files:**

- Create `src/rtl_lens/security/__init__.py`, `src/rtl_lens/security/paths.py`, `tests/security/__init__.py`, `tests/security/test_path_boundaries.py`
- Modify `src/rtl_lens/cli.py`, `src/rtl_lens/services/scan.py`, both file renderers, affected CLI/scan/renderer tests

### Step 1: Write failing adversarial tests

Cover:

- relative `output_dir = "../outside"` and a symlinked output root escaping the project are rejected;
- defaults resolve to `<output-root>/report.{json,html}`;
- relative overrides resolve beneath the configured output root, not the project root;
- `..`, nested symlink-parent, and sibling-prefix escapes are rejected;
- explicit absolute report destinations are allowed;
- relative baselines resolve beneath the configured output root and explicit absolute baselines remain allowed;
- both atomic writers reject existing destination symlinks without changing their targets;
- current project-discovery and SARIF escape tests stay green.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/security/test_path_boundaries.py tests/e2e/test_cli_scan.py tests/unit/test_scan_service.py tests/unit/test_json_report.py tests/unit/test_html_report.py -q -p no:cacheprovider
```

Expected RED: the security module is missing and current override/baseline semantics violate the contract.

### Step 2: Implement the minimal path API

```python
def resolve_output_root(project_root: Path, configured: Path) -> Path: ...
def resolve_report_destination(
    project_root: Path,
    output_dir: Path,
    override: Path | None,
    default_name: str,
) -> Path: ...
def resolve_baseline_path(
    project_root: Path,
    output_dir: Path,
    configured: Path,
) -> Path: ...
def validate_atomic_destination(destination: Path) -> Path: ...
```

Resolve candidate and boundary before `is_relative_to`; reject relative escape and leaf symlinks; never search a legacy fallback path. Replace CLI `_output_path`, use the baseline resolver during preflight, and validate both writer destinations before `mkstemp`.

### Step 3: Verify, commit, review

Run focused tests plus `tests/unit/test_project.py`, `tests/unit/test_sarif.py`, and `tests/e2e/test_cli_exit_codes.py`; then Ruff, mypy, changed-file format, and `git diff --check`.

Commit: `fix: confine report and baseline paths`

Review must cover Windows/POSIX path flavors, parent/leaf symlinks, missing parents, explicit absolute authorization, and ensure no string-prefix boundary test exists.

## Task 2: Redact every shareable-report string and prove HTML safety

**Files:**

- Create `src/rtl_lens/security/redaction.py`, `tests/security/conftest.py`, `tests/security/test_redaction.py`, `tests/security/test_html_injection.py`
- Modify the security exports, project/config models, CLI, JSON/HTML renderers and exports, and affected config/init/e2e tests

### Step 1: Write failing redaction/injection tests

Build a frozen report containing hostile HTML and sensitive values in metadata, findings, provenance, engine version/failure, graph names, and analysis warnings. Assert:

- home prefixes redact across slash styles and Windows case variation;
- configured prefixes use deterministic labels and longest-prefix-first replacement;
- only explicitly named non-empty environment values redact;
- snippets disappear from findings and provenance;
- the input report remains model-equal and repeated redaction is deterministic;
- the output records `metadata.redacted=true`;
- JSON, visible HTML, and embedded `report-data` contain no home/user/project/secret canary;
- no hostile element, event attribute, external resource, or network URL is created;
- a non-shareable report preserves its local data.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/security/test_redaction.py tests/security/test_html_injection.py -q -p no:cacheprovider
```

Expected RED: policy/transformation APIs and renderer integration are absent.

### Step 2: Implement immutable redaction

Add strict frozen config fields:

```python
redact_path_prefixes: tuple[Path, ...] = ()
redact_environment_variables: tuple[str, ...] = ()
```

Add frozen `RedactionPolicy` and pure `redact_report(report, policy)`. Transform every user/tool-controlled text field through typed `model_copy` operations, automatically map `metadata.project_root` to `<project>`, remove snippets, set the flag, and validate the resulting `ScanReport`. Do not rewrite schema/enums/digests/fingerprints/canonical IDs. Recognize both path separators, handle Windows-shaped prefixes case-insensitively, and ignore unset/empty secrets.

Add `render_html_report(...) -> str` and `render_shareable_html(...) -> str`. Writers redact before serialization/rendering when the report is marked redacted or a policy is passed. CLI builds the policy only for shareable scans, resolves relative configured prefixes from the project root, and reads only named environment variables.

### Step 3: Verify, commit, review

Run security tests, affected config/init/renderer/CLI tests, all browser tests with system Chrome, Ruff, mypy, format, and diff checks.

Commit: `fix: redact shareable reports deterministically`

Review must search complete HTML and decoded JSON for every canary, inspect embedded JSON/script boundaries, prove immutability, and verify no secret value enters an exception or config digest.

## Task 3: Replace post-hoc Verilator capture with a hard bound

**Files:**

- Create `tests/security/test_subprocess_safety.py`
- Modify `src/rtl_lens/engines/verilator_engine.py`, `tests/fixtures/bin/fake_verilator.py`, `tests/unit/test_verilator_engine.py`

### Step 1: Write failing process-boundary tests

Cover:

- version and analysis use argv lists, `shell=False`, `stdin=DEVNULL`, and separate binary pipes;
- production no longer uses `subprocess.run(..., capture_output=True)`;
- metacharacters remain one argument and create no sentinel;
- simultaneous stdout/stderr pressure cannot deadlock;
- either 1 MiB overflow kills/reaps the child, returns the correct kind, and exposes `[truncated by rtl-lens]` in a message of at most 500 characters;
- timeout kills/reaps and remains distinct from missing executable;
- spawn failure, reader failure, and kill races are contained;
- SARIF remains separately capped at 16 MiB.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/security/test_subprocess_safety.py tests/unit/test_verilator_engine.py -q -p no:cacheprovider
```

Expected RED: production still uses `subprocess.run(capture_output=True)` and overflow messages lack the marker.

### Step 2: Implement fixed-size concurrent capture

Use `Popen` with an argv list, `shell=False`, `stdin=DEVNULL`, `stdout=PIPE`, `stderr=PIPE`, and binary mode. One reader thread per pipe retains at most its fixed prefix. First overflow marks the stream and idempotently kills the child. The controller waits only to the deadline, kills on timeout, waits, closes streams, and joins both readers before returning or raising. Decode retained bytes deterministically with UTF-8 replacement. Use this runner for version and analysis.

No path may retain unbounded bytes, leave a non-daemon reader alive, or expose a subprocess/reader exception across `VerilatorEngine.run()`.

### Step 3: Verify, commit, review

Run subprocess security, Verilator unit, and engine contract tests; then Ruff, mypy, format, and diff checks.

Commit: `fix: bound and reap Verilator subprocesses`

Review must trace spawn failure, normal/nonzero exit, both overflow paths, simultaneous overflow, timeout, kill race, reader exception, and join cleanup.

## Task 4: Add the large-report ceiling and close Task 13

**Files:**

- Create `tests/performance/__init__.py`, `tests/performance/test_large_report.py`
- Modify `README.md` and only review-required Task 13 files

### Step 1: Add the regression ceiling

Build exactly 500 deterministic findings with mixed severities, provenance, snippets, hostile characters, and module relationships. Write/parse JSON and HTML and assert exactly 500 findings, no shareable canary, self-contained HTML, and separate JSON/HTML rendering times below five seconds.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/performance/test_large_report.py -q -p no:cacheprovider
```

If already GREEN, record a characterization result; do not add artificial code merely to force RED. If it fails, profile and remove only evidenced repeated work or quadratic behavior. Never loosen escaping/validation or raise the ceiling.

Document offline-only behavior, absolute-destination authorization, relative confinement, all redaction options, no telemetry, and that remote upload remains opt-in and outside Task 13.

### Step 2: Run the completion gate

With `RTL_LENS_TEST_CHROMIUM` set to system Chrome, run security/performance tests, full pytest, Ruff, mypy, Task 13 changed-file format, and `git diff --check`. Require no failed test, unclassified skip, sensitive artifact canary, network request, or open Critical/Important finding. Record pre-existing out-of-range formatting separately.

### Step 3: Commit and full-range review

Commit: `test: enforce secure large-report ceilings`

Generate a `9c9e39e..HEAD` review package. A fresh reviewer must read the full range and assess path authorization, symlink/TOCTOU limits, secret lifetime, immutable redaction, every HTML/JSON context, subprocess cleanup/byte bounds, timeout taxonomy, cross-platform behavior, performance stability, documentation honesty, and remote-action boundaries.

Task 13 closes only after a fresh controller completion gate and final spec PASS / quality APPROVED with no open Critical or Important findings.
