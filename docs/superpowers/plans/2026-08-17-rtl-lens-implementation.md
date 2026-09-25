# RTL Lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prepare the first public release of RTL Lens, a cross-platform dual-engine SystemVerilog diagnostic CLI with deterministic bilingual explanations, offline reports, and GitHub Actions integration.

**Architecture:** A Python application resolves an RTL project once, runs PySlang and optional Verilator adapters behind a common protocol, normalizes and merges diagnostics into versioned Pydantic models, enriches findings from a curated data-only knowledge base, and renders terminal, JSON, HTML, and CI outputs. Engine code never imports renderers; renderers consume only the stable `ScanReport` model.

**Tech Stack:** Python 3.11–3.13, uv/uv_build, PySlang 11.x, Pydantic 2.x, Typer, Rich, Jinja2, PyYAML, Pytest, Ruff, mypy, Beautiful Soup, Playwright, Verilator 5.x SARIF, Docker, GitHub Actions.

## Global Constraints

- Product name is `RTL Lens`; distribution is `rtl-lens`, import package is `rtl_lens`, and command is `rtl-lens`.
- If the PyPI distribution name is unavailable at publication time, use `rtl-lens-cli`; do not rename the product, import package, or command.
- Support Python `>=3.11,<3.14` in the first public release.
- License project-authored code under Apache-2.0.
- PySlang is installed with the default package and must provide a useful native scan on Windows, Linux, and macOS.
- Verilator is an optional local engine in automatic mode and a required pinned engine inside the official container and GitHub Action.
- The first promoted release includes both engine adapters; internal commits may introduce them sequentially.
- Analysis is local and offline by default, with no telemetry, account, paid API, or LLM-generated diagnostic text.
- Do not assign an overall health score.
- Unknown diagnostics retain original engine data and are labeled as lacking a curated explanation.
- Use subprocess argument arrays with `shell=False`; bound execution time and captured output.
- Escape every source-derived value before placing it in HTML.
- Default GitHub Action permissions are read-only and report artifact upload is opt-in.
- Do not publish to GitHub, PyPI, a container registry, or GitHub Marketplace without a separate explicit user confirmation at the release checkpoint.
- Follow test-driven development: observe a targeted failing test, implement the minimum behavior, run the targeted test, then run the affected suite.
- Commit after every task using the exact scoped file list shown in that task.

## Planned File Structure

```text
rtl-lens/
├── pyproject.toml                  # Package metadata, dependencies, entry point, tool configuration
├── uv.lock                         # Reproducible Python dependency resolution
├── README.md                       # English landing page and quick start
├── README.zh-CN.md                 # Chinese landing page and quick start
├── LICENSE                         # Canonical Apache-2.0 text
├── CHANGELOG.md                    # Keep-a-Changelog release history
├── SECURITY.md                     # Private vulnerability reporting policy
├── CONTRIBUTING.md                 # Setup, tests, rule contribution workflow
├── CODE_OF_CONDUCT.md              # Contributor Covenant
├── action.yml                      # Marketplace-compatible Docker Action metadata
├── Dockerfile                      # Pinned RTL Lens + Verilator runtime
├── src/rtl_lens/
│   ├── __init__.py                 # Package version export
│   ├── cli.py                      # Typer commands and exit-code boundary
│   ├── config.py                   # TOML loading, defaults, precedence, digest
│   ├── project.py                  # RTL source discovery and resolved project creation
│   ├── models/
│   │   ├── project.py              # ProjectConfig and ResolvedProject
│   │   ├── engine.py               # EngineRequest, EngineRun, EngineFailure, protocol types
│   │   ├── diagnostic.py           # SourceLocation, RawDiagnostic, Finding, provenance enums
│   │   └── report.py               # ScanMetadata, ScanReport, ModuleNode, ModuleEdge
│   ├── engines/
│   │   ├── base.py                 # AnalysisEngine protocol and shared timeout/result helpers
│   │   ├── pyslang_engine.py       # In-process PySlang adapter and module extraction
│   │   ├── verilator_engine.py     # Safe Verilator process invocation
│   │   └── sarif.py                # SARIF-to-RawDiagnostic parser
│   ├── diagnostics/
│   │   ├── canonical.py            # Engine rule mapping and severity policy
│   │   ├── merge.py                # Fingerprinting, merging, provenance retention
│   │   └── baseline.py             # New/existing/resolved comparison
│   ├── analysis/
│   │   ├── module_graph.py          # Deterministic module relationships
│   │   └── trends.py                # New, unchanged, and resolved summaries
│   ├── knowledge/
│   │   ├── schema.py               # ExplanationEntry schema
│   │   ├── store.py                # Safe data loading and lookup
│   │   └── rules/*.yaml            # One reviewed canonical explanation per file
│   ├── renderers/
│   │   ├── terminal.py             # Rich terminal summary
│   │   ├── json_report.py          # Stable JSON writer
│   │   ├── html_report.py          # Jinja rendering and self-contained output
│   │   └── assets/                 # HTML template, CSS, and minimal JavaScript
│   ├── security/
│   │   ├── paths.py                 # Output and symlink boundaries
│   │   └── redaction.py             # Shareable-report path and secret redaction
│   └── services/
│       ├── scan.py                 # Orchestration, policy evaluation, report assembly
│       └── doctor.py               # Read-only environment inspection
├── tests/
│   ├── unit/                       # Fast model, config, discovery, merge, renderer tests
│   ├── contract/                   # Shared engine-adapter contract tests
│   ├── e2e/                        # CLI and complete scan tests
│   ├── security/                   # Adversarial path, process, and HTML tests
│   ├── automation/                 # CI, Action, container, and release contracts
│   └── fixtures/                   # Minimal RTL projects, SARIF, baselines, report samples
├── docs/
│   ├── configuration.md            # Complete `.rtl-lens.toml` reference
│   ├── rules/                      # Generated bilingual rule reference
│   ├── contributing-rules.md       # Explanation and fixture contribution guide
│   ├── beta/                       # Compatibility matrix and anonymized feedback log
│   └── superpowers/                # Approved specification and implementation plan
└── .github/
    ├── workflows/                  # CI, container, docs/report, release checks
    ├── ISSUE_TEMPLATE/             # Bug, false-positive, and rule-request forms
    ├── PULL_REQUEST_TEMPLATE.md    # Verification checklist
    └── dependabot.yml              # Dependency update policy
```

---

### Task 1: Package foundation and versioned domain models

**Week checkpoint:** Week 1 begins.

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `src/rtl_lens/__init__.py`
- Create: `src/rtl_lens/models/project.py`
- Create: `src/rtl_lens/models/engine.py`
- Create: `src/rtl_lens/models/diagnostic.py`
- Create: `src/rtl_lens/models/report.py`
- Create: `tests/unit/test_models.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: none.
- Produces: `ProjectConfig`, `ResolvedProject`, `EngineMode`, `EngineState`, `EngineRequest`, `EngineFailure`, `EngineRun`, `Severity`, `BaselineState`, `SourceLocation`, `RawDiagnostic`, `Finding`, `ScanMetadata`, and `ScanReport`.

- [ ] **Step 1: Write model validation tests**

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rtl_lens.models.diagnostic import Finding, Severity, SourceLocation
from rtl_lens.models.project import ResolvedProject
from rtl_lens.models.report import ScanMetadata, ScanReport


def test_resolved_project_rejects_sources_outside_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.sv"
    with pytest.raises(ValidationError):
        ResolvedProject(root=tmp_path, sources=(outside,))


def test_scan_report_round_trips_json(tmp_path: Path) -> None:
    source = tmp_path / "top.sv"
    report = ScanReport(
        schema_version="1.0",
        metadata=ScanMetadata(
            project_root=".",
            started_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            duration_ms=12,
            requested_engines=("pyslang",),
            completed_engines=("pyslang",),
            config_digest="0" * 64,
            redacted=False,
        ),
        findings=(
            Finding(
                fingerprint="1" * 64,
                canonical_rule="width-mismatch",
                severity=Severity.ERROR,
                location=SourceLocation(path="top.sv", line=3, column=9),
                title="Assignment width mismatch",
                explanation_id=None,
                provenance=(),
            ),
        ),
    )
    assert ScanReport.model_validate_json(report.model_dump_json()) == report
```

