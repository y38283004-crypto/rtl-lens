# Task 12 native diagnostic mapping evidence

Date: 2026-08-28

## Scope and evidence standard

This note audits the exact 30 canonical IDs approved for Task 12. A candidate is listed only when an official Verilator warning definition or an official slang diagnostic definition describes the same defect. Similar wording is not treated as proof.

Primary sources:

- [Verilator 5.050 warning reference](https://verilator.org/guide/latest/warnings.html). Verilator explicitly recommends SARIF, rather than parsing display text, for tooling.
- slang diagnostic definitions at pinned commit [`a5ab852`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt). The relevant public lookup is [`DiagnosticEngine::getOptionName`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/include/slang/diagnostics/DiagnosticEngine.h#L151).

Local facts that affect proof:

- PySlang 11.0.0 is installed. An in-memory undeclared-identifier fixture produced option name `""` and string form `DiagCode(UndeclaredIdentifier)`, exactly matching RTL Lens's current fallback path.
- Verilator is not installed on this workstation. All `V` fixtures below are small and documented by Verilator, but must be executed in the pinned CI/container before a mapping is accepted.
- RTL Lens invokes Verilator with `--Wall`, so style diagnostics such as `BLKSEQ`, `DECLFILENAME`, `DEFPARAM`, and `PINCONNECTEMPTY` are reachable once Verilator is available.

Legend: `P` = locally provable with installed PySlang; `V*` = minimal fixture is realistic but currently requires CI/container Verilator; `conditional` = needs multiple declarations/files, a particular form, or several fixtures. `None` means there is no exact first-party native code suitable for a code-only mapping.

## Evidence matrix

| Canonical ID | Verilator candidate(s) | PySlang candidate(s) | Fixture feasibility and mapping status |
|---|---|---|---|
| `width-mismatch` | [`WIDTH`, `WIDTHEXPAND`, `WIDTHTRUNC`, `WIDTHXZEXPAND`](https://verilator.org/guide/latest/warnings.html#width) | [`constant-conversion`, `width-expand`, `width-trunc`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L770-L773), plus [`constant-conversion`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1133) | `P`, `V*`; confirmed family, but Verilator codes also occur on ports, so they cannot simultaneously prove `port-width-mismatch`. |
| `incomplete-assignment` | [`LATCH`](https://verilator.org/guide/latest/warnings.html#latch) | [`inferred-latch`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1254) | `P`, `V*`; direct minimal `always_comb` fixture. |
| `case-incomplete` | [`CASEINCOMPLETE`](https://verilator.org/guide/latest/warnings.html#caseincomplete) | [`case-incomplete`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1266) | `P`, `V*`; direct finite-width case fixture. |
| `case-overlap` | [`CASEOVERLAP`](https://verilator.org/guide/latest/warnings.html#caseoverlap) | [`case-overlap`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1261) | `P`, `V*`; direct wildcard case fixture. |
| `unused-signal` | [`UNUSEDSIGNAL`](https://verilator.org/guide/latest/warnings.html#unusedsignal) | [`unused-net`, `unused-variable`, `unused-port`, `unused-but-set-*`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1216-L1224) | `P`, `V*`, conditional; canonical family intentionally groups several distinct slang codes, so each proposed code needs its own fixture. |
| `undriven-signal` | [`UNDRIVEN`](https://verilator.org/guide/latest/warnings.html#undriven) | [`undriven-net`, `unassigned-variable`, `undriven-port`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1219-L1225) | `P`, `V*`, conditional; three slang subfamilies require separate fixtures. |
| `multiple-drivers` | [`MULTIDRIVEN`](https://verilator.org/guide/latest/warnings.html#multidriven) | [`mixed-var-assigns`, `multiple-cont-assigns`, `multiple-always-assigns`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1274-L1276) | `P`, `V*`, conditional; direct only for the specific driver pattern represented by each code. |
| `blocking-in-sequential` | [`BLKSEQ`](https://verilator.org/guide/latest/warnings.html#blkseq) | None | `V*`; direct clocked-block fixture, style warning enabled by `--Wall`. |
| `always-comb-order` | [`ALWCOMBORDER`](https://verilator.org/guide/latest/warnings.html#alwcomborder) | None | `V*`; direct read-before-later-write `always_comb` fixture. |
| `always-never` | [`ALWNEVER`](https://verilator.org/guide/latest/warnings.html#alwnever) | None | `V*`; direct `always @*` block with no read dependency. |
| `ascending-range` | [`ASCRANGE`](https://verilator.org/guide/latest/warnings.html#ascrange) | None; slang `reversed-range` is a different open-range condition | `V*`; direct `[0:7]` packed-vector fixture. Do not map slang `reversed-range`. |
| `assignment-in-expression` | [`ASSIGNEQEXPR`](https://verilator.org/guide/latest/warnings.html#assigneqexpr) | None; `AssignmentRequiresParens` / `AssignmentNotAllowed` enforce language contexts, not this style family | `V*`; direct complex-expression fixture. |
| `assignment-to-input` | [`ASSIGNIN`](https://verilator.org/guide/latest/warnings.html#assignin) | candidate `DiagCode(InputPortAssign)` from official [`InputPortAssign`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1194) | `P`, `V*`; exact semantics, but observe PySlang's actual fallback string before adding it. |
| `blocking-and-nonblocking` | [`BLKANDNBLK`](https://verilator.org/guide/latest/warnings.html#blkandnblk) | None; slang multiple-driver codes are broader and do not prove blocking/nonblocking mixing | `V*`; direct two-process mixed-assignment fixture. |
| `case-with-x` | [`CASEWITHX`](https://verilator.org/guide/latest/warnings.html#casewithx) | [`case-not-wildcard`, `casez-with-x`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1263-L1264) | `P`, `V*`, conditional; use separate plain-`case` and `casez` fixtures. |
| `case-x` | [`CASEX`](https://verilator.org/guide/latest/warnings.html#casex) | None | `V*`; direct `casex` fixture. |
| `constant-comparison` | [`CMPCONST`](https://verilator.org/guide/latest/warnings.html#cmpconst) | None; slang has type/sign comparison warnings but no documented constant-result equivalent | `V*`; direct one-bit-versus-out-of-range comparison. |
| `combinational-delay` | [`COMBDLY`](https://verilator.org/guide/latest/warnings.html#combdly) | None | `V*`; direct delayed assignment in combinational block. |
| `declaration-filename` | [`DECLFILENAME`](https://verilator.org/guide/latest/warnings.html#declfilename) | None | `V*`, conditional on the real source filename; style warning enabled by `--Wall`. |
| `deprecated-defparam` | [`DEFPARAM`](https://verilator.org/guide/latest/warnings.html#defparam) | None; slang `duplicate-defparam` is a different defect | `V*`; direct defparam fixture, style warning enabled by `--Wall`. |
| `implicit-net` | [`IMPLICIT`](https://verilator.org/guide/latest/warnings.html#implicit) | [`implicit-net`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L580-L581) | `P`, `V*`; direct undeclared net in a legal implicit-net context. |
| `port-width-mismatch` | No distinct code: Verilator reuses `WIDTHEXPAND` / `WIDTHTRUNC` from `WIDTH` | [`port-width-expand`, `port-width-trunc`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L772-L773) | `P`; safe PySlang mapping. Verilator is **not safely mappable** with the current `(engine, code)` key because the same codes also mean non-port width mismatches. |
| `missing-pin` | [`PINMISSING`](https://verilator.org/guide/latest/warnings.html#pinmissing) | [`unconnected-input-port`, `unconnected-output-port`, `unconnected-inout-port`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L571-L573) | `P`, `V*`, conditional by port direction. |
| `empty-pin-connection` | [`PINCONNECTEMPTY`](https://verilator.org/guide/latest/warnings.html#pinconnectempty) | [`empty-input-connection`, `empty-output-connection`, `empty-inout-connection`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L576-L578) | `P`, `V*`, conditional by port direction; Verilator style warning is enabled by `--Wall`. |
| `signedness-mismatch` | [`UNSIGNED`](https://verilator.org/guide/latest/warnings.html#unsigned) covers unsigned comparisons only | [`sign-conversion`, `sign-compare`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L783-L800) | `P`, `V*`, conditional. These are proven subfamilies, not one universal signedness diagnostic; keep scope explicit. |
| `out-of-range-select` | [`SELRANGE`](https://verilator.org/guide/latest/warnings.html#selrange) | [`range-oob`, `range-width-oob`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L779-L780) cover range/part-selects | `P`, `V*`, conditional. PySlang evidence does not establish every bit-select form, so fixtures must match the mapped subcodes. |
| `duplicate-definition` | [`MODDUP`](https://verilator.org/guide/latest/warnings.html#moddup) | [`duplicate-definition`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1031) | `P`, `V*`; requires two same-named definitions, but remains a minimal fixture. |
| `undeclared-identifier` | None: Verilator currently emits a plain `%Error:` without a documented stable warning code | observed `DiagCode(UndeclaredIdentifier)`; official symbol [`UndeclaredIdentifier`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L968) | `P`; exact and locally observed, but the adapter relies on PySlang's string representation because `getOptionName` is empty. Add only with a version-pinned regression fixture. |
| `unsupported-construct` | [`UNSUPPORTED`](https://verilator.org/guide/latest/warnings.html#unsupported) | None; slang has many feature-specific diagnostics but no documented umbrella equivalent | `V*`, fragile: a construct may become supported in a later Verilator. Pin engine version and fixture, or leave unmapped until the release container proves it. |
| `timescale-mismatch` | [`TIMESCALEMOD`](https://verilator.org/guide/latest/warnings.html#timescalemod) | candidate `DiagCode(MissingTimeScale)` from official [`MissingTimeScale`](https://github.com/MikePopoloski/slang/blob/a5ab85255e2a479a0c34d0d3d9cddc8259cfff07/scripts/diagnostics.txt#L1162) | `P`, `V*`, conditional on at least two design elements. Observe PySlang's fallback string before mapping. Do not use `MismatchedTimeScales`, which concerns duplicate timescale declarations. |

## Recommended implementation boundary

1. Add only mappings whose exact emitted code is asserted by a failing fixture and absent from its corrected pair. This report supplies candidates, not permission to bulk-add them.
2. Treat `port-width-mismatch` as PySlang-only unless the canonicalization key gains structured context. Mapping Verilator `WIDTH*` to both width families is impossible without guessing from message text.
3. Keep PySlang error-backed families (`assignment-to-input`, `undeclared-identifier`, `timescale-mismatch`) unknown until a version-pinned test proves the adapter's exact `DiagCode(...)` string. Warning option names are a stronger interface than `DiagCode.__str__`.
4. Validate Verilator-only mappings in the pinned CI/container before merge because this workstation has no Verilator executable.
5. For umbrella families (`unused-signal`, `undriven-signal`, `multiple-drivers`, `signedness-mismatch`, `out-of-range-select`), require one fixture per native subcode and document the narrower semantics; do not infer the family from message text.

