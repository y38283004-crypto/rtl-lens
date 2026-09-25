# Architecture

RTL Lens resolves project sources, loads a validated `ProjectConfig`, runs PySlang and optionally
Verilator, merges diagnostics into canonical rules, then renders terminal, JSON, and self-contained
HTML reports. The public CLI is `rtl_lens.cli.app`; configuration is loaded by
`rtl_lens.config.load_config`.

PySlang is required. The Verilator adapter is disabled, optional (`auto`), or mandatory
(`required`) according to configuration. An optional-engine failure can make an `auto` report
partial; a required-engine failure is a runtime failure. Rule explanations are packaged in the
[rule catalog](rules/index.md) and are available in English and Simplified Chinese.

Output destinations are checked before reports are written. Read [privacy](privacy.md) for the
authorization boundary and filesystem race limitation, and [configuration](configuration.md) for
the settings that shape a scan.