- [ ] **Step 2: Run the model tests and verify collection fails**

Run: `uv run pytest tests/unit/test_models.py -v`

Expected: FAIL during import because `rtl_lens.models` does not exist.

- [ ] **Step 3: Create package metadata and exact model skeletons**

Use this `pyproject.toml` dependency and entry-point core:

```toml
[project]
name = "rtl-lens"
version = "0.1.0.dev0"
description = "Explainable dual-engine diagnostics for Verilog and SystemVerilog projects"
readme = "README.md"
requires-python = ">=3.11,<3.14"
license = "Apache-2.0"
dependencies = [
  "jinja2>=3.1,<4",
  "pydantic>=2.11,<3",
  "pyslang>=11,<12",
  "pyyaml>=6,<7",
  "rich>=13,<15",
  "typer>=0.16,<1",
]

[project.scripts]
rtl-lens = "rtl_lens.cli:app"

[dependency-groups]
dev = [
  "beautifulsoup4>=4.13,<5",
  "mypy>=1.17,<2",
  "playwright>=1.54,<2",
  "pytest>=8.4,<9",
  "pytest-cov>=6.2,<7",
  "ruff>=0.12,<1",
  "types-pyyaml>=6.0,<7",
]

[build-system]
requires = ["uv_build>=0.11.32,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
packages = ["rtl_lens"]
```

Implement immutable Pydantic models with `ConfigDict(frozen=True)`. Validate every `ResolvedProject.sources` entry with `Path.resolve().is_relative_to(root.resolve())`. Use string enums for every serialized state and tuples rather than mutable lists in the domain layer.

- [ ] **Step 4: Lock dependencies and run the targeted test**

Run: `uv lock`

Expected: `uv.lock` is created with Python 3.11–3.13 compatible resolutions.

Run: `uv run pytest tests/unit/test_models.py -v`

Expected: PASS.

- [ ] **Step 5: Run foundation quality checks**

Run: `uv run ruff check src tests`

Run: `uv run mypy src`

Expected: both commands exit `0`.

- [ ] **Step 6: Commit the foundation**

```bash
git add pyproject.toml uv.lock .python-version .gitignore src/rtl_lens tests/unit/test_models.py
git commit -m "feat: establish versioned RTL Lens domain models"
```

### Task 2: Configuration loading and deterministic project discovery

**Files:**
- Create: `src/rtl_lens/config.py`
- Create: `src/rtl_lens/project.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/unit/test_project.py`
- Create: `tests/fixtures/projects/basic/rtl/top.sv`
- Create: `tests/fixtures/projects/basic/rtl/child.v`

**Interfaces:**
- Consumes: `ProjectConfig` and `ResolvedProject` from Task 1.
- Produces: `load_config(root: Path, overrides: dict[str, object] | None = None) -> ProjectConfig`, `config_digest(config: ProjectConfig) -> str`, and `resolve_project(root: Path, config: ProjectConfig) -> ResolvedProject`.

- [ ] **Step 1: Write failing precedence, digest, and discovery tests**

```python
def test_cli_override_wins_over_toml(tmp_path: Path) -> None:
    (tmp_path / ".rtl-lens.toml").write_text(
        '[scan]\nlanguage = "en"\nsource_roots = ["rtl"]\n', encoding="utf-8"
    )
    config = load_config(tmp_path, {"scan.language": "zh-CN"})
    assert config.scan.language == "zh-CN"


def test_discovery_is_sorted_and_repository_relative(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "z.sv").write_text("module z; endmodule", encoding="utf-8")
    (rtl / "a.v").write_text("module a; endmodule", encoding="utf-8")
    project = resolve_project(tmp_path, ProjectConfig())
    assert [path.name for path in project.sources] == ["a.v", "z.sv"]
```

- [ ] **Step 2: Run tests and verify missing functions fail**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_project.py -v`

Expected: FAIL because `load_config` and `resolve_project` are undefined.

- [ ] **Step 3: Implement safe TOML loading and source discovery**

Use `tomllib.loads()`, reject unknown keys through Pydantic `extra="forbid"`, apply dotted CLI overrides through an explicit allowlist, serialize the effective config with sorted JSON, and compute SHA-256. Discovery must include `.v` and `.sv`, ignore `.git`, `.venv`, configured output directories, and symlinks resolving outside the repository root.

```python
SUPPORTED_SUFFIXES = {".v", ".sv"}
IGNORED_DIRS = {".git", ".venv", ".rtl-lens"}


def config_digest(config: ProjectConfig) -> str:
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run targeted tests**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_project.py -v`

Expected: PASS, including a test for a Unicode path and a symlink escaping the root.

- [ ] **Step 5: Run the affected suite and commit**

Run: `uv run pytest tests/unit -v`

```bash
git add src/rtl_lens/config.py src/rtl_lens/project.py tests/unit/test_config.py tests/unit/test_project.py tests/fixtures/projects/basic
git commit -m "feat: resolve RTL projects from strict configuration"
```

### Task 3: Engine protocol and PySlang adapter

**Files:**
- Create: `src/rtl_lens/engines/__init__.py`
- Create: `src/rtl_lens/engines/base.py`
- Create: `src/rtl_lens/engines/pyslang_engine.py`
- Create: `tests/contract/test_engine_contract.py`
- Create: `tests/unit/test_pyslang_engine.py`
- Create: `tests/fixtures/projects/pyslang_error/top.sv`

**Interfaces:**
- Consumes: `EngineRequest`, `EngineRun`, `RawDiagnostic`, and `ResolvedProject`.
- Produces: `AnalysisEngine` protocol with `name: str`, `version() -> str`, `available() -> bool`, and `run(request: EngineRequest) -> EngineRun`; concrete `PySlangEngine`.

- [ ] **Step 1: Write the shared contract and PySlang diagnostic test**

```python
def test_pyslang_engine_returns_structured_diagnostic(tmp_path: Path) -> None:
    source = tmp_path / "top.sv"
    source.write_text("module top; assign missing = 1'b1; endmodule", encoding="utf-8")
    project = ResolvedProject(root=tmp_path, sources=(source,))
    result = PySlangEngine().run(EngineRequest(project=project, timeout_seconds=10))
    assert result.state is EngineState.COMPLETED
    assert result.engine == "pyslang"
    assert result.diagnostics
    assert result.diagnostics[0].location.path == "top.sv"
    assert result.diagnostics[0].original_code
```

- [ ] **Step 2: Run the adapter test and verify it fails**

Run: `uv run pytest tests/unit/test_pyslang_engine.py -v`

Expected: FAIL because `PySlangEngine` does not exist.

- [ ] **Step 3: Implement PySlang through supported APIs**

Construct each syntax tree with `SyntaxTree.fromFile(str(path))`, add it to `Compilation`, call `getAllDiagnostics()`, and use `DiagnosticEngine(compilation.sourceManager)` to format diagnostic arguments. Convert source locations to repository-relative `SourceLocation` values. Catch Python exceptions at the adapter boundary and return `EngineState.FAILED` with a bounded `EngineFailure`; never allow adapter exceptions to escape into renderers.

```python
compilation = Compilation()
for source in request.project.sources:
    compilation.addSyntaxTree(SyntaxTree.fromFile(str(source)))
