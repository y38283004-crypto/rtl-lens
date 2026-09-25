# Curated Bilingual Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand RTL Lens from six to exactly thirty reviewed bilingual diagnostic guides whose runtime mappings, examples, and generated documentation remain deterministic and evidence-backed.

**Architecture:** Versioned YAML entries remain the only authored source for explanations, native engine-code mappings, example paths, references, and review status. `KnowledgeStore` validates those records and materializes an immutable `(engine, native_code) -> canonical_rule` map consumed by canonicalization, while tests independently verify the declared map against real failing/fixed package resources. Markdown rule pages are generated from the same typed store so runtime explanations and public documentation cannot drift.

**Tech Stack:** Python 3.11–3.13, Pydantic 2.x, PyYAML, importlib.resources, PySlang 11.x, optional Verilator 5.x, Pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-17-rtl-lens-design.md`

**Research:** `docs/superpowers/research/2026-08-28-task12-rule-mapping.md`

## Global Constraints

- The final catalog contains exactly these 30 IDs: `width-mismatch`, `incomplete-assignment`, `case-incomplete`, `case-overlap`, `unused-signal`, `undriven-signal`, `multiple-drivers`, `blocking-in-sequential`, `always-comb-order`, `always-never`, `ascending-range`, `assignment-in-expression`, `assignment-to-input`, `blocking-and-nonblocking`, `case-with-x`, `case-x`, `constant-comparison`, `combinational-delay`, `declaration-filename`, `deprecated-defparam`, `implicit-net`, `port-width-mismatch`, `missing-pin`, `empty-pin-connection`, `signedness-mismatch`, `out-of-range-select`, `duplicate-definition`, `undeclared-identifier`, `unsupported-construct`, and `timescale-mismatch`.
- Every guide has non-empty English and Simplified Chinese title, cause, risk, and fix; one minimal failing example; one corrected example; at least one stable first-party HTTPS reference; and `review_status: reviewed`.
- Knowledge entries are inert data. They never contain executable Python, Jinja, shell fragments, or message-text matching rules.
- A native code is activated only when the exact code is expected from the failing fixture and absent from the corrected fixture. Similar wording is not proof.
- Unmapped diagnostics remain `engine-native:<engine>:<code>`; never guess from message text.
- Do not add PySlang `AnalysisManager` in this task. The current adapter's `Compilation.getAllDiagnostics()` surface is binding.
- Verilator `WIDTH`, `WIDTHEXPAND`, and `WIDTHTRUNC` map only to `width-mismatch`; `port-width-mismatch` is PySlang-only because the current key has no structural context.
- Verilator tests skip explicitly when the executable is absent locally, but the pinned container/CI execution is required before the release candidate can pass.
- `UNSUPPORTED` remains inactive until a pinned Verilator fixture actually emits it; the guide and fixture may exist before activation.
- Python support remains `>=3.11,<3.14`; no new runtime dependency is added.
- Follow TDD for every production behavior: add a focused failing test, observe the expected failure, implement the minimum change, and re-run the affected suite.
- Commit only the exact scoped files for each task. Do not push, publish, tag, create a remote repository, contact external users, or perform promotion.

## Target Mapping Matrix

`local` means the current PySlang adapter must prove the exact emitted code on this host. `container` means a real Verilator executable must prove it in the pinned CI/container before release. AnalysisManager-only slang codes are deliberately absent.

| Canonical ID | Severity | Active native mappings after this plan |
|---|---|---|
| `width-mismatch` | error | Verilator `WIDTH`, `WIDTHEXPAND`, `WIDTHTRUNC` (container); PySlang `constant-conversion`, `width-expand`, `width-trunc` (local) |
| `incomplete-assignment` | warning | Verilator `LATCH` (container) |
| `case-incomplete` | warning | Verilator `CASEINCOMPLETE` (container) |
| `case-overlap` | warning | Verilator `CASEOVERLAP` (container) |
| `unused-signal` | info | Verilator `UNUSEDSIGNAL` (container) |
| `undriven-signal` | warning | Verilator `UNDRIVEN` (container) |
| `multiple-drivers` | error | Verilator `MULTIDRIVEN` (container) |
| `blocking-in-sequential` | warning | Verilator `BLKSEQ` (container) |
| `always-comb-order` | warning | Verilator `ALWCOMBORDER` (container) |
| `always-never` | warning | Verilator `ALWNEVER` (container) |
| `ascending-range` | warning | Verilator `ASCRANGE` (container) |
| `assignment-in-expression` | warning | Verilator `ASSIGNEQEXPR` (container) |
| `assignment-to-input` | error | Verilator `ASSIGNIN` (container) |
| `blocking-and-nonblocking` | error | Verilator `BLKANDNBLK` (container) |
| `case-with-x` | warning | Verilator `CASEWITHX` (container) |
| `case-x` | warning | Verilator `CASEX` (container) |
| `constant-comparison` | warning | Verilator `CMPCONST` (container) |
| `combinational-delay` | warning | Verilator `COMBDLY` (container) |
| `declaration-filename` | info | Verilator `DECLFILENAME` (container) |
| `deprecated-defparam` | warning | Verilator `DEFPARAM` (container) |
| `implicit-net` | warning | Verilator `IMPLICIT` (container) |
| `port-width-mismatch` | error | PySlang `port-width-expand`, `port-width-trunc` (local) |
| `missing-pin` | warning | Verilator `PINMISSING` (container); PySlang `unconnected-input-port`, `unconnected-output-port`, `unconnected-inout-port` (local) |
| `empty-pin-connection` | info | Verilator `PINCONNECTEMPTY` (container); PySlang `empty-input-connection`, `empty-output-connection`, `empty-inout-connection` (local) |
| `signedness-mismatch` | warning | Verilator `UNSIGNED` (container); PySlang `sign-conversion`, `sign-compare` (local) |
| `out-of-range-select` | error | Verilator `SELRANGE` (container); PySlang `index-oob`, `range-oob` (local) |
| `duplicate-definition` | error | Verilator `MODDUP` (container); PySlang `duplicate-definition` (local) |
| `undeclared-identifier` | error | PySlang `DiagCode(UndeclaredIdentifier)` (local, pinned PySlang 11 regression) |
| `unsupported-construct` | error | no active mapping until pinned Verilator proves `UNSUPPORTED` |
| `timescale-mismatch` | warning | Verilator `TIMESCALEMOD` (container); PySlang `DiagCode(MissingTimeScale)` (local, pinned PySlang 11 regression) |

The `unsupported-construct` entry is the single intentional guide-only record. It must set `mapping_note` to explain that no stable native mapping is active; every other entry has at least one `engine_mapping`.

## Content Focus for the 24 New Guides

| IDs | English/Chinese content must explain |
|---|---|
| `multiple-drivers`, `blocking-in-sequential` | Conflicting procedural/continuous ownership and clocked-process simulation/synthesis mismatch; fixes establish one owner and nonblocking sequential assignments. |
| `always-comb-order`, `always-never` | Read-before-write sensitivity pitfalls and event controls with no effective trigger; fixes order combinational assignments by dependency and add a real sensitivity dependency or intended clock/event. |
| `ascending-range`, `assignment-in-expression` | Accidental index direction assumptions and assignment mistaken for comparison; fixes standardize range direction or document conversion, and separate assignment from the condition. |
| `assignment-to-input`, `blocking-and-nonblocking` | Input ports are driven by the parent and one variable must not mix assignment disciplines; fixes use an internal signal/output or one consistent owner/style. |
| `case-with-x`, `case-x` | Literal X/Z matching and `casex` optimism can hide unknown-state bugs; fixes use explicit `case inside`, `casez`, assertions, or ordinary `case` with deliberate unknown handling. |
| `constant-comparison`, `combinational-delay` | Type/range constraints can make a comparison constant and delays in combinational logic are not synthesizable timing models; fixes correct widths/signs and move timing to a testbench or sequential design. |
| `declaration-filename`, `deprecated-defparam` | File/module-name mismatch hurts navigation/tooling and hierarchical `defparam` overrides are fragile; fixes align names and use parameter overrides at instantiation. |
| `implicit-net`, `port-width-mismatch` | Typos can silently create one-bit nets and port connections can truncate/extend; fixes declare signals under ``default_nettype none`` and explicitly size/cast ports. |
| `missing-pin`, `empty-pin-connection` | Omitted named pins differ from explicitly empty connections; fixes connect required ports and document intentionally open outputs without concealing missing inputs. |
| `signedness-mismatch`, `out-of-range-select` | Signed/unsigned conversion changes extension/comparison and illegal selects yield X or tool-dependent behavior; fixes use explicit signed casts and valid parameterized bounds. |
| `duplicate-definition`, `undeclared-identifier` | Duplicate design-unit names create ambiguous elaboration and undeclared names are usually scope/typo failures; fixes keep one definition and declare/import the intended symbol. |
| `unsupported-construct`, `timescale-mismatch` | Tool support is version-specific and inconsistent time units change delay interpretation; fixes use supported equivalents or the pinned tool, and declare consistent `timeunit/timeprecision` or ``timescale`` policy. |

---

### Task 1: Typed mapping evidence and test harness

**Files:**
- Modify: `src/rtl_lens/knowledge/schema.py`
- Modify: `src/rtl_lens/knowledge/store.py`
- Modify: `src/rtl_lens/knowledge/rules/{width-mismatch,incomplete-assignment,case-incomplete,case-overlap,unused-signal,undriven-signal}.yaml`
- Modify: `tests/unit/test_knowledge.py`
- Create: `tests/knowledge/conftest.py`
- Create: `tests/knowledge/test_rule_catalog.py`
- Create: `tests/knowledge/test_rule_examples.py`
- Create: `tests/fixtures/rules/engine-codes.json`

**Interfaces:**
- Consumes: existing `ExplanationEntry`, `KnowledgeStore`, packaged `rules/` and `examples/` resources, `PySlangEngine`, and `VerilatorEngine`.
- Produces: `EngineMapping(engine: Literal["pyslang", "verilator"], code: str, verification: Literal["local", "container"])`; `TARGET_RULE_IDS: frozenset[str]`; `KnowledgeStore.engine_rules: Mapping[tuple[str, str], str]`; reusable real-adapter fixture tests.

- [ ] **Step 1: Add failing schema and store tests**

Add tests that require all 30 values in `typing.get_args(RuleId)`, reject duplicate/unsorted mappings, reject control characters in codes, require either at least one mapping or a non-empty `mapping_note`, and reject one native `(engine, code)` assigned to two canonical IDs.

```python
def test_schema_declares_exact_target_rule_ids() -> None:
    assert set(get_args(RuleId)) == EXPECTED_CANONICAL_RULE_IDS


