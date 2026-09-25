# Module Relationships and Baseline Trends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic PySlang-derived module relationships and baseline trend data to the stable JSON/HTML report without weakening scan diagnostics, timeouts, offline safety, or exit semantics.

**Architecture:** The existing PySlang worker will extract diagnostics and a bounded semantic/syntax relationship artifact from the same `Compilation`; no second parse or analyzer process is allowed. Shared immutable analysis models travel through `EngineRun` into `ScanReport`, while pure analysis functions own graph normalization and trend partitioning. JSON retains the complete artifact; offline HTML presents accessible counts and a searchable relationship table capped by a validated display limit.

**Tech Stack:** Python 3.11–3.13, PySlang 11.x public APIs, Pydantic v2 frozen models, Jinja2 autoescape, embedded vanilla JavaScript/CSS, pytest, Rich-independent report data.

**Spec:** `docs/superpowers/specs/2026-08-17-rtl-lens-design.md` and the user-approved Task 11 refinement on 2026-08-26.

## Global Constraints

- Reuse the existing PySlang compilation and worker deadline; never run a second graph-only compilation.
- Graph extraction failure produces a bounded structured analysis warning, retains all diagnostics, and does not change `EngineRun.state`, scan completeness, or exit status.
- Renderers consume only `ScanReport`; they never import PySlang or inspect engine-private objects.
- JSON contains every extracted node, edge, unresolved name, trend fingerprint, and analysis warning in deterministic order.
- A graph artifact larger than 16 MiB is treated as graph-extraction degradation: omit only the graph, add a bounded warning, and preserve diagnostics/completeness; accepted graphs are never truncated in JSON.
- HTML caps only displayed relationship rows at `scan.graph_display_limit` (default `200`, minimum `1`, maximum `2000`) and explicitly states displayed/total counts.
- Every graph and trend meaning remains available as text without JavaScript, color, or an overall score.
- All report-derived content remains untrusted: Jinja autoescape, `tojson`, restrictive offline CSP, and zero network requests remain mandatory.
- New report fields have defaults so version-1.0 reports and existing fixtures remain readable.
- TDD chronology, review findings, fix rounds, and controller infrastructure fallbacks are recorded in the Task 11 SDD ledger.

---

### Task 1: Immutable analysis models and pure deterministic builders

**Files:**
- Create: `src/rtl_lens/analysis/__init__.py`
- Create: `src/rtl_lens/analysis/module_graph.py`
- Create: `src/rtl_lens/analysis/trends.py`
- Create: `src/rtl_lens/models/analysis.py`
- Modify: `src/rtl_lens/models/__init__.py`
- Modify: `src/rtl_lens/models/project.py`
- Modify: `src/rtl_lens/config.py`
- Modify: `src/rtl_lens/cli.py`
- Create: `tests/unit/test_module_graph.py`
- Create: `tests/unit/test_trends.py`
- Modify: `tests/unit/test_config.py`
- Modify: `tests/unit/test_cli_init.py`

**Interfaces:**
- Consumes: PySlang syntax JSON shaped as nested mappings/lists with `kind`, module-header `name.text`, and hierarchy-instantiation `type.text`; normalized `Finding` records and resolved fingerprints.
- Produces: `ModuleGraph(nodes: tuple[str, ...], edges: tuple[tuple[str, str], ...], unresolved: tuple[str, ...])`; `AnalysisWarning(kind: str, message: str)`; `TrendSummary(new: tuple[str, ...], unchanged: tuple[str, ...], resolved: tuple[str, ...], baseline_configured: bool)`; `build_module_graph(syntax_payloads, defined_modules)`; `summarize_trends(findings, resolved_fingerprints, baseline_configured)`.

- [ ] **Step 1: Write failing model and graph tests**

```python
def test_module_graph_is_sorted_unique_and_preserves_unresolved() -> None:
    payload = {
        "kind": "CompilationUnit",
        "members": [
            {
                "kind": "ModuleDeclaration",
                "header": {"name": {"text": "top"}},
                "members": [
                    {"kind": "HierarchyInstantiation", "type": {"text": "alu"}},
                    {"kind": "HierarchyInstantiation", "type": {"text": "missing_ip"}},
                    {"kind": "HierarchyInstantiation", "type": {"text": "alu"}},
                ],
            }
        ],
    }

    graph = build_module_graph((payload,), frozenset({"top", "alu"}))

    assert graph.nodes == ("alu", "missing_ip", "top")
    assert graph.edges == (("top", "alu"), ("top", "missing_ip"))
    assert graph.unresolved == ("missing_ip",)
```

