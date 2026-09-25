# RTL Lens

Explainable, offline diagnostics for Verilog and SystemVerilog projects. RTL Lens is in
pre-release development; its public interface may change before a stable release.
This English README is the canonical user-documentation source of truth. For a Simplified Chinese
mirror of the same core contract, see [简体中文说明](README.zh-CN.md).

## Installation

RTL Lens is installed from a source checkout, not from PyPI. Install [uv 0.12.7](https://docs.astral.sh/uv/),
then, at the repository root, run:

```powershell
uv sync --locked --all-groups
```

Use `uv run rtl-lens ...` for every command below. Supported local runtimes are
`Python >=3.11,<3.14` and `PySlang >=11,<12`. Dual-engine use additionally needs
`Verilator >=5.040` available on `PATH`. The project is licensed under `Apache-2.0`.

## Quick start

Create and review a configuration, check the local environment, and scan the project:

```powershell
uv run rtl-lens init .
uv run rtl-lens doctor .
uv run rtl-lens scan .
uv run rtl-lens explain width-mismatch
uv run rtl-lens version
```

The command names are `rtl-lens init .`, `rtl-lens doctor .`, `rtl-lens scan .`,
`rtl-lens explain width-mismatch`, and `rtl-lens version`; `uv run` selects the source
checkout environment. `scan` always renders terminal output plus JSON and self-contained HTML
reports in the configured output directory.

<!-- rtl-lens-config-example:start -->
[scan]
source_roots = ["src"]
include_dirs = []
defines = []
top_modules = ["top"]
timeout = 30
language = "en"
engine_mode = "disabled"
output_dir = ".rtl-lens"
# Optional after the first successful scan:
# baseline_path = "baseline.json"
redact_sources = false
redact_path_prefixes = []
redact_environment_variables = []
fail_on = "error"
graph_display_limit = 200
<!-- rtl-lens-config-example:end -->

This portable PySlang-only configuration sets `engine_mode = "disabled"`. For a local
dual-engine scan, set it to `"auto"` or `"required"` and install Verilator. `auto` can emit a
partial report when optional Verilator is unavailable; `required` fails instead. Configuration
precedence is defaults < `.rtl-lens.toml`/`--config` < explicit CLI `--fail-on`.
Keep `baseline_path` commented out until you have a saved prior report to compare against.

![Redacted report preview](docs/assets/report-preview.png)

Read the [getting-started guide](docs/getting-started.md), [configuration reference](docs/configuration.md),
[architecture overview](docs/architecture.md), [privacy guide](docs/privacy.md), and
[rule catalog](docs/rules/index.md), [contribution guide](CONTRIBUTING.md),
[security policy](SECURITY.md), [Code of Conduct](CODE_OF_CONDUCT.md), and
[maintenance policy](docs/maintenance.md).

## Privacy

RTL Lens runs scans and renders reports locally. It does not send telemetry, make network
requests, or upload source code or reports. Any future remote publication or upload workflow
must remain an explicit opt-in operation and is outside the local scan contract.
Running a scan requires no account, sign-in, or paid API. Installing RTL Lens and its dependencies
may still require network access; the offline guarantee applies to scanning and report generation.

Reports remain local and unredacted unless you enable redaction. Set `scan.redact_sources = true`
to remove source snippets, redact project and home paths, and apply named path and environment
value redaction. Keep non-shareable reports local because they intentionally retain source snippets
and machine-local paths. See [privacy](docs/privacy.md) for the full boundary and sharing guidance.

## Limitations

RTL Lens is an offline development tool, not a proof of design correctness. PySlang is required;
Verilator is optional only in `auto` mode. An `auto` scan can be partial without Verilator, and
diagnostic coverage varies by language feature and analyzer support. Exit codes are: 0 success,
1 policy block, 2 runtime or required-engine failure, and 3 invalid project or configuration.
Malformed Typer syntax uses 2 before application logic.

## Contributing

This pre-release repository welcomes focused issues and changes. Follow the
[contribution guide](CONTRIBUTING.md), [security policy](SECURITY.md),
[Code of Conduct](CODE_OF_CONDUCT.md), and [maintenance policy](docs/maintenance.md); do not
publish packages, describe version 0.2 as released, or trigger remote workflows from this checkout.