def test_store_rejects_conflicting_native_mapping(sample_entries) -> None:
    first, second = sample_entries
    duplicate = EngineMapping(engine="verilator", code="WIDTH", verification="container")
    with pytest.raises(ValueError, match="native mapping"):
        KnowledgeStore(
            (
                first.model_copy(update={"engine_mappings": (duplicate,)}),
                second.model_copy(update={"engine_mappings": (duplicate,)}),
            )
        )
```

- [ ] **Step 2: Run the RED tests**

Run: `python -m pytest tests/unit/test_knowledge.py tests/knowledge/test_rule_catalog.py -v`

Expected: FAIL because `RuleId` has six values and `EngineMapping`, `TARGET_RULE_IDS`, and `engine_rules` do not exist.

- [ ] **Step 3: Implement immutable evidence records and deterministic map construction**

Use this exact model boundary:

```python
class EngineMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    engine: Literal["pyslang", "verilator"]
    code: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.()\-]+$")
    verification: Literal["local", "container"]


class ExplanationEntry(BaseModel):
    # retain all existing fields and validators
    engine_mappings: tuple[EngineMapping, ...] = ()
    mapping_note: str | None = Field(default=None, min_length=12)
```

Add a model validator that requires mappings or `mapping_note`, rejects duplicate pairs, and requires mappings sorted by `(engine, code)`. `KnowledgeStore` materializes a `MappingProxyType` map and raises on cross-entry conflicts. Keep `DEFAULT_RULE_IDS` equal to the currently installed six IDs in this task; add `TARGET_RULE_IDS` for the exact final 30.

- [ ] **Step 4: Migrate the six seed YAML entries and independent expectation fixture**

Add the exact mappings from the target matrix to the six YAML files and to `tests/fixtures/rules/engine-codes.json`. The JSON fixture is a test oracle and must not be imported by production code.

- [ ] **Step 5: Add real-adapter example contracts and verify GREEN**

`tests/knowledge/test_rule_examples.py` copies each packaged failing/fixed resource into isolated temporary project roots. For every `local` PySlang mapping, assert the exact code occurs in the failing run and not the corrected run. For every `container` mapping, run the same assertion through the real `VerilatorEngine`; use only this explicit skip:

```python
requires_verilator = pytest.mark.skipif(
    shutil.which("verilator") is None,
    reason="real Verilator mapping evidence requires the pinned container",
)


