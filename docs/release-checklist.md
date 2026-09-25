# Release checklist

This checklist records evidence; it does not authorize publication. RTL Lens is
**not release-ready** while mandatory external and platform gates remain open.

Status meanings:

- **PASSED** — the named check ran and satisfied its stated acceptance criteria.
- **FAILED** — the check ran and did not satisfy its acceptance criteria; preserve
  the failure until it is resolved and rerun.
- **NOT RUN — OPEN** — no qualifying result exists. Absence of a tool, credential,
  participant, approval or remote run is not a pass.

## Evidence recorded locally

| Gate | Status | Evidence and limits |
| --- | --- | --- |
| Installed wheel scan | PASSED | A wheel built with `uv build --no-sources` was installed into its own temporary environment. `uv pip check`, isolated `python -I` import-origin proof, and the installed `rtl-lens` console scan all passed on a clean one-file fixture outside the checkout. The report used PySlang only, was complete and redacted, contained no findings, and produced self-contained JSON/HTML. |
| Installed source-distribution scan | PASSED | The independently installed sdist passed the same dependency, import-origin, console-scan, report and offline-HTML assertions in a separate temporary environment. |
| Pinned public RTL file subsets | PASSED | On 2026-09-15, the offline runner completed all 10 manifest entries: 28 selected Verilog files, 157 findings and 102 unknown diagnostics. Every entry returned exit 0, `complete`, `redacted=true`, requested/completed `pyslang`, and no runner failure. See [Compatibility](beta/compatibility.md). |

The ten compatibility entries are **file-subset analysis observations**, not ten
whole-project certifications and not external beta users. They cover three
maintainer groups and Verilog inputs only. They do not establish simulation,
synthesis, timing, hardware correctness, false-positive adjudication, broad
SystemVerilog support, performance superiority, whole-repository compatibility, or
Verilator/container compatibility.

## Mandatory gates still open

| Gate | Status | What remains |
| --- | --- | --- |
| Fresh actual-browser verification | FAILED — OPEN (host environment) | The 2026-09-19 attempt failed during test collection with Windows `WinError 10106` while importing Python `_overlapped`. A minimal `asyncio` import reproduced the error again on 2026-09-25, including outside the sandbox. Restore a working Python/Winsock environment and rerun `python -m pytest tests/browser -q -p no:cacheprovider` with an actual browser. The earlier six passing browser tests remain historical evidence only. |
| Docker plus pinned Verilator execution | NOT RUN — OPEN | Docker and Verilator were absent on the observation host. Run the pinned dual-engine/container path on a supported host; PySlang-only evidence cannot close this gate. |
| Remote CI | NOT RUN — OPEN | Obtain a successful run of the required remote workflows for the exact candidate commit. Local checks are not a substitute. |
| Ten external beta users | NOT RUN — OPEN | 0 of 10 external users have attempted installation and a scan. Invitations require separate approval; see [External beta feedback](beta/feedback.md). |
| Private security reporting | NOT RUN — OPEN | Confirm that the repository's private vulnerability-reporting route is actually enabled and usable. Documentation alone does not activate it. |
| Demo and case studies | NOT RUN — OPEN | Review and approve any publishable demo and case-study evidence. Local ignored reports are not a hosted demo. |
| Package-name availability | NOT RUN — OPEN | Check the intended package registry immediately before publication; no name reservation or availability claim is recorded here. |
| Publication approval | NOT RUN — OPEN | Obtain explicit maintainer approval for the exact artifacts and version before any upload, tag, workflow dispatch or public release. |

## Final candidate checks

Before publication, record fresh results for the full lint, format, typing,
non-browser coverage, actual-browser, lock, build, artifact-content and checksum
gates. Each result must be marked **PASSED**, **FAILED**, or **NOT RUN — OPEN** with
the exact candidate commit and command. Do not infer those results from this focused
installed-artifact check, and do not replace an adverse result with a later run
without retaining the earlier observation.