diagnostic_engine = DiagnosticEngine(compilation.sourceManager)
diagnostics = tuple(compilation.getAllDiagnostics())
```

- [ ] **Step 4: Run the targeted and contract tests**

Run: `uv run pytest tests/unit/test_pyslang_engine.py tests/contract/test_engine_contract.py -v`

Expected: PASS for availability, version reporting, completed runs, and bounded failure results.

- [ ] **Step 5: Run quality checks and commit**

Run: `uv run ruff check src tests`

Run: `uv run mypy src`

```bash
git add src/rtl_lens/engines tests/contract/test_engine_contract.py tests/unit/test_pyslang_engine.py tests/fixtures/projects/pyslang_error
git commit -m "feat: add the native PySlang analysis engine"
```

### Task 4: Safe Verilator execution and SARIF ingestion

**Week checkpoint:** End of Week 2. The package can discover a project and obtain PySlang diagnostics; this task completes the dual-engine foundation.

**Files:**
- Create: `src/rtl_lens/engines/verilator_engine.py`
- Create: `src/rtl_lens/engines/sarif.py`
- Create: `tests/unit/test_sarif.py`
- Create: `tests/unit/test_verilator_engine.py`
- Create: `tests/fixtures/sarif/verilator-width.sarif.json`
- Create: `tests/fixtures/bin/fake_verilator.py`

**Interfaces:**
- Consumes: `AnalysisEngine`, `EngineRequest`, `EngineRun`, and `RawDiagnostic`.
- Produces: `parse_verilator_sarif(payload: Mapping[str, object], root: Path) -> tuple[RawDiagnostic, ...]` and `VerilatorEngine(executable: Path | None = None)`.

- [ ] **Step 1: Write failing SARIF and subprocess-safety tests**

```python
def test_parse_verilator_width_sarif(fixture_dir: Path, tmp_path: Path) -> None:
    payload = json.loads((fixture_dir / "sarif/verilator-width.sarif.json").read_text())
    diagnostics = parse_verilator_sarif(payload, tmp_path)
    assert diagnostics[0].original_code == "WIDTH"
    assert diagnostics[0].location == SourceLocation(path="rtl/top.sv", line=8, column=5)


def test_verilator_arguments_do_not_use_shell(monkeypatch: pytest.MonkeyPatch, project) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append(kwargs) or fake_ok())
    VerilatorEngine(Path("verilator")).run(EngineRequest(project=project, timeout_seconds=3))
    assert calls[0]["shell"] is False
    assert calls[0]["timeout"] == 3
```

- [ ] **Step 2: Run tests and verify missing parser/adapter failures**

Run: `uv run pytest tests/unit/test_sarif.py tests/unit/test_verilator_engine.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement exact Verilator invocation and SARIF parsing**

Invoke:

```python
args = [
    str(executable),
    "--lint-only",
    "--diagnostics-sarif-output",
    str(sarif_path),
    "--Wall",
    *define_args,
    *include_args,
    *source_args,
]
completed = subprocess.run(
    args,
    cwd=request.project.root,
    capture_output=True,
    text=True,
    timeout=request.timeout_seconds,
    shell=False,
    check=False,
)
```

Treat exit codes with valid SARIF as completed analysis even when findings are errors. Treat timeout, missing executable, malformed SARIF, or output exceeding the configured bound as `EngineState.FAILED`. Normalize SARIF paths only after verifying they resolve under the project root.

- [ ] **Step 4: Run tests including malicious paths and timeout**

Run: `uv run pytest tests/unit/test_sarif.py tests/unit/test_verilator_engine.py tests/contract/test_engine_contract.py -v`

Expected: PASS; a filename containing spaces and shell metacharacters remains a single argument.

- [ ] **Step 5: Commit the Verilator adapter**

```bash
git add src/rtl_lens/engines/verilator_engine.py src/rtl_lens/engines/sarif.py tests/unit/test_sarif.py tests/unit/test_verilator_engine.py tests/fixtures/sarif tests/fixtures/bin
git commit -m "feat: ingest Verilator diagnostics through SARIF"
```

### Task 5: Canonical mapping, fingerprinting, merge, and baselines

**Files:**
- Create: `src/rtl_lens/diagnostics/__init__.py`
- Create: `src/rtl_lens/diagnostics/canonical.py`
- Create: `src/rtl_lens/diagnostics/merge.py`
- Create: `src/rtl_lens/diagnostics/baseline.py`
- Create: `tests/unit/test_canonical.py`
- Create: `tests/unit/test_merge.py`
- Create: `tests/unit/test_baseline.py`

**Interfaces:**
- Consumes: tuples of `RawDiagnostic` from any engine.
- Produces: `canonicalize(raw: RawDiagnostic) -> Finding`, `fingerprint(finding: Finding) -> str`, `merge_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]`, `compare_baseline(current: tuple[Finding, ...], previous: ScanReport | None) -> BaselineComparison`.

- [ ] **Step 1: Write failing deterministic merge tests**

```python
def test_two_engines_merge_same_width_issue() -> None:
    slang = raw("pyslang", "WidthTruncate", "rtl/alu.sv", 42, 9)
    verilator = raw("verilator", "WIDTH", "rtl/alu.sv", 42, 9)
    merged = merge_findings([canonicalize(slang), canonicalize(verilator)])
    assert len(merged) == 1
    assert merged[0].canonical_rule == "width-mismatch"
    assert {p.engine for p in merged[0].provenance} == {"pyslang", "verilator"}


def test_message_wording_does_not_change_known_rule_fingerprint() -> None:
    first = canonicalize(raw("verilator", "WIDTH", "rtl/alu.sv", 42, 9, "old wording"))
    second = canonicalize(raw("verilator", "WIDTH", "rtl/alu.sv", 42, 9, "new wording"))
    assert fingerprint(first) == fingerprint(second)
```

- [ ] **Step 2: Run tests and verify missing diagnostic services fail**

