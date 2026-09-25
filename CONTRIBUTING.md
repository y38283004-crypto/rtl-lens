# Contributing to RTL Lens

Thank you for helping make RTL Lens more useful and trustworthy. This project is
currently pre-release; keep contributions focused, reviewable, and accompanied
by reproducible evidence.

## Before opening an issue or pull request

Read the [Code of Conduct](CODE_OF_CONDUCT.md), [security policy](SECURITY.md),
and [maintenance policy](docs/maintenance.md). Security vulnerabilities and
conduct reports must not go through public issues or forms: use GitHub
**Security → Advisories → Report a vulnerability** instead.

## Setup

Use Python 3.11–3.13 and the repository's pinned `uv` toolchain. From a clean
checkout, run:

```powershell
uv sync --group dev
uv run rtl-lens doctor .
```

Do not treat an unknown diagnostic as a known rule. Include the unmodified
engine output with secrets and private information redacted, and explain what
is unknown; do not guess, suppress, or relabel a
diagnostic merely to make a report appear complete.

## Test-driven changes

Follow TDD: write or extend a focused test first, run it to observe the
expected failure, make the smallest change, then rerun it to observe GREEN.
Run the focused gate for the code you changed and record its command and
result. Before requesting review, run the full applicable suite:

```powershell
uv run pytest --ignore=tests/browser -q -p no:cacheprovider
uv run ruff check --no-cache src tests tools
uv run ruff format --check src tests tools
```

## Rules and diagnostics

Rule changes require the rule YAML, a failing fixture, a fixed fixture, and
tests that demonstrate both outcomes. Regenerate or verify generated rule
documentation before review:

```powershell
uv run python tools/generate_rule_docs.py --check
```

For a new diagnostic mapping, include the engine/version, source evidence or
upstream documentation, a minimal sanitized RTL reproduction, and the intended
user-facing explanation. For a false positive, include the smallest fixed RTL
example that demonstrates the intended behavior.

## Documentation and translations

Update English documentation whenever a public CLI, configuration, report
schema, or rule behavior changes. Update the Simplified Chinese translation in
the same pull request, or explicitly identify the translation follow-up for
review. Translation review checks technical meaning, commands, links, and
terminology rather than literal word-for-word matching.

## License for contributions

By submitting a contribution, you agree that it is licensed under
[Apache-2.0](LICENSE), unless a maintainer has agreed in writing to a different
arrangement before submission.
