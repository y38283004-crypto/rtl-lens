# Getting started

RTL Lens is a source-checkout, pre-release tool. Install uv 0.12.7 and run
`uv sync --locked --all-groups` from the repository root. Invoke the installed local command as
`uv run rtl-lens ...`; it is not a PyPI installation workflow.

## First scan

1. Arrange RTL below `src/`, then run `uv run rtl-lens init .`.
2. Review `.rtl-lens.toml`; use `engine_mode = "disabled"` for portable PySlang-only work.
3. Run `uv run rtl-lens doctor .` to check Python, PySlang, the configuration, and optional tools.
4. Run `uv run rtl-lens scan .`. It renders terminal output and writes JSON plus self-contained HTML.
5. Use `uv run rtl-lens explain width-mismatch` for a bilingual rule explanation and
   `uv run rtl-lens version` for analyzer compatibility.

For dual-engine local analysis, install `Verilator >=5.040` on `PATH` and choose `auto` or
`required`. `auto` may return a partial report when Verilator is absent; `required` fails. See the
[configuration reference](configuration.md), [rule catalog](rules/index.md), and [privacy guide](privacy.md).