Also cover nested generate-block mappings/lists, malformed or non-string tokens being ignored rather than stringified, duplicate module declarations, empty projects, stable `model_dump_json()` across reversed inputs, and frozen/extra-forbid model behavior.

- [ ] **Step 2: Run graph tests and record import RED**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_module_graph.py -v -p no:cacheprovider`

Expected: collection fails because `rtl_lens.analysis.module_graph` and `rtl_lens.models.analysis` do not exist.

- [ ] **Step 3: Implement immutable analysis models**

```python
class ModuleGraph(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    unresolved: tuple[str, ...] = ()


class AnalysisWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    kind: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class TrendSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    new: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    resolved: tuple[str, ...] = ()
    baseline_configured: bool = False
```

Model validators reject non-sorted or duplicate tuples and graph edges whose endpoints are absent from `nodes`; builders are responsible for canonical sorting/deduplication before construction.

- [ ] **Step 4: Implement syntax/semantic graph normalization**

`build_module_graph` recursively walks mappings and non-string sequences. On each `ModuleDeclaration`, it reads only `header.name.text` as the current parent. Beneath that declaration it records each `HierarchyInstantiation.type.text`; nested mappings such as generate blocks retain the current parent. `defined_modules` comes from semantic `Compilation.getDefinitions()` filtered to `DefinitionKind.Module`, `Interface`, and `Program`. Nodes are the union of valid declared definitions, parent modules, and referenced child types; unresolved names are referenced children absent from `defined_modules`.

```python
def build_module_graph(
    syntax_payloads: Sequence[Mapping[str, object]],
    defined_modules: AbstractSet[str],
) -> ModuleGraph:
    edges: set[tuple[str, str]] = set()
    parents: set[str] = set()
    for payload in syntax_payloads:
        _walk(payload, parent=None, parents=parents, edges=edges)
    referenced = {child for _, child in edges}
    nodes = set(defined_modules) | parents | referenced
    return ModuleGraph(
        nodes=tuple(sorted(nodes)),
        edges=tuple(sorted(edges)),
        unresolved=tuple(sorted(referenced - set(defined_modules))),
    )
```

- [ ] **Step 5: Write failing trend partition tests**

```python
def test_trends_partition_new_unchanged_and_resolved() -> None:
    findings = (
        finding("b", baseline_state=BaselineState.EXISTING),
        finding("a", baseline_state=BaselineState.NEW),
    )

    summary = summarize_trends(
        findings,
        resolved_fingerprints=("d", "c", "c"),
        baseline_configured=True,
    )

    assert summary.new == ("a",)
    assert summary.unchanged == ("b",)
    assert summary.resolved == ("c", "d")
    assert summary.baseline_configured is True
```

Also cover no baseline, empty reports, input-order independence, and rejection of one fingerprint appearing in more than one trend partition.

- [ ] **Step 6: Implement trend normalization**

`summarize_trends` uses only current `Finding.baseline_state` plus `resolved_fingerprints`; it does not reread baseline files. It returns sorted unique fingerprint tuples and raises `ValueError` if new/unchanged/resolved sets overlap, preserving one unambiguous state per fingerprint.

- [ ] **Step 7: Add and test the display-limit configuration**

Add `graph_display_limit: int = Field(default=200, ge=1, le=2000)` to `ScanConfig`, allow `scan.graph_display_limit` in `ALLOWED_OVERRIDES`, and add `graph_display_limit = 200` to the starter configuration. Update the fixed default configuration digest with a separately computed SHA-256 value. Tests cover TOML and override values `1`, `200`, and `2000`, plus rejection of `0` and `2001`; `rtl-lens init` must still generate a loadable starter.

- [ ] **Step 8: Run Task 1 tests and quality gates**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_module_graph.py tests\unit\test_trends.py tests\unit\test_config.py tests\unit\test_cli_init.py -v -p no:cacheprovider`

Run: `.venv\Scripts\python.exe -m ruff check --no-cache src tests`

Run: `.venv\Scripts\python.exe -m mypy src`

Expected: all pass; repeated reversed-input serialization is byte-identical.

- [ ] **Step 9: Commit Task 1**

```bash
git add src/rtl_lens/analysis src/rtl_lens/models/analysis.py src/rtl_lens/models/__init__.py src/rtl_lens/models/project.py src/rtl_lens/config.py src/rtl_lens/cli.py tests/unit/test_module_graph.py tests/unit/test_trends.py tests/unit/test_config.py tests/unit/test_cli_init.py
git commit -m "feat: model module relationships and baseline trends"
```

---

### Task 2: Single-pass PySlang artifact transport and scan integration

**Files:**
- Modify: `src/rtl_lens/models/engine.py`
- Modify: `src/rtl_lens/models/report.py`
- Modify: `src/rtl_lens/engines/pyslang_engine.py`
- Modify: `src/rtl_lens/services/scan.py`
- Modify: `tests/unit/test_models.py`
- Modify: `tests/unit/test_pyslang_engine.py`
- Modify: `tests/unit/test_scan_service.py`
- Modify: `tests/e2e/test_partial_scan.py`

**Interfaces:**
- Consumes: Task 1 `ModuleGraph`, `AnalysisWarning`, `TrendSummary`, `build_module_graph`, and `summarize_trends`.
- Produces: optional `EngineRun.module_graph`, `EngineRun.analysis_warnings`, `ScanReport.module_graph`, `ScanReport.trends`, and `ScanReport.analysis_warnings`; PySlang worker transport carries diagnostics and graph artifacts from one `Compilation`.

- [ ] **Step 1: Write failing engine/report round-trip tests**

```python
def test_engine_and_report_round_trip_analysis_artifacts() -> None:
    graph = ModuleGraph(nodes=("alu", "top"), edges=(("top", "alu"),))
    warning = AnalysisWarning(kind="module_graph", message="graph extraction failed")
    run = EngineRun(
        engine="pyslang",
        state=EngineState.COMPLETED,
        module_graph=graph,
        analysis_warnings=(warning,),
    )
    report = report_fixture(
        engine_runs=(run,),
        module_graph=graph,
        trends=TrendSummary(new=("a",), baseline_configured=True),
        analysis_warnings=(warning,),
    )

    assert ScanReport.model_validate_json(report.model_dump_json()) == report
```

Also prove old version-1.0 fixture JSON without these fields loads with empty defaults.

- [ ] **Step 2: Run model tests and record missing-field RED**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_models.py -v -p no:cacheprovider`

Expected: Pydantic rejects the new `EngineRun` and `ScanReport` fields as extras.

- [ ] **Step 3: Extend immutable engine and report contracts**

```python
class EngineRun(BaseModel):
    # existing fields remain unchanged
    module_graph: ModuleGraph | None = None
    analysis_warnings: tuple[AnalysisWarning, ...] = ()


class ScanReport(BaseModel):
    # existing fields remain unchanged
    module_graph: ModuleGraph = Field(default_factory=ModuleGraph)
    trends: TrendSummary = Field(default_factory=TrendSummary)
    analysis_warnings: tuple[AnalysisWarning, ...] = ()
```

No renderer or service may recover graph data from engine-private state; the report fields are the only renderer inputs.

- [ ] **Step 4: Write failing single-compilation PySlang tests**

Add a hierarchy fixture with `top -> alu`, a duplicate `alu` instance, a nested generate instantiation, and `missing_ip`. A real-adapter test asserts diagnostics and graph return in the same completed `EngineRun`. Instrument `SyntaxTree.fromFile` and `Compilation` construction in a direct native-analysis unit so each source tree is added once and no second compilation occurs.

Add a graph-extractor fault injection at the `_analyze_native` boundary:

```python
def test_graph_failure_retains_diagnostics_and_completed_state(monkeypatch, project) -> None:
    monkeypatch.setattr(pyslang_module, "build_module_graph", raises_graph_error)

    native = pyslang_module._analyze_native(EngineRequest(project=project, timeout_seconds=10))

    assert native.diagnostics
    assert native.module_graph is None
    assert native.analysis_warnings[0].kind == "module_graph"
```

The warning message must be bounded to 500 characters even when exception stringification fails.

- [ ] **Step 5: Refactor the worker result without weakening existing limits**

Change `_analyze_native` to return `_WorkerResult`, not only diagnostics. It builds one `Compilation`, converts all diagnostics under the existing 10,000-diagnostic and 4,096-character limits, then separately attempts graph extraction:

```python
diagnostics = _convert_all_diagnostics(compilation, root)
try:
    graph = build_module_graph(
        tuple(json.loads(tree.root.to_json()) for tree in compilation.getSyntaxTrees()),
        frozenset(
            definition.name
            for definition in compilation.getDefinitions()
            if definition.definitionKind in {
                DefinitionKind.Module,
                DefinitionKind.Interface,
                DefinitionKind.Program,
            }
        ),
    )
    warnings = ()
except Exception as error:
    graph = None
    warnings = (AnalysisWarning(kind="module_graph", message=_bounded_failure_message(error)),)
return _WorkerResult(
    diagnostics=diagnostics,
    module_graph=graph,
    analysis_warnings=warnings,
)
```

Before returning, serialize only the graph artifact and enforce `_GRAPH_ARTIFACT_LIMIT = 16 * 1024 * 1024`; an oversized artifact becomes `module_graph=None` plus an `AnalysisWarning(kind="module_graph_limit", ...)`. `_worker_main`, `_validate_worker_result`, the 64 MiB overall transport cap, deadline checks, terminate/kill/reaper ownership, and temporary cleanup remain intact. `PySlangEngine.run` copies the artifact fields into its completed `EngineRun`; graph failure or graph oversize never enters the adapter failure branch.

- [ ] **Step 6: Write failing scan-integration tests**

Cover all of these combinations:

- completed PySlang graph is copied into `ScanReport`;
- Verilator artifacts never replace a PySlang graph;
- graph warning is retained once, diagnostics still merge, `scan_state` stays complete, and policy exit is unchanged;
- optional/required Verilator failures keep their existing completeness/exit behavior;
- trends derive from NEW/EXISTING findings and resolved fingerprints;
- `baseline_configured` is true exactly when `config.scan.baseline_path` is not `None`;
- configuration-failure reports contain empty/default graph and trend artifacts.

- [ ] **Step 7: Integrate artifacts in `ScanService`**

After engine runs and baseline comparison, select the PySlang graph only from a completed run, concatenate analysis warnings in deterministic engine/kind/message order, and call:

```python
trends = summarize_trends(
    findings,
    comparison.resolved_fingerprints,
    baseline_configured=config.scan.baseline_path is not None,
)
```

Populate the three report fields in complete, partial, failed, and configuration-failure outcomes. Do not include graph/trend state in policy blocking or scan completeness calculations.

- [ ] **Step 8: Run Task 2 and regression gates**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_models.py tests\unit\test_pyslang_engine.py tests\unit\test_scan_service.py tests\e2e\test_partial_scan.py -v -p no:cacheprovider`

Run: `.venv\Scripts\python.exe -m ruff check --no-cache src tests`

Run: `.venv\Scripts\python.exe -m mypy src`

Expected: all pass, with only the existing platform-specific skips; real PySlang hierarchy extraction proves a single worker scan.

- [ ] **Step 9: Commit Task 2**

```bash
git add src/rtl_lens/models/engine.py src/rtl_lens/models/report.py src/rtl_lens/engines/pyslang_engine.py src/rtl_lens/services/scan.py tests/unit/test_models.py tests/unit/test_pyslang_engine.py tests/unit/test_scan_service.py tests/e2e/test_partial_scan.py
git commit -m "feat: carry semantic graph artifacts through scans"
```

---

### Task 3: Stable JSON and accessible offline HTML views

**Files:**
- Modify: `src/rtl_lens/renderers/json_report.py`
- Modify: `src/rtl_lens/renderers/html_report.py`
- Modify: `src/rtl_lens/renderers/assets/report.html.j2`
- Modify: `src/rtl_lens/renderers/assets/report.css`
- Modify: `src/rtl_lens/renderers/assets/report.js`
- Modify: `tests/unit/test_json_report.py`
- Modify: `tests/unit/test_html_report.py`
- Modify: `tests/browser/test_html_report.py`
- Modify: `tests/fixtures/reports/representative.json`

**Interfaces:**
- Consumes: Task 2 `ScanReport.module_graph`, `ScanReport.trends`, `ScanReport.analysis_warnings`, plus `ScanConfig.graph_display_limit` supplied to HTML writing.
- Produces: deterministic complete JSON; accessible module/trend/warning HTML sections; local relationship search; no network requests.

- [ ] **Step 1: Resolve the HTML display-limit transport explicitly**

Change `write_html_report` to accept a keyword-only validated display limit while preserving the existing call shape:

```python
def write_html_report(
    report: ScanReport,
    destination: Path,
    *,
    graph_display_limit: int = 200,
) -> None:
    if not 1 <= graph_display_limit <= 2000:
        raise ValueError("graph_display_limit must be between 1 and 2000")
```

Update the CLI call to pass `project_config.scan.graph_display_limit`. Tests prove old two-argument callers retain the default.

- [ ] **Step 2: Write failing JSON completeness and determinism tests**

Create a report with more than 200 graph edges, unresolved hostile strings, all three trend partitions, and an analysis warning. Write it twice and assert byte-identical JSON contains every edge and fingerprint; no JSON truncation is permitted. Existing atomic write, concurrency, cleanup, and destination-preservation tests remain unchanged.

- [ ] **Step 3: Write failing HTML structural and safety tests**

Assert the generated file contains:

- an `analysis-warnings` section with explicit WARNING text;
- a `baseline-trends` section that says whether a baseline was configured and prints NEW/UNCHANGED/RESOLVED counts;
- a `module-relationships` section with node, relationship, unresolved, and displayed/total counts;
- a relationship-search label/input and a semantic `<table>` whose first `graph_display_limit` sorted edges are server-rendered;
- an explicit no-relationships empty state;
- literal hostile graph/warning text without executable tags or attributes;
- complete artifact data inside escaped `report-data` JSON;
- no score text and no external URL/resource.

- [ ] **Step 4: Prepare bounded renderer context**

`write_html_report` computes `displayed_edges = report.module_graph.edges[:graph_display_limit]`, never mutates the report, and passes total/display counts plus complete `report_data`. Trend rows map current fingerprints back to findings when available; resolved fingerprints remain honest fingerprints rather than invented titles. Analysis warnings are sorted and rendered as untrusted text.

- [ ] **Step 5: Implement accessible template and styles**

Add sections in this order after engine status and before findings: analysis warnings (only when non-empty), baseline trends, then module relationships. Use headings, text labels, `<dl>` counts, and a captioned relationship table with `Parent module`, `Instantiated module`, and `Resolution` columns. Unresolved rows include the literal label `UNRESOLVED`; CSS color is supplementary. At 390px the table scrolls within its own region and never expands the page viewport.

- [ ] **Step 6: Implement local relationship search**

Extend existing embedded JavaScript without introducing a dependency. On `input`, compare a case-folded query against each row's `data-search` value, toggle `hidden`, and update an `aria-live` displayed-row count. With JavaScript disabled, every server-rendered capped row stays visible. Preserve existing finding filters and CSP.

- [ ] **Step 7: Add real-browser acceptance**

Using Playwright with `RTL_LENS_TEST_CHROMIUM` fallback already established by Task 9, verify:

- zero non-`file:` requests;
- searching by parent, child, and hostile literal text filters rows correctly;
- keyboard focus is visible on the graph search field;
- the aria-live count updates;
- baseline and unresolved meanings are textual;
- a 390px viewport has no document-level horizontal overflow;
- existing engine token, finding filter, injection, and keyboard tests still pass.

- [ ] **Step 8: Run Task 3 and full release gates**

Run: `.venv\Scripts\python.exe -m pytest tests\unit\test_json_report.py tests\unit\test_html_report.py tests\browser\test_html_report.py -v -p no:cacheprovider`

Run with system Chrome when managed Playwright Chromium is unavailable:

```powershell
$env:RTL_LENS_TEST_CHROMIUM='C:\Program Files\Google\Chrome\Application\chrome.exe'
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Run: `.venv\Scripts\python.exe -m ruff check --no-cache src tests`

Run: `.venv\Scripts\python.exe -m mypy src`

Run: `.venv\Scripts\python.exe -m ruff format --check .`

Run: `git diff --check`

Expected: the full suite passes with only established platform skips; HTML remains offline/injection-safe and JSON contains the uncapped graph.

- [ ] **Step 9: Commit Task 3**

```bash
git add src/rtl_lens/renderers src/rtl_lens/cli.py tests/unit/test_json_report.py tests/unit/test_html_report.py tests/browser/test_html_report.py tests/fixtures/reports/representative.json
git commit -m "feat: report module relationships and baseline trends"
```

---

## Task 11 completion gate

- A fresh read-only reviewer evaluates each subtask diff before the next subtask begins.
- Every Critical or Important finding returns to the same implementer for at most five bounded fix rounds.
- After Task 3, a final reviewer inspects the complete Task 11 range for schema compatibility, single-compilation truthfulness, degradation semantics, full-JSON/capped-HTML behavior, offline security, accessibility, deterministic output, and test honesty.
- Task 11 is complete only after final review reports 0 Critical and 0 Important findings and controller-run full verification is green.
