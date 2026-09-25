# Configuration

RTL Lens validates one `[scan]` table. Effective values are loaded in this order:

1. built-in defaults;
2. one TOML file: `<project>/.rtl-lens.toml`, or the file selected by `scan --config` instead;
3. the explicit `scan --fail-on` CLI override, when supplied.

`--json` and `--html` select report destinations; they do not change the validated configuration.
Unknown tables or keys are rejected. The command `uv run rtl-lens init .` creates a smaller reviewed
starter file; omitted fields continue to use the defaults below.

## Scan settings

| Field | TOML type | Default | Meaning and constraints |
| --- | --- | --- | --- |
| `source_roots` | array of paths | `["."]` | Directories searched recursively for `.v` and `.sv` files. Relative entries are resolved from the project root. Discovery stays inside that root and skips missing, escaping, generated, and ignored directories. |
| `include_dirs` | array of paths | `[]` | User include directories passed to both analyzers. Relative entries are resolved from the project root. |
| `defines` | array of strings | `[]` | Preprocessor definitions in `NAME` or `NAME=value` form, without a leading `-D`; each string is passed as a PySlang predefine and as one Verilator `-D...` argument. |
| `top_modules` | array of strings | `[]` | Explicit top-level definition names for PySlang compilation. An empty list leaves top selection to PySlang. Verilator does not consume this setting. |
| `timeout` | integer | `30` | Per-engine timeout in seconds. Must be greater than zero. |
| `language` | string | `"en"` | Curated-explanation locale: `"en"` or `"zh-CN"`. There is no fallback for another locale: unsupported values are configuration errors. Diagnostics without a matching curated rule remain visible under an `engine-native:<engine>:<code>` identity and have no curated explanation. HTML includes both reviewed languages for matched explanations. |
| `engine_mode` | string | `"auto"` | Controls Verilator only: `"disabled"` omits it, `"auto"` treats it as optional, and `"required"` makes its absence or failure fatal. PySlang is always selected and required. |
| `output_dir` | path | `".rtl-lens"` | Root for generated reports. A relative value resolves beneath the project root and may not escape it; an explicit absolute value is treated as deliberate authorization. Default report names are `report.json` and `report.html`. |
| `baseline_path` | path or omitted | omitted (`None`) | Existing JSON report to compare. A relative value resolves beneath `output_dir` and may not escape it; an explicit absolute value is treated as deliberate authorization. The file must exist, validate as a scan report, and be at most 16 MiB. |
| `redact_sources` | boolean | `false` | Enables shareable-output redaction, including removal of source snippets and path/value redaction. See [privacy](privacy.md) for the exact boundary. |
| `redact_path_prefixes` | array of paths | `[]` | Additional path prefixes redacted when `redact_sources` is enabled. Relative entries are resolved from the project root. |
| `redact_environment_variables` | array of strings | `[]` | Names of environment variables whose non-empty values are redacted when `redact_sources` is enabled. Names must match `[A-Za-z_][A-Za-z0-9_]*`; duplicates are normalized. |
| `fail_on` | string | `"error"` | Lowest severity that blocks policy: `"info"`, `"warning"`, or `"error"`. Only **new** findings at or above the threshold cause policy exit 1; findings already present in the baseline do not. |
| `graph_display_limit` | integer | `200` | Maximum module-graph edges displayed in HTML. Valid range: 1 through 2000 inclusive; it does not truncate the JSON report's graph. |

`engine_mode = "disabled"` is the portable PySlang-only path. `"auto"` runs Verilator when
available and can emit a partial report without it. `"required"` requires `Verilator >=5.040` on
`PATH` and fails if that engine cannot run. In every mode, PySlang remains a required dependency.

See [privacy](privacy.md) before sharing reports or enabling source redaction.

## Baseline workflow

Run the first scan without `baseline_path`, then preserve its generated JSON report as a separate
file under the output directory (for example, `.rtl-lens/baseline.json`). Only after that file
exists should you set `baseline_path = "baseline.json"` and run later scans. Pointing the first scan
at a missing baseline is an invalid configuration, and using `report.json` itself as the baseline
would lose the prior snapshot when the next report is written.

Current findings are classified as new or existing from the loaded baseline. A finding can be
reported as resolved only when the baseline and current scan are both complete and each has the
same requested and completed engine set. If either report is partial or failed, or the engine sets
differ, resolution is unknown and resolved fingerprints are withheld; an empty resolved list must
not be read as proof that nothing was fixed.

## Exit codes

`scan` returns 0 for success, 1 when policy blocks, 2 for a runtime or required-engine failure,
and 3 for an invalid project or configuration. Malformed Typer command syntax returns 2 before
application logic runs.