Run: `uv run pytest tests/unit/test_canonical.py tests/unit/test_merge.py tests/unit/test_baseline.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement documented deterministic rules**

Start the reviewed mapping with these exact engine pairs:

```python
ENGINE_RULES = {
    ("verilator", "WIDTH"): "width-mismatch",
    ("verilator", "LATCH"): "incomplete-assignment",
    ("verilator", "CASEINCOMPLETE"): "case-incomplete",
    ("verilator", "CASEOVERLAP"): "case-overlap",
    ("verilator", "UNUSEDSIGNAL"): "unused-signal",
    ("verilator", "UNDRIVEN"): "undriven-signal",
    ("verilator", "MULTIDRIVEN"): "multiple-drivers",
    ("verilator", "BLKSEQ"): "blocking-in-sequential",
}
```

Add PySlang rule names only after the Task 3 fixtures prove their emitted identifiers. Known-rule fingerprints use canonical rule, normalized path, line, column, and symbol. Unknown-rule fingerprints additionally include the original engine code and normalized message. Baseline output retains resolved fingerprints even though resolved findings do not count against current policy.

- [ ] **Step 4: Run targeted tests and inspect a stable JSON snapshot**

Run: `uv run pytest tests/unit/test_canonical.py tests/unit/test_merge.py tests/unit/test_baseline.py -v`

Expected: PASS with deterministic order by severity, path, line, column, and fingerprint.

- [ ] **Step 5: Commit diagnostic semantics**

```bash
git add src/rtl_lens/diagnostics tests/unit/test_canonical.py tests/unit/test_merge.py tests/unit/test_baseline.py
git commit -m "feat: canonicalize and baseline multi-engine findings"
```

### Task 6: Curated bilingual explanation knowledge base

**Files:**
- Create: `src/rtl_lens/knowledge/__init__.py`
- Create: `src/rtl_lens/knowledge/schema.py`
- Create: `src/rtl_lens/knowledge/store.py`
- Create: `src/rtl_lens/knowledge/rules/width-mismatch.yaml`
- Create: `src/rtl_lens/knowledge/rules/incomplete-assignment.yaml`
- Create: `src/rtl_lens/knowledge/rules/case-incomplete.yaml`
- Create: `src/rtl_lens/knowledge/rules/case-overlap.yaml`
- Create: `src/rtl_lens/knowledge/rules/unused-signal.yaml`
- Create: `src/rtl_lens/knowledge/rules/undriven-signal.yaml`
- Create: `tests/unit/test_knowledge.py`
- Create: `tests/fixtures/knowledge/failing/width-mismatch.sv`
- Create: `tests/fixtures/knowledge/fixed/width-mismatch.sv`

**Interfaces:**
- Consumes: canonical rule identifiers.
- Produces: `ExplanationEntry`, `KnowledgeStore.load_default() -> KnowledgeStore`, and `KnowledgeStore.get(rule_id: str, language: Literal["en", "zh-CN"]) -> LocalizedExplanation | None`.

- [ ] **Step 1: Write failing schema and lookup tests**

```python
def test_every_packaged_rule_has_two_languages_and_examples() -> None:
    store = KnowledgeStore.load_default()
    assert len(store) == 6
    for entry in store.entries:
        assert entry.en.title and entry.zh_cn.title
        assert entry.en.cause and entry.zh_cn.cause
        assert entry.en.risk and entry.zh_cn.risk
        assert entry.en.fix and entry.zh_cn.fix
        assert entry.failing_example.endswith(".sv")
        assert entry.fixed_example.endswith(".sv")
        assert entry.references


def test_unknown_rule_returns_none() -> None:
    assert KnowledgeStore.load_default().get("not-known", "en") is None
```

- [ ] **Step 2: Run tests and verify missing store fails**

Run: `uv run pytest tests/unit/test_knowledge.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement safe data loading and six complete entries**

Load with `yaml.safe_load`, validate with Pydantic `extra="forbid"`, reject duplicate rule IDs, and resolve example paths only under `tests/fixtures/knowledge`. Use this exact record shape:

```yaml
schema_version: "1.0"
rule_id: width-mismatch
severity: error
en:
  title: Assignment width mismatch
  cause: The source and destination widths differ, so the assignment extends or truncates bits.
  risk: Silent truncation can change numeric results without stopping synthesis or simulation.
  fix: Make both widths agree, or use an explicit slice or cast to document intentional conversion.
zh-CN:
  title: 赋值两侧位宽不一致
  cause: 源信号与目标信号位宽不同，赋值时会发生扩展或截断。
  risk: 静默截断可能改变数值结果，但综合或仿真不一定停止。
  fix: 统一两侧位宽；若转换是有意的，请使用明确的位选或类型转换。
failing_example: failing/width-mismatch.sv
fixed_example: fixed/width-mismatch.sv
references:
  - https://verilator.org/guide/latest/warnings.html#width
review_status: reviewed
```

- [ ] **Step 4: Run lookup, schema, and fixture tests**

Run: `uv run pytest tests/unit/test_knowledge.py -v`

Expected: PASS; malformed YAML, duplicate IDs, missing translation fields, and path traversal all fail validation.

- [ ] **Step 5: Commit the knowledge-base foundation**

```bash
git add src/rtl_lens/knowledge tests/unit/test_knowledge.py tests/fixtures/knowledge
git commit -m "feat: add reviewed bilingual diagnostic explanations"
```

### Task 7: Scan orchestration, policy evaluation, and exit semantics

**Files:**
- Create: `src/rtl_lens/services/__init__.py`
- Create: `src/rtl_lens/services/scan.py`
- Create: `tests/unit/test_scan_service.py`
- Create: `tests/e2e/test_partial_scan.py`

**Interfaces:**
- Consumes: `ResolvedProject`, `ProjectConfig`, `AnalysisEngine` instances, diagnostic services, and `KnowledgeStore`.
- Produces: `ScanService.scan(project: ResolvedProject, config: ProjectConfig) -> ScanOutcome`, where `ScanOutcome` has `report: ScanReport` and `exit_code: int`.

- [ ] **Step 1: Write failing partial-completion and policy tests**

```python
def test_automatic_mode_allows_missing_verilator(clean_project) -> None:
    service = ScanService(engines=(completed_pyslang(), unavailable_verilator()))
    outcome = service.scan(clean_project, config(engine_mode="auto"))
    assert outcome.exit_code == 0
    assert outcome.report.metadata.completed_engines == ("pyslang",)
    assert outcome.report.metadata.scan_state == "partial"


def test_required_verilator_failure_returns_two(clean_project) -> None:
    service = ScanService(engines=(completed_pyslang(), unavailable_verilator()))
    assert service.scan(clean_project, config(engine_mode="required")).exit_code == 2


def test_new_blocking_finding_returns_one(project_with_width_error) -> None:
    outcome = service_with_width_error().scan(project_with_width_error, config())
    assert outcome.exit_code == 1
```

- [ ] **Step 2: Run tests and verify missing service fails**

Run: `uv run pytest tests/unit/test_scan_service.py tests/e2e/test_partial_scan.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement the orchestration pipeline**

Run engines independently, preserve failures, canonicalize, merge, apply the baseline, enrich known rules, redact when configured, assemble `ScanReport`, then evaluate policy. Exit code priority is configuration error `3`, required runtime failure `2`, blocking finding `1`, success `0`. A code finding never becomes an engine failure.

```python
for engine in self.engines:
    if not engine.available():
        runs.append(EngineRun.unavailable(engine.name, required=is_required(engine, config)))
        continue
    runs.append(engine.run(EngineRequest(project=project, timeout_seconds=config.scan.timeout)))
