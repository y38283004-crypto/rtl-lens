# Maintenance Policy

RTL Lens is maintained as a pre-release project. The practices below describe
review targets, not service-level agreements or a guarantee of response,
feature delivery, compatibility, or security remediation.

## Triage and review cadence

Weekly triage covers new issues, false positives, rule requests, and private
security intake. Monthly dependency review covers updates, available security
information, and CI health. During repository setup, maintainers should enable
GitHub private vulnerability reporting and verify that Security → Advisories →
Report a vulnerability is available for both security and private conduct intake.

The following are proposed triage labels for repository setup; their inclusion
here does not claim that labels already exist: `bug`, `false-positive`,
`rule-request`, `enhancement`, `documentation`, `translation`, `security`, and
`needs-reproduction`.

## 30/60/90-day routines

### 30 days

Review weekly issue intake, dependency changes, and private security reports.
Confirm that new bug reports have a reproduction and that reporting guidance is
still accurate.

### 60 days

Review rule documentation, Simplified Chinese translations, recurring false
positives, and unknown-diagnostic evidence. Prioritize fixes with small,
sanitized reproductions and useful user impact.

### 90 days

Review compatibility evidence, stale dependencies, CI reliability, and whether
the project is ready for a separately approved release decision. Do not infer a
release from this routine alone.

## Healthy project growth

Maintainership does not buy, exchange, bot, coerce, or otherwise manipulate
stars. Adoption evidence, reproducible successful scans, issue quality, and
useful contributions are more meaningful than star counts. There is no
guarantee of support or feature acceptance.
