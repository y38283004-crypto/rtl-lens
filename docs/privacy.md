# Privacy and local output

RTL Lens runs scans and renders reports locally. It does not send telemetry, make network requests,
or upload source code or reports. Any future remote publication or upload workflow must remain an
explicit opt-in operation and is outside the local scan contract.
Running `rtl-lens scan` requires no account, sign-in, or paid API. Installing RTL Lens and its
dependencies may still require network access; the offline guarantee applies to scanning and
report generation.

Report and baseline paths follow these boundaries:

- relative `output_dir` values must stay beneath the project root;
- relative `--json` and `--html` destinations stay beneath the configured output directory;
- relative `baseline_path` values are read beneath that same output directory;
- explicit absolute report and baseline paths are treated as deliberate user authorization;
- symlinked parents that escape a permitted root at resolution time and existing symlink report
  destinations at write-validation time are rejected.

These checks reject paths that already escape their authorized boundary. They do not defend against
another local process maliciously replacing a parent directory between validation and the atomic
report write (a filesystem TOCTOU race).

Set `scan.redact_sources = true` in `.rtl-lens.toml` to produce shareable JSON and HTML reports.
Shareable output removes source snippets, redacts the project and home paths, and applies both
optional redaction lists. Relative `redact_path_prefixes` entries resolve from the project root.
Only the values of explicitly named, non-empty environment variables are redacted; those secret
values are not part of the validated configuration. Keep non-shareable reports local because they
intentionally retain source snippets and machine-local paths.

For operational choices, see [configuration](configuration.md) and [getting started](getting-started.md).