```

- [ ] **Step 4: Run service and partial-scan tests**

Run: `uv run pytest tests/unit/test_scan_service.py tests/e2e/test_partial_scan.py -v`

Expected: PASS for complete, partial, blocking, runtime-failed, and invalid-configuration outcomes.

- [ ] **Step 5: Commit the scan service**

```bash
git add src/rtl_lens/services tests/unit/test_scan_service.py tests/e2e/test_partial_scan.py
git commit -m "feat: orchestrate scans with explicit exit semantics"
```

### Task 8: JSON and terminal report renderers

**Week checkpoint:** End of Week 4. Dual-engine data, merging, explanations, baselines, and policy semantics form a complete non-HTML vertical slice.

**Files:**
- Create: `src/rtl_lens/renderers/__init__.py`
- Create: `src/rtl_lens/renderers/json_report.py`
- Create: `src/rtl_lens/renderers/terminal.py`
- Create: `tests/unit/test_json_report.py`
- Create: `tests/unit/test_terminal_report.py`
- Create: `tests/fixtures/reports/width-report.json`

**Interfaces:**
- Consumes: `ScanReport` only.
- Produces: `write_json_report(report: ScanReport, destination: Path) -> None` and `render_terminal(report: ScanReport, console: Console) -> None`.

- [ ] **Step 1: Write failing stable-schema and no-score tests**

```python
def test_json_report_is_stable_and_atomic(sample_report: ScanReport, tmp_path: Path) -> None:
    destination = tmp_path / "report.json"
    write_json_report(sample_report, destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["findings"][0]["canonical_rule"] == "width-mismatch"
    assert "health_score" not in payload


def test_terminal_marks_partial_scan(sample_partial_report: ScanReport) -> None:
    console = Console(record=True, width=100)
    render_terminal(sample_partial_report, console)
    output = console.export_text()
    assert "partial" in output.lower()
    assert "Verilator" in output
```

- [ ] **Step 2: Run tests and verify renderer imports fail**

Run: `uv run pytest tests/unit/test_json_report.py tests/unit/test_terminal_report.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement atomic JSON and accessible terminal output**

Write JSON to a sibling temporary file, flush and replace the destination atomically. Terminal output must use text labels in addition to color, show scan completeness, counts, new findings, unexplained diagnostics, engine failures, and output paths. It must never print an overall score.

```python
temporary = destination.with_suffix(destination.suffix + ".tmp")
temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
temporary.replace(destination)
```

- [ ] **Step 4: Run renderer tests at color and no-color settings**

Run: `uv run pytest tests/unit/test_json_report.py tests/unit/test_terminal_report.py -v`

Expected: PASS with `Console(color_system=None)` and the default test console.

- [ ] **Step 5: Commit non-HTML rendering**

```bash
git add src/rtl_lens/renderers tests/unit/test_json_report.py tests/unit/test_terminal_report.py tests/fixtures/reports
git commit -m "feat: render stable JSON and terminal reports"
```

### Task 9: Self-contained HTML report

**Files:**
- Create: `src/rtl_lens/renderers/html_report.py`
- Create: `src/rtl_lens/renderers/assets/report.html.j2`
- Create: `src/rtl_lens/renderers/assets/report.css`
- Create: `src/rtl_lens/renderers/assets/report.js`
- Create: `tests/unit/test_html_report.py`
- Create: `tests/browser/test_html_report.py`
- Create: `tests/fixtures/reports/partial-report.json`

**Interfaces:**
- Consumes: `ScanReport` and a destination path.
- Produces: `write_html_report(report: ScanReport, destination: Path) -> None`.
- Security boundary: all diagnostic text, paths, snippets, and explanations are untrusted input and must be escaped before insertion into HTML.

- [ ] **Step 1: Write failing structure, escaping, and no-score tests**

```python
def test_html_report_is_self_contained_and_escapes_input(
    sample_report: ScanReport, tmp_path: Path
) -> None:
    sample_report.findings[0].message = '<script>alert("x")</script>'
    destination = tmp_path / "report.html"
    write_html_report(sample_report, destination)
    html = destination.read_text(encoding="utf-8")
    document = BeautifulSoup(html, "html.parser")
    assert document.select_one("[data-testid='summary']")
    assert document.select_one("[data-testid='finding-row']")
    assert not document.find("script", src=True)
    assert "&lt;script&gt;" in html
    assert "health score" not in document.get_text(" ").lower()
```

- [ ] **Step 2: Run the HTML unit test and verify the renderer is missing**

Run: `uv run pytest tests/unit/test_html_report.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement a single-file, responsive report**

Embed CSS and the small filtering script directly in the generated file. Include scan completeness, engine status, summary counts, filters, finding detail, bilingual explanations, baseline state, and unknown raw diagnostics. Use Jinja auto-escaping and serialize filter data with Jinja's JSON encoder rather than string concatenation.

```python
environment = Environment(
    loader=PackageLoader("rtl_lens", "renderers/assets"),
    autoescape=select_autoescape(enabled_extensions=("html", "j2"), default=True),
)
html = environment.get_template("report.html.j2").render(report=report.model_dump())
```

- [ ] **Step 4: Add a browser test for keyboard use and narrow screens**

```python
def test_report_filters_without_network_requests(page: Page, html_report: Path) -> None:
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    page.goto(html_report.as_uri())
    page.get_by_role("combobox", name="Severity").select_option("warning")
    expect(page.locator("[data-testid='finding-row']:visible")).to_have_count(1)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("main")).to_be_visible()
    assert all(url.startswith("file:") for url in requests)
```

- [ ] **Step 5: Run HTML unit and browser tests**

Run: `uv run playwright install chromium`

Run: `uv run pytest tests/unit/test_html_report.py tests/browser/test_html_report.py -v`

Expected: PASS; report opens from `file://`, remains usable at 390 px width, and makes no HTTP request.

- [ ] **Step 6: Commit the HTML report**

```bash
git add src/rtl_lens/renderers/html_report.py src/rtl_lens/renderers/assets tests/unit/test_html_report.py tests/browser/test_html_report.py tests/fixtures/reports/partial-report.json
git commit -m "feat: generate self-contained HTML reports"
```

### Task 10: Public CLI commands and end-to-end exit codes

**Week checkpoint:** End of Week 5. A user can install the package, initialize a project, scan it, inspect the environment, explain a rule, and obtain terminal, JSON, and HTML output.

**Files:**
- Create: `src/rtl_lens/cli.py`
- Create: `src/rtl_lens/version.py`
- Create: `tests/unit/test_cli_init.py`
- Create: `tests/unit/test_cli_doctor.py`
- Create: `tests/unit/test_cli_explain.py`
- Create: `tests/e2e/test_cli_scan.py`
- Create: `tests/e2e/test_cli_exit_codes.py`

**Interfaces:**
- Commands: `rtl-lens scan`, `rtl-lens init`, `rtl-lens doctor`, `rtl-lens explain RULE`, and `rtl-lens version`.
- Exit contract: `0` policy passed, `1` findings violate policy, `2` a required engine or runtime failure prevented requested completeness, and `3` invalid project or RTL Lens configuration. Report-writing failure is a runtime failure and returns `2`. A permitted partial scan uses `0` or `1` according to policy and displays a completeness warning.

- [ ] **Step 1: Write failing command and help tests**

```python
def test_help_lists_the_public_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("scan", "init", "doctor", "explain", "version"):
        assert command in result.stdout


@pytest.mark.parametrize(
    ("fixture", "arguments", "expected"),
    [
        ("clean", ["scan", "."], 0),
        ("width_mismatch", ["scan", ".", "--fail-on", "warning"], 1),
        ("required_engine_missing", ["scan", "."], 2),
        ("invalid_config", ["scan", "."], 3),
    ],
)
def test_scan_exit_contract(fixture: str, arguments: list[str], expected: int) -> None:
    result = run_fixture_cli(fixture, arguments)
    assert result.exit_code == expected
```

- [ ] **Step 2: Run CLI tests and verify command imports fail**

Run: `uv run pytest tests/unit/test_cli_init.py tests/unit/test_cli_doctor.py tests/unit/test_cli_explain.py tests/e2e/test_cli_scan.py tests/e2e/test_cli_exit_codes.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement thin commands over application services**

Keep parsing and presentation in `cli.py`; project discovery, scanning, explanations, and rendering stay in their existing modules. `init` refuses to overwrite an existing configuration unless `--force` is present. `doctor` reports PySlang, Verilator, configuration, output-directory, and container availability as separate checks.

```python
@app.command()
def scan(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    config: Annotated[Path | None, typer.Option("--config")] = None,
    fail_on: Annotated[Severity | None, typer.Option("--fail-on")] = None,
) -> None:
    outcome = scan_project(path=path, config_path=config, fail_on=fail_on)
    render_terminal(outcome.report, console)
    raise typer.Exit(outcome.exit_code)
