# Task 13 security-hardening research

## Scope

This note resolves the security/runtime assumptions behind the approved Task 13 contract. It combines primary documentation with an audit of the current `9c9e39e` implementation. It does not expand the product into networking, telemetry, sandboxing, or secret storage.

## Primary-source findings

### Subprocess output and timeout handling

- Python documents that `subprocess.run(..., capture_output=True)` creates `PIPE` streams and buffers the captured output. Its timeout is implemented through `Popen.communicate()`.
- Python explicitly warns that `Popen.communicate()` buffers data in memory and should not be used when output is large or unlimited.
- Python also warns that waiting on a process with unread `PIPE` streams can deadlock. Both stdout and stderr therefore need concurrent draining when separate pipes are used.
- A timed-out `Popen.communicate()` does not kill the child automatically; cleanup requires killing the process and completing communication. Task 13's custom runner must likewise kill, wait, and join every reader path.

Primary source: https://docs.python.org/3/library/subprocess.html

### Path normalization and boundary checks

- `Path.resolve()` makes a path absolute, resolves symlinks, and eliminates `..` components.
- `PurePath.is_relative_to()` is lexical/string-based and does not resolve symlinks or treat `..` specially. Boundary code must resolve the candidate and boundary first, then compare them.
- Nonexistent destination leaves can use `resolve(strict=False)`, but existing symlink leaves and symlinked parents require explicit refusal/boundary checks before atomic writing.

Primary source: https://docs.python.org/3/library/pathlib.html

### Temporary files and atomic replacement

- Python's `TemporaryFile`, `NamedTemporaryFile`, `TemporaryDirectory`, and `mkstemp()` use secure creation rules; `mktemp()` is unsafe and must not be used.
- `os.replace()` is the documented cross-platform overwrite primitive and is atomic where the platform/filesystem guarantees the underlying rename. The current same-directory `mkstemp()` plus `os.replace()` design should be retained.

Primary sources:

- https://docs.python.org/3/library/tempfile.html
- https://docs.python.org/3/library/os.html#os.replace

### HTML autoescaping

- Jinja does not enable autoescape globally by default; its documentation recommends explicit configuration.
- `select_autoescape()` is the recommended filename-aware configuration. The current environment sets HTML/Jinja extensions and both defaults to true, so Task 13 should preserve it and test every hostile context rather than replace the renderer.

Primary source: https://jinja.palletsprojects.com/en/stable/api/#jinja2.select_autoescape

## Current implementation audit

| Contract area | Current evidence | Remaining gap |
|---|---|---|
| Shell safety | Verilator uses argv lists and `shell=False`; real fake-executable tests preserve metacharacters | Move the proof to Task 13 security coverage and preserve it through the runner refactor |
| Timeout | `subprocess.run(timeout=...)` produces a structured `timeout` failure | Custom bounded capture must still kill and reap on every timeout/overflow path |
| Output bound | stdout/stderr are rejected after 1 MiB; SARIF is read with a 16 MiB cap | `capture_output=True` can allocate beyond the limit before the check |
| Source paths | project discovery, `ResolvedProject`, Verilator validation, and SARIF parsing reject resolved escapes | Consolidate adversarial coverage; avoid weakening the existing behavior |
| Report paths | atomic writers use same-directory secure temporary files | Relative overrides can traverse and are not rooted beneath configured `output_dir`; direct writers do not reject destination symlinks |
| Baseline path | 16 MiB bounded read | Relative baseline currently resolves from project root, contrary to Task 13's output-root wording |
| HTML injection | explicit autoescape, offline CSP, no remote assets, hostile-context tests | Shareable redaction must occur before both HTML template data and embedded JSON are rendered |
| Source privacy | `redact_sources=true` removes snippets | Absolute home/project/configured paths and explicitly marked environment values remain in metadata/messages/failures |
| Large reports | deterministic renderers and graph-display limit exist | No explicit 500-diagnostic/5-second regression ceiling |

## Binding design rulings

1. **Relative output roots are project-confined.** A relative `output_dir` resolves beneath the project root; `..` or symlink escape is rejected. An absolute `output_dir` is an explicit user-selected root.
2. **Relative report overrides are output-root-relative.** `--json foo.json` and `--html nested/foo.html` resolve beneath the configured output root. A relative traversal is rejected. An explicit absolute override remains allowed.
3. **Relative baselines are output-root-relative.** This follows the approved Task 13 contract. Existing tests that intend a project-root fixture must use an explicit absolute path. No compatibility fallback silently searches both locations.
4. **Direct writers reject leaf symlinks.** Boundary-aware resolution belongs in the CLI/service layer; the atomic writers additionally refuse an existing symlink destination and require a real directory parent.
5. **Shareable mode is explicit and model-preserving.** `report.metadata.redacted` activates default home redaction. A renderer policy can additionally name path prefixes and secret environment variables. Redaction returns a deep validated copy and sets `metadata.redacted=true`; input models are never mutated.
6. **Secret environment values are explicitly named.** New configuration contains environment-variable names, not secret values. Only the values of those exact names are redacted; no heuristic token/password scan is used. Values are never placed in the report or configuration digest.
7. **Redaction covers every user/tool-controlled report string.** Home, project/configured prefixes, and named secret values are replaced before JSON serialization or HTML rendering in metadata paths, locations, diagnostic titles/messages/symbols/codes/versions, provenance, engine failures, graph names, analysis warnings, and embedded report JSON. RTL Lens-owned structural enums, schema versions, fingerprints, canonical IDs, timestamps, and digests are not rewritten because they contain no raw external value and must remain schema-valid. Source snippets remain omitted in shareable mode.
8. **Bounded Verilator capture uses concurrent binary readers.** Both pipes are drained concurrently into fixed-size buffers. Overflow kills the child immediately, preserves only the bounded prefix plus a visible truncation marker, then waits and joins readers. Timeout follows the same cleanup path. `subprocess.run(capture_output=True)` is removed from production adapter execution.
9. **Existing failure taxonomy is preserved where already sufficient.** `timeout`, `stdout_limit_exceeded`, `stderr_limit_exceeded`, SARIF failures, and `FileNotFoundError` are already distinguishable. Task 13 will not rename stable kinds without a security reason.
10. **The performance ceiling is a regression guard.** JSON plus HTML rendering of exactly 500 representative diagnostics must each complete under five seconds on the reference runner; documentation must not market this as a general benchmark.
