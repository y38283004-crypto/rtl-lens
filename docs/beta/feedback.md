# External beta feedback

## Current status

**Zero external beta installation-and-scan attempts have been collected.** No
invitations have been sent. Outreach is pending separate maintainer approval and is
not implied by the local compatibility or release-candidate evidence.

Participation must be voluntary. A participant is never required to star, follow,
endorse or promote the project. Do not ask a participant to upload private RTL,
credentials, proprietary logs or an unreviewed report. A redacted report is not
automatically safe to share: the participant must review it first and may instead
describe the problem without attaching files. See [Privacy](../privacy.md).

The pinned public-project observations are recorded separately in
[Compatibility](compatibility.md). They are maintainer-run file-subset scans, not
external beta-user attempts.

## Opt-in feedback template

Use this only after outreach has been approved and the participant has opted in.
Every question is optional unless the participant chooses to answer it.

```text
RTL Lens external beta feedback

Platform
- Operating system and version:
- Python version:
- RTL Lens version or exact commit/artifact:
- uv/pip version and installation command:
- PySlang version:
- Verilator version, or "not installed/not used":

Outcome
- Did installation complete? yes / no / not attempted
- Did one scan complete? yes / no / not attempted
- Requested and completed engines shown in report.json:
- Exit code and scan state:
- What was confusing, slow, or otherwise difficult?
- What would have made the first run easier?

Optional reproduction consent
- I consent to sharing a reproduction that I have personally reviewed and sanitized:
  yes / no
- If yes, provide only a minimal synthetic example or public source link. Do not
  upload private RTL, secrets, credentials, proprietary logs, or an unreviewed report.
- May the maintainers quote this feedback publicly, after removing identifying data?
  yes / no

No star, follow, endorsement, or public testimonial is requested or required.
```

Record unsuccessful attempts as unsuccessful; do not discard or relabel them. A
response counts toward the external beta gate only when a real external participant
attempts installation and a scan. Maintainer tests, public-corpus observations and
duplicate attempts by the same participant do not count as additional users.