```

- [ ] **Step 4: Run CLI tests and package-entry smoke tests**

Run: `uv run pytest tests/unit/test_cli_init.py tests/unit/test_cli_doctor.py tests/unit/test_cli_explain.py tests/e2e/test_cli_scan.py tests/e2e/test_cli_exit_codes.py -v`

Run: `uv run rtl-lens --help`

Run: `uv run rtl-lens version`

Expected: all tests PASS; the installed entry point prints help and the package version.

- [ ] **Step 5: Commit the public CLI**

```bash
git add src/rtl_lens/cli.py src/rtl_lens/version.py tests/unit/test_cli_init.py tests/unit/test_cli_doctor.py tests/unit/test_cli_explain.py tests/e2e/test_cli_scan.py tests/e2e/test_cli_exit_codes.py
git commit -m "feat: expose the RTL Lens command line interface"
```

### Task 11: Module relationships and baseline trend views

**Files:**
- Create: `src/rtl_lens/analysis/module_graph.py`
- Create: `src/rtl_lens/analysis/trends.py`
- Modify: `src/rtl_lens/models/report.py`
- Modify: `src/rtl_lens/renderers/json_report.py`
- Modify: `src/rtl_lens/renderers/html_report.py`
- Modify: `src/rtl_lens/renderers/assets/report.html.j2`
- Create: `tests/unit/test_module_graph.py`
- Create: `tests/unit/test_trends.py`
- Modify: `tests/unit/test_json_report.py`
- Modify: `tests/unit/test_html_report.py`

**Interfaces:**
- Produces: `ModuleGraph(nodes, edges, unresolved)` from PySlang syntax/semantic data and `TrendSummary(new, resolved, unchanged)` from the current report plus baseline.
- Degradation rule: graph extraction failure adds an analysis warning but never discards diagnostics or changes engine completeness.

- [ ] **Step 1: Write failing graph and trend tests**

```python
def test_module_graph_records_instances_and_unresolved_modules() -> None:
    graph = build_module_graph(project_fixture("hierarchy"))
    assert ("top", "alu") in graph.edges
    assert "missing_ip" in graph.unresolved


def test_trend_summary_partitions_current_and_baseline_findings() -> None:
    summary = compare_with_baseline(current_fingerprints={"a", "b"}, baseline={"b", "c"})
    assert summary.new == {"a"}
    assert summary.unchanged == {"b"}
    assert summary.resolved == {"c"}