VERILATOR_ENTRIES = tuple(
    entry
    for entry in KnowledgeStore.load_default().entries
    if any(mapping.engine == "verilator" for mapping in entry.engine_mappings)
)


@requires_verilator
@pytest.mark.parametrize("entry", VERILATOR_ENTRIES, ids=lambda entry: entry.rule_id)
def test_verilator_mapping_is_emitted_only_by_the_failing_example(
    entry: ExplanationEntry, tmp_path: Path
) -> None:
    failing = run_example(entry, "failing", tmp_path / "failing", VerilatorEngine())
    fixed = run_example(entry, "fixed", tmp_path / "fixed", VerilatorEngine())
    expected = {
        mapping.code for mapping in entry.engine_mappings if mapping.engine == "verilator"
    }
    assert expected <= {diagnostic.original_code for diagnostic in failing.diagnostics}
    assert expected.isdisjoint(
        diagnostic.original_code for diagnostic in fixed.diagnostics
    )
```

Define `run_example(entry, variant, root, engine) -> EngineRun` in `tests/knowledge/conftest.py`; it copies the selected packaged resource to `root`, builds a one-source `ResolvedProject` and `EngineRequest(timeout_seconds=10)`, then calls the real adapter. It must not parse display text or mock the adapter.

Run: `python -m pytest tests/unit/test_knowledge.py tests/knowledge -v`

Expected: PASS; Verilator cases are explicitly skipped on this host, while current PySlang cases execute.

- [ ] **Step 6: Run quality checks and commit**

Run: `python -m ruff check src tests`

Run: `python -m mypy src`

```bash
git add src/rtl_lens/knowledge/schema.py src/rtl_lens/knowledge/store.py src/rtl_lens/knowledge/rules tests/unit/test_knowledge.py tests/knowledge tests/fixtures/rules/engine-codes.json
git commit -m "feat: model evidence-backed diagnostic mappings"
```

### Task 2: First six-family expansion and runtime single source of truth

**Files:**
- Modify: `src/rtl_lens/diagnostics/canonical.py`
- Modify: `src/rtl_lens/knowledge/store.py`
- Create: `src/rtl_lens/knowledge/rules/{multiple-drivers,blocking-in-sequential,always-comb-order,always-never,ascending-range,assignment-in-expression}.yaml`
- Create: matching `src/rtl_lens/knowledge/examples/{failing,fixed}/*.sv`
- Modify: `tests/fixtures/rules/engine-codes.json`
- Modify: `tests/unit/test_canonical.py`
- Modify: `tests/unit/test_knowledge.py`
- Modify: `tests/knowledge/test_rule_catalog.py`
- Modify: `tests/knowledge/test_rule_examples.py`

**Interfaces:**
- Consumes: `KnowledgeStore.engine_rules` and the Task 1 evidence model.
- Produces: a 12-entry default catalog and `ENGINE_RULES: Final[Mapping[tuple[str, str], str]]` derived from the validated default store rather than a hand-written Python table.

- [ ] **Step 1: Add failing tests for six new entries and derived runtime mappings**

Assert the default store contains the seed plus these six IDs, all bilingual fields contain at least eight characters, each example pair differs, and `ENGINE_RULES == KnowledgeStore.load_default().engine_rules`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge -v`

Expected: FAIL because the six entries/resources are missing and `ENGINE_RULES` is still hand-written.

- [ ] **Step 3: Add the reviewed batch**

Write the six YAML entries using the exact severity/mappings and content focus tables above. Each failing file triggers the named defect; each corrected file removes that defect without suppressing the warning pragma. Use first-party Verilator warning URLs for references.

- [ ] **Step 4: Switch canonicalization to the validated store**

Replace the literal mapping table with:

```python
ENGINE_RULES: Final[Mapping[tuple[str, str], str]] = KnowledgeStore.load_default().engine_rules
_KNOWN_RULES = TARGET_RULE_IDS
```

No message matching or fallback heuristics are added. Update `DEFAULT_RULE_IDS` to the exact 12 installed entries and expand the independent JSON oracle.

- [ ] **Step 5: Verify GREEN, regression behavior, and commit**

Run: `python -m pytest tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge -v`

Run: `python -m pytest tests/unit/test_scan_service.py tests/unit/test_html_report.py -v`

```bash
git add src/rtl_lens/diagnostics/canonical.py src/rtl_lens/knowledge tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge tests/fixtures/rules/engine-codes.json
git commit -m "feat: add six procedural RTL diagnostic guides"
```

### Task 3: Expression, case, and timing guide batch

**Files:**
- Modify: `src/rtl_lens/knowledge/store.py`
- Create: `src/rtl_lens/knowledge/rules/{assignment-to-input,blocking-and-nonblocking,case-with-x,case-x,constant-comparison,combinational-delay}.yaml`
- Create: matching `src/rtl_lens/knowledge/examples/{failing,fixed}/*.sv`
- Modify: `tests/fixtures/rules/engine-codes.json`
- Modify: `tests/unit/test_knowledge.py`
- Modify: `tests/knowledge/test_rule_catalog.py`
- Modify: `tests/knowledge/test_rule_examples.py`

**Interfaces:**
- Consumes: data-driven mapping and example contracts from Tasks 1–2.
- Produces: an 18-entry default catalog with exact mappings `ASSIGNIN`, `BLKANDNBLK`, `CASEWITHX`, `CASEX`, `CMPCONST`, and `COMBDLY`.

- [ ] **Step 1: Write and run failing batch tests**

Add the six expected IDs and mapping pairs to the independent oracle before adding production YAML.

Run: `python -m pytest tests/unit/test_knowledge.py tests/knowledge -v`

Expected: FAIL with six missing catalog entries/resources.

- [ ] **Step 2: Add the six reviewed YAML/example pairs**

Use the exact target matrix and content-focus table. The `combinational-delay` corrected example removes the delay rather than disabling timing diagnostics; `case-x` replaces `casex`; `case-with-x` handles unknowns deliberately without converting to `casex`.

- [ ] **Step 3: Update exact installed IDs and verify**

Update `DEFAULT_RULE_IDS` to the exact 18 installed IDs.

Run: `python -m pytest tests/unit/test_knowledge.py tests/knowledge -v`

Expected: PASS with real PySlang coverage and explicit Verilator skips only.

- [ ] **Step 4: Commit the batch**

```bash
git add src/rtl_lens/knowledge tests/unit/test_knowledge.py tests/knowledge tests/fixtures/rules/engine-codes.json
git commit -m "feat: explain expression case and timing diagnostics"
```

### Task 4: Declaration and interface guide batch

**Files:**
- Modify: `src/rtl_lens/knowledge/store.py`
- Create: `src/rtl_lens/knowledge/rules/{declaration-filename,deprecated-defparam,implicit-net,port-width-mismatch,missing-pin,empty-pin-connection}.yaml`
- Create: matching `src/rtl_lens/knowledge/examples/{failing,fixed}/*.sv`
- Modify: `tests/fixtures/rules/engine-codes.json`
- Modify: `tests/unit/test_knowledge.py`
- Modify: `tests/knowledge/test_rule_catalog.py`
- Modify: `tests/knowledge/test_rule_examples.py`

**Interfaces:**
- Consumes: the shared schema, store, and real-adapter evidence harness.
- Produces: a 24-entry default catalog; safe PySlang-only port-width mapping; direction-specific missing/empty pin mappings; no Verilator `WIDTH*` alias to port width.

- [ ] **Step 1: Write and run failing batch tests**

Add six IDs and the exact mapping pairs to the independent oracle. Add a regression asserting `ENGINE_RULES[("verilator", "WIDTHTRUNC")] == "width-mismatch"` and no second value can be assigned to `port-width-mismatch`.

Run: `python -m pytest tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge -v`

Expected: FAIL because the six entries and evidence resources are absent.

- [ ] **Step 2: Add the six reviewed entries and examples**

Use `declaration_filename.sv` as the real resource filename for the filename guide so its corrected module can exactly match the basename. The missing/empty pin fixtures contain input, output, and inout ports so every declared PySlang subcode is independently observed.

- [ ] **Step 3: Update exact installed IDs and verify**

Update `DEFAULT_RULE_IDS` to the exact 24 installed IDs.

Run: `python -m pytest tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge -v`

Expected: PASS; `port-width-mismatch` is proven only through `port-width-expand`/`port-width-trunc`.

- [ ] **Step 4: Commit the batch**

```bash
git add src/rtl_lens/knowledge tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge tests/fixtures/rules/engine-codes.json
git commit -m "feat: document declaration and interface diagnostics"
```

### Task 5: Type, scope, support, and timescale guide batch

**Files:**
- Modify: `src/rtl_lens/knowledge/store.py`
- Create: `src/rtl_lens/knowledge/rules/{signedness-mismatch,out-of-range-select,duplicate-definition,undeclared-identifier,unsupported-construct,timescale-mismatch}.yaml`
- Create: matching `src/rtl_lens/knowledge/examples/{failing,fixed}/*.sv`
- Modify: `tests/fixtures/rules/engine-codes.json`
- Modify: `tests/unit/test_knowledge.py`
- Modify: `tests/knowledge/test_rule_catalog.py`
- Modify: `tests/knowledge/test_rule_examples.py`

**Interfaces:**
- Consumes: the prior 24 entries and the exact 30-ID `TARGET_RULE_IDS`.
- Produces: the final exact 30-entry default catalog and version-pinned fallback-code tests.

- [ ] **Step 1: Add the final failing completeness and version-pinning tests**

```python
def test_default_catalog_contains_exactly_the_approved_thirty() -> None:
    store = KnowledgeStore.load_default()
    assert {entry.rule_id for entry in store.entries} == TARGET_RULE_IDS
    assert len(store.entries) == 30


def test_fallback_codes_are_pinned_to_pyslang_11() -> None:
    assert ENGINE_RULES[("pyslang", "DiagCode(UndeclaredIdentifier)")] == (
        "undeclared-identifier"
    )
    assert ENGINE_RULES[("pyslang", "DiagCode(MissingTimeScale)")] == "timescale-mismatch"
```

Run: `python -m pytest tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge -v`

Expected: FAIL because the last six entries do not exist.

- [ ] **Step 2: Add five mapped guides plus the honest guide-only entry**

Use the exact target matrix. `unsupported-construct.yaml` has `engine_mappings: []` and a `mapping_note` stating that `UNSUPPORTED` is documented but inactive until the pinned Verilator fixture emits it. Its failing/fixed example demonstrates the concept but does not create a runtime mapping.

- [ ] **Step 3: Update the exact default set and run GREEN**

Set `DEFAULT_RULE_IDS = TARGET_RULE_IDS`. Verify the PySlang failing fixtures emit the two exact `DiagCode(...)` fallback strings and that the fixed fixtures do not.

Run: `python -m pytest tests/unit/test_canonical.py tests/unit/test_knowledge.py tests/knowledge -v`

Expected: PASS; the default store contains exactly 30 entries and all active local mappings have executed evidence.

- [ ] **Step 4: Run affected regressions and commit**

Run: `python -m pytest tests/unit/test_scan_service.py tests/unit/test_html_report.py tests/e2e/test_cli_scan.py -v`

```bash
git add src/rtl_lens/knowledge tests/unit/test_knowledge.py tests/knowledge tests/fixtures/rules/engine-codes.json
git commit -m "feat: complete thirty bilingual diagnostic guides"
```

### Task 6: Deterministic rule documentation and release evidence gate

**Files:**
- Create: `src/rtl_lens/knowledge/docs.py`
- Create: `tools/generate_rule_docs.py`
- Create: `docs/rules/index.md`
- Create: `docs/rules/*.md`
- Create: `tests/knowledge/test_rule_docs.py`
- Modify: `tests/knowledge/test_rule_examples.py`
- Modify: `tests/unit/test_knowledge.py`

**Interfaces:**
- Consumes: final `KnowledgeStore.entries` and packaged example resources.
- Produces: `render_rule_docs(store: KnowledgeStore) -> Mapping[PurePosixPath, str]`; `write_rule_docs(output: Path, *, check: bool) -> tuple[Path, ...]`; committed deterministic bilingual Markdown pages.

- [ ] **Step 1: Add failing generated-document tests**

```python
def test_committed_rule_docs_match_typed_catalog(tmp_path: Path) -> None:
    expected = render_rule_docs(KnowledgeStore.load_default())
    assert set(expected) == {
        PurePosixPath("index.md"),
        *(PurePosixPath(f"{rule_id}.md") for rule_id in TARGET_RULE_IDS),
    }
    for relative, content in expected.items():
        assert (Path("docs/rules") / relative).read_text(encoding="utf-8") == content
```

Also assert each page contains both localized titles, cause/risk/fix sections, failing/fixed fenced SystemVerilog, native mapping status, and primary references.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/knowledge/test_rule_docs.py -v`

Expected: FAIL because the renderer and committed docs do not exist.

- [ ] **Step 3: Implement a pure deterministic renderer and thin writer**

Sort entries by `rule_id`, use LF line endings, end every file with one newline, and read examples through `importlib.resources`. The writer rejects stale or extra generated `.md` files in `--check` mode and never deletes files outside the exact `docs/rules/*.md` output set.

Run: `python tools/generate_rule_docs.py`

Run: `python tools/generate_rule_docs.py --check`

Expected: both exit `0`; the second command writes nothing.

- [ ] **Step 4: Verify package-resource and all-engine evidence contracts**

Assert through `importlib.resources.files("rtl_lens.knowledge")` that all 60 example resources are readable and `KnowledgeStore.load_default()` returns 30 entries. Wheel/sdist installation is owned by Task 14's packaging gate. If Verilator is absent, record the explicit skips; do not relabel them as passes.

Run: `python -m pytest tests/knowledge tests/unit/test_knowledge.py tests/unit/test_canonical.py -v`

Run with a real pinned Verilator when available: `python -m pytest tests/knowledge/test_rule_examples.py -v`

- [ ] **Step 5: Run the Task 12 completion gate**

Set `RTL_LENS_TEST_CHROMIUM` to the system Chrome path on Windows.

Run: `python -m pytest -q -p no:cacheprovider`

Run: `python -m ruff check --no-cache src tests tools`

Run: `python -m ruff format --check src tests tools`

Run: `python -m mypy src`

Run: `git diff --check`

Expected: all available gates pass; only explicitly documented platform/tool skips remain.

- [ ] **Step 6: Commit generated documentation and evidence**

```bash
git add src/rtl_lens/knowledge/docs.py tools/generate_rule_docs.py docs/rules tests/knowledge/test_rule_docs.py tests/knowledge/test_rule_examples.py tests/unit/test_knowledge.py
git commit -m "docs: generate the bilingual diagnostic catalog"
```

## Preflight Compatibility Rulings

- Ruling: packaged resources remain under `src/rtl_lens/knowledge/examples`, while `tests/fixtures/rules/engine-codes.json` is the independent test oracle. This resolves the older master-plan path inconsistency without duplicating 60 SystemVerilog files. If wrong, installed users could lose example availability or tests could cease to be independent.
- Ruling: PySlang AnalysisManager diagnostics are deferred. Task 12 activates only codes emitted by the current adapter. If wrong, PySlang-only users receive fewer explanations now, but never false canonical labels.
- Ruling: Verilator width codes stay assigned to generic width mismatch and never port width mismatch. If wrong, port-specific reports remain less precise, but ordinary width findings are not misclassified by message parsing.
- Ruling: the unsupported guide ships without an active mapping until the pinned container proves a stable `UNSUPPORTED` fixture. If wrong, users see a guide that is not automatically attached, but unsupported engine errors remain honestly unknown.

## Final Review Gate

After all six tasks pass their task-scoped reviews, generate one review package over the full Task 12 range. A fresh final reviewer must check all 30 entries, the no-guessed-mapping boundary, current-adapter reachability, fixture honesty, generated-doc determinism, Unicode quality, package resources, security of data loading, and all deferred-minor/ruling ledger lines. Task 12 is complete only with no open Critical or Important findings and a clean controller-run completion gate.