```

- [ ] **Step 2: Run focused tests and verify the analysis modules are missing**

Run: `uv run pytest tests/unit/test_module_graph.py tests/unit/test_trends.py -v`

Expected: FAIL during import.

- [ ] **Step 3: Implement deterministic graph and trend models**

Sort nodes and edges before serialization, preserve unresolved module names, and cap the interactive graph at the configured display limit while retaining all graph data in JSON. Render text counts and a relationship table so the report remains useful without JavaScript or color.

- [ ] **Step 4: Run analysis and renderer regression tests**

Run: `uv run pytest tests/unit/test_module_graph.py tests/unit/test_trends.py tests/unit/test_json_report.py tests/unit/test_html_report.py -v`

Expected: PASS with deterministic snapshots across two repeated runs.

- [ ] **Step 5: Commit graph and trend reporting**

```bash
git add src/rtl_lens/analysis src/rtl_lens/models/report.py src/rtl_lens/renderers tests/unit/test_module_graph.py tests/unit/test_trends.py tests/unit/test_json_report.py tests/unit/test_html_report.py
git commit -m "feat: report module relationships and baseline trends"
```

### Task 12: Expand the curated bilingual knowledge base to 30 rule families

**Week checkpoint:** End of Week 6. Reports cover the agreed 30 high-value diagnostic families while preserving raw unknown diagnostics.

**Files:**
- Modify: `src/rtl_lens/knowledge/rules/*.yaml`
- Modify: `src/rtl_lens/knowledge/schema.py`
- Create: `tests/knowledge/test_rule_catalog.py`
- Create: `tests/knowledge/test_rule_examples.py`
- Create: `tests/fixtures/rules/`
- Create: `docs/rules/index.md`
- Create: `docs/rules/`

**Catalog contract:**
- Exactly these first 30 canonical IDs: `width-mismatch`, `incomplete-assignment`, `case-incomplete`, `case-overlap`, `unused-signal`, `undriven-signal`, `multiple-drivers`, `blocking-in-sequential`, `always-comb-order`, `always-never`, `ascending-range`, `assignment-in-expression`, `assignment-to-input`, `blocking-and-nonblocking`, `case-with-x`, `case-x`, `constant-comparison`, `combinational-delay`, `declaration-filename`, `deprecated-defparam`, `implicit-net`, `port-width-mismatch`, `missing-pin`, `empty-pin-connection`, `signedness-mismatch`, `out-of-range-select`, `duplicate-definition`, `undeclared-identifier`, `unsupported-construct`, and `timescale-mismatch`.
- Every entry contains English and Simplified Chinese title, cause, risk, fix, failing example, corrected example, engine mappings proven by fixtures, and at least one stable primary reference URL.
- If an engine emits a diagnostic that has no proven mapping, retain it as `unknown`; never guess from message text.

- [ ] **Step 1: Write failing catalog completeness tests**

```python
def test_catalog_contains_the_exact_initial_rule_set(rule_catalog: RuleCatalog) -> None:
    assert set(rule_catalog.rules) == EXPECTED_CANONICAL_RULE_IDS


@pytest.mark.parametrize("rule_id", sorted(EXPECTED_CANONICAL_RULE_IDS))
def test_each_rule_is_bilingual_and_has_valid_examples(
    rule_catalog: RuleCatalog, rule_id: str
) -> None:
    rule = rule_catalog.rules[rule_id]
    assert rule.en.title and rule.zh_cn.title
    assert rule.en.cause and rule.zh_cn.cause
    assert rule.en.risk and rule.zh_cn.risk
    assert rule.en.fix and rule.zh_cn.fix
    assert rule.references
    assert fixture_pair("tests/fixtures/knowledge", rule_id).failing.exists()
    assert fixture_pair("tests/fixtures/knowledge", rule_id).fixed.exists()
```

- [ ] **Step 2: Run catalog tests and verify the six-rule seed is insufficient**

Run: `uv run pytest tests/knowledge/test_rule_catalog.py -v`

Expected: FAIL because 24 required families and their fixtures are absent.

- [ ] **Step 3: Add four reviewed batches of six families**

For each batch, add YAML content under `src/rtl_lens/knowledge/rules`, matching fixtures under `tests/fixtures/knowledge/failing` and `tests/fixtures/knowledge/fixed`, documentation generated from the same typed catalog, and exact PySlang or Verilator code mappings observed from the failing fixture. Run the catalog and example tests after each batch so no unreviewed bulk text enters the repository.

Run after each batch: `uv run pytest tests/knowledge/test_rule_catalog.py tests/knowledge/test_rule_examples.py -v`

Expected: the number of missing families decreases by six and reaches zero after batch four; every corrected fixture removes the target diagnostic.

- [ ] **Step 4: Validate all catalog mappings against both available engines**

Run: `uv run pytest tests/knowledge tests/integration/test_pyslang_engine.py tests/integration/test_verilator_engine.py -v`

Expected: PASS when Verilator is installed; otherwise Verilator-dependent cases are explicitly skipped and CI container coverage remains required before release.

- [ ] **Step 5: Commit the reviewed catalog**

```bash
git add src/rtl_lens/knowledge tests/knowledge tests/fixtures/rules docs/rules
git commit -m "feat: curate thirty bilingual RTL diagnostic guides"
```

### Task 13: Security, privacy, and bounded-resource hardening

**Files:**
- Create: `src/rtl_lens/security/paths.py`
- Create: `src/rtl_lens/security/redaction.py`
- Modify: `src/rtl_lens/engines/verilator.py`
- Modify: `src/rtl_lens/renderers/html_report.py`
- Modify: `src/rtl_lens/renderers/json_report.py`
- Create: `tests/security/test_html_injection.py`
- Create: `tests/security/test_path_boundaries.py`
- Create: `tests/security/test_subprocess_safety.py`
- Create: `tests/security/test_redaction.py`
- Create: `tests/performance/test_large_report.py`

**Security contract:**
- Invoke tools with argument arrays and `shell=False`; enforce timeout and maximum captured output.
- Resolve report and baseline destinations beneath the configured output root unless the user supplies an explicit absolute destination.
- Do not follow project symlinks outside the project root by default.
- Redact user-home prefixes, environment values marked secret, and configured path prefixes in shareable reports; keep source files local and never transmit telemetry.

- [ ] **Step 1: Write failing adversarial tests**

```python
def test_verilator_arguments_are_never_executed_by_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: observed.update(kwargs) or completed())
    run_verilator([Path("rtl;whoami.sv")], timeout_seconds=30)
    assert observed["shell"] is False


def test_shareable_report_redacts_home_and_escapes_markup(sample_report: ScanReport) -> None:
    sample_report.findings[0].message = r"C:\\Users\\alice\\secret\\<img src=x onerror=alert(1)>"
    rendered = render_shareable_html(sample_report, home=Path(r"C:\\Users\\alice"))
    document = BeautifulSoup(rendered, "html.parser")
    assert "alice" not in rendered
    assert document.find("img") is None
```

- [ ] **Step 2: Run security and performance tests and record the failures**

Run: `uv run pytest tests/security tests/performance/test_large_report.py -v`

Expected: FAIL until path boundaries, redaction, output limits, and the performance ceiling exist.

- [ ] **Step 3: Implement bounded execution and shareable-output redaction**

Use a streaming temporary file or bounded reader for tool output, terminate timed-out processes, add a visible truncation marker, and distinguish timeout from executable-not-found. Render 500 diagnostics to JSON and HTML within 5 seconds on the CI reference runner; keep this as a regression ceiling, not a benchmark claim.

- [ ] **Step 4: Run security, performance, and full regression tests**

Run: `uv run pytest tests/security tests/performance/test_large_report.py -v`

Run: `uv run pytest -q`

Expected: PASS with no external network request and no path, HTML, or shell injection.

- [ ] **Step 5: Commit hardening**

```bash
git add src/rtl_lens/security src/rtl_lens/engines/verilator.py src/rtl_lens/renderers tests/security tests/performance
git commit -m "fix: harden local scans and shareable reports"
```

### Task 14: Cross-platform CI, pinned container, and reusable GitHub Action

**Week checkpoint:** End of Week 7. Every supported platform verifies the PySlang path, while Linux container jobs verify the pinned Verilator path and packaging artifacts.

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/action-smoke.yml`
- Create: `.github/dependabot.yml`
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `action.yml`
- Create: `scripts/action-entrypoint.sh`
- Create: `tests/action/fixture/clean.sv`
- Create: `tests/action/fixture/width_mismatch.sv`
- Create: `tests/automation/test_ci_contract.py`
- Create: `tests/automation/test_action_contract.py`
- Create: `tests/automation/test_container_contract.py`
- Modify: `pyproject.toml`
- Create: `uv.lock`

**Automation contract:**
- CI matrix: Ubuntu, Windows, and macOS on Python 3.11, 3.12, and 3.13 for PySlang; one Ubuntu container job for the pinned Verilator release.
- Workflow permissions are `contents: read`; no token is persisted into the analyzer container.
- The Action is read-only by default. JSON/HTML artifact upload occurs only when the caller sets `upload-report: "true"`.
- Docker build arguments and labels record the exact Verilator version; no `latest` tag appears in configuration.

- [ ] **Step 1: Add failing configuration-contract tests**

```python
def test_ci_has_read_only_permissions_and_supported_matrix() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]["test"]["strategy"]["matrix"]["python-version"]) == {
        "3.11", "3.12", "3.13"
    }


def test_action_upload_is_opt_in() -> None:
    action = yaml.safe_load(Path("action.yml").read_text())
    assert action["inputs"]["upload-report"]["default"] == "false"
```

- [ ] **Step 2: Run automation tests and verify files are absent**

Run: `uv run pytest tests/automation -v`

Expected: FAIL because CI, container, and Action metadata do not exist.

- [ ] **Step 3: Implement CI, lockfile, container, and Action**

Generate and validate the lockfile with `uv lock`. Build one deterministic package artifact with `uv build`. Implement `action.yml` as a composite Action: one step runs the pinned container and the second conditionally invokes the pinned major release of `actions/upload-artifact` only when `upload-report == "true"`. It calls the same public CLI used locally and exposes project path, configuration path, fail threshold, report format, and upload opt-in as inputs.

- [ ] **Step 4: Run local equivalents of all CI gates**

Run: `uv lock --check`

Run: `uv run ruff check .`

Run: `uv run ruff format --check .`

Run: `uv run mypy src`

Run: `uv run pytest --cov=rtl_lens --cov-report=term-missing --cov-fail-under=90`

Run: `uv build`

Run: `docker build --build-arg VERILATOR_VERSION=5.040 -t rtl-lens:ci .`

Run: `docker run --rm -v "${PWD}:/workspace" rtl-lens:ci scan /workspace/tests/action/fixture --format json`

Expected: every command exits `0`; the container report records Verilator `5.040`. If that exact release is unavailable when execution begins, update the pin once in the design record and all automation files before implementation, never by floating the version.

- [ ] **Step 5: Commit reproducible automation**

```bash
git add .github Dockerfile .dockerignore action.yml scripts/action-entrypoint.sh tests/action pyproject.toml uv.lock
git commit -m "ci: verify platforms and package the analyzer action"
```

### Task 15: Documentation, governance, and release checks

**Files:**
- Create: `README.md`
- Create: `README.zh-CN.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`
- Create: `CHANGELOG.md`
- Create: `LICENSE`
- Create: `docs/getting-started.md`
- Create: `docs/configuration.md`
- Create: `docs/architecture.md`
- Create: `docs/privacy.md`
- Create: `docs/maintenance.md`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/feature.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/workflows/release-check.yml`
- Create: `tests/docs/test_documentation.py`
- Create: `tests/automation/test_release_workflow.py`

**Documentation contract:**
- English is the canonical README; Chinese mirrors all installation, quick-start, privacy, limitation, and contribution claims.
- Every public command and configuration example is exercised by a test fixture.
- Release workflow builds and verifies artifacts only. Uploading to GitHub Releases, PyPI, a registry, or Marketplace remains absent until the user separately approves publication.

- [ ] **Step 1: Write failing documentation and workflow policy tests**

```python
def test_readmes_include_install_scan_privacy_and_limitations() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = Path(name).read_text(encoding="utf-8").lower()
        for required in ("install", "rtl-lens scan", "privacy", "limitations"):
            assert required in text


def test_release_check_has_no_publish_step() -> None:
    text = Path(".github/workflows/release-check.yml").read_text(encoding="utf-8")
    assert "uv publish" not in text
    assert "gh release create" not in text
```

- [ ] **Step 2: Run docs tests and verify the public documentation is absent**

Run: `uv run pytest tests/docs/test_documentation.py tests/automation/test_release_workflow.py -v`

Expected: FAIL because the documentation and release-check workflow do not exist.

- [ ] **Step 3: Write bilingual user, contributor, security, and maintenance guides**

Include copy-paste quick starts for PySlang-only and dual-engine scans, a truthful comparison table, example screenshots generated from fixtures, configuration precedence, exit codes, data-handling guarantees, known limitations, rule-contribution instructions, triage labels, monthly dependency cadence, and a 30/60/90-day maintenance routine.

- [ ] **Step 4: Exercise every documented command and check links**

Run: `uv run pytest tests/docs/test_documentation.py tests/automation/test_release_workflow.py -v`

Run: `uv run python -m doctest README.md README.zh-CN.md docs/getting-started.md docs/configuration.md`

Expected: PASS; local links resolve, public commands match the CLI, and no publication command exists.

- [ ] **Step 5: Commit project documentation and governance**

```bash
git add README.md README.zh-CN.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md CHANGELOG.md LICENSE docs .github/ISSUE_TEMPLATE .github/PULL_REQUEST_TEMPLATE.md .github/workflows/release-check.yml tests/docs tests/automation/test_release_workflow.py
git commit -m "docs: prepare RTL Lens for public collaboration"
```

### Task 16: Compatibility evidence, beta feedback, and local release candidate

**Week checkpoint:** End of Week 8. A locally verified release candidate exists with reproducible evidence; publication still requires an explicit user confirmation.

**Files:**
- Create: `compatibility.toml`
- Create: `scripts/scan_compatibility.py`
- Create: `docs/beta/compatibility.md`
- Create: `docs/beta/feedback.md`
- Create: `docs/release-checklist.md`
- Create: `tests/integration/test_compatibility_manifest.py`
- Create: `tests/e2e/test_release_candidate.py`

**Evidence contract:**
- The manifest contains ten permissively licensed public RTL repositories, each pinned to a commit SHA with repository URL, license identifier, intended top files, expected scan completeness, and attribution.
- Compatibility output records tool versions, commit SHA, elapsed time, diagnostic count, unknown count, failures, and redaction state. It reports observations, not unsupported performance claims.
- External beta invitations, GitHub pushes, repository creation, tags on a remote, package uploads, container pushes, Marketplace listing, and promotional posts require separate user approval.

- [ ] **Step 1: Write failing manifest and release-candidate tests**

```python
def test_compatibility_manifest_is_pinned_and_attributed() -> None:
    manifest = load_compatibility_manifest(Path("compatibility.toml"))
    assert len(manifest.projects) == 10
    assert all(re.fullmatch(r"[0-9a-f]{40}", project.commit) for project in manifest.projects)
    assert all(project.license and project.repository.startswith("https://") for project in manifest.projects)


def test_sdist_and_wheel_install_into_clean_environment(built_artifacts: list[Path]) -> None:
    for artifact in built_artifacts:
        environment = create_isolated_environment(artifact)
        result = environment.run("rtl-lens", "scan", clean_fixture_path())
        assert result.returncode == 0
```

- [ ] **Step 2: Run release-candidate tests and verify evidence files are absent**

Run: `uv run pytest tests/integration/test_compatibility_manifest.py tests/e2e/test_release_candidate.py -v`

Expected: FAIL because the pinned manifest and release artifacts do not exist.

- [ ] **Step 3: Select, license-check, and pin the compatibility corpus**

Record ten projects only after verifying their license files and a successful shallow checkout at the exact SHA. Cache checkouts outside the source tree, respect each license, run without modifying upstream contents, and keep generated reports out of Git. If network access is unavailable, the script reports `not-run` and the release checklist remains incomplete.

- [ ] **Step 4: Run compatibility scans and document beta evidence**

Run: `uv run python scripts/scan_compatibility.py --manifest compatibility.toml --output .artifacts/compatibility`

Run: `uv run pytest tests/integration/test_compatibility_manifest.py -v`

Expected: ten machine-readable scan results and a generated aggregate table with no unredacted home paths. Pause for the user to review the corpus and separately approve any outreach to beta testers.

- [ ] **Step 5: Build and verify the local release candidate**

Run: `uv lock --check`

Run: `uv run ruff check .`

Run: `uv run ruff format --check .`

Run: `uv run mypy src`

Run: `uv run pytest --cov=rtl_lens --cov-report=term-missing --cov-fail-under=90`

Run: `uv build`

Run: `uv run pytest tests/e2e/test_release_candidate.py -v`

Expected: all gates PASS and both the wheel and source distribution install and scan the clean fixture in isolated environments.

- [ ] **Step 6: Commit the evidence and stop before publication**

```bash
git add compatibility.toml scripts/scan_compatibility.py docs/beta docs/release-checklist.md tests/integration/test_compatibility_manifest.py tests/e2e/test_release_candidate.py
git commit -m "test: document beta compatibility evidence"
```

Present the local commit, test evidence, package contents, known limitations, and release checklist to the user. Do not create a remote tag or publish any artifact until the user gives explicit approval.

## Execution Order and Checkpoints

| Week | Tasks | Demonstrable outcome |
|---|---:|---|
| 1 | 1–2 | Installable typed package, configuration, and deterministic source discovery |
| 2 | 3–4 | PySlang and Verilator adapters with honest partial-scan behavior |
| 3 | 5–6 | Stable merging, baselines, and six deeply reviewed bilingual rules |
| 4 | 7–8 | Complete non-HTML scan path with terminal and JSON reports |
| 5 | 9–10 | Self-contained HTML report and full public CLI |
| 6 | 11–12 | Module/trend views and the exact 30-rule catalog |
| 7 | 13–14 | Security hardening, cross-platform CI, container, and Action |
| 8 | 15–16 | Public-project documentation, compatibility evidence, and a local release candidate |

After each week checkpoint, run the focused tests listed in its tasks plus `uv run pytest -q`, demonstrate the resulting user-visible behavior, update `CHANGELOG.md` once it exists, and record scope cuts in `docs/release-checklist.md` once it exists. Core correctness, privacy, raw unknown diagnostics, and dual-engine support cannot be scope-cut; decorative report polish and additional rule families beyond the initial 30 can.

## Specification Coverage Review

| Approved requirement | Implementation evidence |
|---|---|
| Cross-platform default engine plus optional local/pinned Verilator | Tasks 3, 4, and 14 |
| Terminal, stable JSON, and self-contained HTML | Tasks 8 and 9 |
| Bilingual explanations with raw unknown diagnostics | Tasks 5, 6, and 12 |
| Baseline, new/resolved findings, and module relationships | Tasks 5 and 11 |
| Explicit complete/partial/failed semantics and policy exits | Tasks 7 and 10 |
| Offline operation, privacy, escaping, and no telemetry | Tasks 9, 13, and 15 |
| Reproducible package, container, CI, and opt-in Action upload | Task 14 |
| Maintenance, contribution, compatibility, and release evidence | Tasks 15 and 16 |
| No overall health score and no guessed diagnostic mapping | Tasks 5, 8, 9, and 12 |
| No publication or outreach without separate approval | Global constraints, Tasks 15 and 16 |

## Final Verification Before Any Publication Decision

Run the complete local gate from a clean checkout:

```bash
uv sync --locked --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=rtl_lens --cov-report=term-missing --cov-fail-under=90
uv build
docker build --build-arg VERILATOR_VERSION=5.040 -t rtl-lens:release-candidate .
docker run --rm -v "${PWD}:/workspace" rtl-lens:release-candidate scan /workspace/tests/action/fixture --format json
```

Expected: every command exits `0`; the test report identifies any deliberately skipped platform-specific cases; wheel and source distribution contents contain licenses, templates, rule data, and type information; the container records the pinned Verilator version; and the release checklist contains no incomplete correctness, privacy, security, or licensing item.
