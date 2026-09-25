# Task 15 Documentation and Governance Primary-Source Research

Date: 2026-08-31

## Decision summary

- Add the unmodified canonical Apache License 2.0 text as top-level `LICENSE`; keep the
  `Apache-2.0` SPDX expression already used by `pyproject.toml`.
- Do not copy ASF-specific headers or an ASF-specific `NOTICE`. For a non-ASF project, a
  `NOTICE` is optional unless the work or bundled material has attribution notices that must be
  propagated. If RTL Lens adds one, keep it factual and limited to legally relevant attribution.
- Adopt Contributor Covenant **3.0**, which the official site and adoption builder identify as
  the latest English and Simplified Chinese version as of this date. Customize its reporting
  instructions before merging; never leave the template note or direct conduct reports to a
  public issue.
- Use two structured Issue Forms (bug and feature), a private security contact link, and one
  default pull-request template.
- Keep every verification workflow at `permissions: contents: read`, pin external Actions to full
  commit SHAs, and disable checkout credential persistence.
- Define `release-check` as build and verification only. It may retain a short-lived GitHub Actions
  workflow artifact for maintainer inspection, but it must never create a GitHub Release, publish
  to a package/container registry, deploy, attest, or receive any publishing credential.

## Apache License 2.0 and NOTICE

Apache identifies Version 2.0 (January 2004) as its current license and publishes the canonical
plain-text copy. RTL Lens should copy that text unchanged into `LICENSE`; a translated copy may be
provided only as non-binding convenience because the English text remains authoritative.

- [Canonical Apache License 2.0 text](https://www.apache.org/licenses/LICENSE-2.0.txt)
- [Apache licensing FAQ: applying the license and translations](https://www.apache.org/foundation/license-faq.html)

Section 4 requires a redistributor to give recipients a copy of the license, mark modified files,
and preserve pertinent copyright, patent, trademark, and attribution notices. If the original work
contains a `NOTICE`, a derivative distribution must retain the pertinent attribution notices in a
readable permitted location. The `NOTICE` is informational and cannot modify the license.

- [Apache License 2.0, redistribution and NOTICE terms](https://www.apache.org/licenses/LICENSE-2.0.html#redistribution)

Apache's FAQ tells non-ASF licensors to include a license copy, usually named `LICENSE`, and to
*consider* a `NOTICE`. It also offers either the full per-file boilerplate or a short copyright plus
`SPDX-License-Identifier: Apache-2.0` header. Those per-file headers are useful when files may be
detached, but the ASF-specific source header exists for ASF's CLA process and must not be copied
into RTL Lens.

- [Apache FAQ: how to apply Apache-2.0 to your own software](https://www.apache.org/foundation/license-faq.html#how-should-i-apply-the-apache-license-to-my-own-software)

The important distinction is that ASF policy requires every ASF distribution to carry an ASF
`NOTICE`; that organizational rule is not an extra condition imposed on every unrelated
Apache-2.0 project. Apache's own assembly guidance says `NOTICE` should represent only the bits
actually distributed, carry only legally required notices, and stay brief. RTL Lens therefore
must not add the ASF attribution line or an invented copyright owner. Add a project `NOTICE` only
after the maintainer supplies the correct owner/attribution or a bundled component requires notice
propagation.

- [ASF assembly guide: policy scope and legally required NOTICE content](https://infra.apache.org/licensing-howto.html)

## Contributor Covenant 3.0

The official Contributor Covenant site's **Latest Version** link resolves to 3.0, and its adoption
builder lists English and Simplified Chinese as 3.0. The GitHub repository's Releases UI still
marks 2.1 as its latest GitHub Release, so that stale release badge must not override the project's
own current website and builder. RTL Lens should adopt the official 3.0 Markdown template.

- [Official latest-version destination: Contributor Covenant 3.0](https://www.contributor-covenant.org/version/3/0/)
- [Official 3.0 Code of Conduct template](https://www.contributor-covenant.org/version/3/0/code_of_conduct/)
- [Official adoption builder and available versions](https://www.contributor-covenant.org/adopt/)

Version 3.0 deliberately leaves a reporting placeholder and an enforcement customization note.
Before adding `CODE_OF_CONDUCT.md`, replace the reporting placeholder with a maintainer-controlled,
non-public channel and decide who receives and enforces reports. Do not invent or publish a personal
address without the owner's approval. Preserve the template's 3.0 attribution and CC BY-SA 4.0
notice. A public Issue Form is suitable for bugs and features, not confidential conduct reports.

## GitHub community templates

Issue Forms belong on the default branch under `.github/ISSUE_TEMPLATE/*.yml`. GitHub's schema
supports structured inputs and `required` validation. For RTL Lens, use `bug.yml`, `feature.yml`,
and `config.yml`; set `blank_issues_enabled: false`, and route vulnerabilities through a
`contact_links` entry to `SECURITY.md` or GitHub private vulnerability reporting rather than a
public bug report.

- [About issue and pull-request templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)
- [Issue Form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema)
- [Issue-template configuration](https://docs.github.com/en/enterprise-cloud@latest/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
- [Common Issue Form validation errors](https://docs.github.com/en/enterprise-cloud@latest/communities/using-templates-to-encourage-useful-issues-and-pull-requests/common-validation-errors-when-creating-issue-forms)

The bug form should require the RTL Lens version, operating system, Python and Verilator versions,
reproduction steps, expected and actual behavior, a minimal RTL example, and sanitized logs. The
feature form should collect the motivating problem, proposed result, alternatives, and willingness
to contribute. Any auto-applied labels must already exist or GitHub will not apply them.

Use one default `.github/pull_request_template.md` for the first public release. GitHub supports a
single template in `.github`, the repository root, or `docs`; multiple templates require a template
directory and usually a query parameter, which adds unnecessary choice for a new project. The
template should request scope, linked issue, verification commands/results, CLI/API/report-format
impact, documentation and compatibility notes, and security/supply-chain impact.

- [Creating a pull-request template](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)
- [Template-selection query parameters](https://docs.github.com/en/pull-requests/reference/using-query-parameters-to-create-a-pull-request)

## GitHub Actions permissions and immutable dependencies

GitHub documents that once any `permissions` scope is declared, every omitted scope becomes
`none`. A checkout-only build therefore needs only:

```yaml
permissions:
  contents: read
```

- [Workflow syntax: `permissions`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)

Actions can access the token through `github.token` even if a workflow author does not explicitly
pass the secret. The release check must therefore rely on minimal permissions, must not receive
repository/environment publishing secrets, and must use `persist-credentials: false` for checkout.
GitHub identifies a full commit SHA as the only immutable Action reference.

- [Using `GITHUB_TOKEN`](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token)
- [Secure-use reference: least privilege and full-SHA pins](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions)

Verified official release pins as of 2026-08-31:

| Action | Selected release | Full commit SHA | Use in Task 15 |
|---|---:|---|---|
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | Yes |
| `actions/upload-artifact` | `v7.0.1` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | Optional short-lived check artifact |
| `actions/download-artifact` | `v8.0.1` | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` | Only if a separate verification job needs it |
| `actions/attest` | `v4.2.1` | `508db95dd578ae2727ebd6217d5ba78e4fbda05d` | **No**; publishing provenance is out of scope |

- [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1)
- [upload-artifact v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1)
- [download-artifact v8.0.1](https://github.com/actions/download-artifact/releases/tag/v8.0.1)
- [attest v4.2.1](https://github.com/actions/attest/releases/tag/v4.2.1)

For workflow artifacts, use a unique name containing the commit SHA,
`if-no-files-found: error`, a short retention such as seven days, and explicit `dist/*.whl` and
`dist/*.tar.gz` paths. Do not enable hidden-file upload. If artifacts are downloaded, retain v8's
default failure on digest mismatch and treat artifacts originating from untrusted code as data,
never as executable input.

- [upload-artifact inputs, immutability, retention, and hidden-file guidance](https://github.com/actions/upload-artifact)
- [download-artifact usage and digest verification](https://github.com/actions/download-artifact)
- [GitHub workflow-artifact concept](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)

Artifact attestations are designed to establish provenance for software people will release and
consume. GitHub advises against generating them for frequent CI builds, source files, documents,
and images. Generating one uploads it to GitHub and requires `id-token: write` plus
`attestations: write`; those permissions and `actions/attest` must remain absent from this
build-only workflow. They belong only in a future, independently approved publication workflow.

- [When to generate artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations#when-to-generate-attestations)
- [Attestation permissions and workflow](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)

## Safe triggers and untrusted contributions

Use ordinary `pull_request` for contributor validation, `push` limited to the protected default
branch, and optionally `workflow_dispatch` for a maintainer-requested release check. Fork pull
requests receive no repository secrets and a read-only token by default. Do not switch a build job
to `pull_request_target`: GitHub warns that checking out and executing fork code in that privileged
event can expose base-repository credentials. Similarly, do not use a privileged `workflow_run` to
download and execute an untrusted upstream artifact.

- [Events and fork pull-request restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflows-in-forked-repositories)
- [Secure use of `pull_request_target` and `workflow_run`](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target)

PR titles, bodies, branch names, labels, and similar GitHub context values are attacker-controlled.
Do not interpolate them directly into generated shell scripts; pass any necessary value through a
quoted environment variable and validate it before use.

- [GitHub Actions script-injection guidance](https://docs.github.com/en/actions/concepts/security/script-injections)

## uv build, installation, and lock verification

Retain the project's reproducibility pins, uv `0.12.7` and `uv_build>=0.12.7,<0.13`; this is a
project selection, not a claim that 0.12.7 will remain the latest uv. The official `setup-uv`
release selected by the existing automation is `v10.0.1` at full SHA
`20cfd1bf945f4377ade1205e4dbc17946fc9a30d`.

- [setup-uv v10.0.1](https://github.com/astral-sh/setup-uv/releases/tag/v10.0.1)
- [Official uv installation options](https://docs.astral.sh/uv/getting-started/installation/)

Astral documents `uv lock --check` as checking that the lock matches project metadata; it is
equivalent to locked mode and fails rather than updating an outdated lock. `uv build` creates an
sdist and then builds the wheel from that sdist. For a publication-like check, Astral recommends
`uv build --no-sources` so local/workspace source overrides cannot conceal packaging defects.

- [Lock checking and locked mode](https://docs.astral.sh/uv/concepts/projects/sync/#checking-the-lockfile)
- [Building distributions](https://docs.astral.sh/uv/concepts/projects/build/)
- [Why publication checks should use `--no-sources`](https://docs.astral.sh/uv/guides/package/#building-your-package)

The release check must test the built wheel, not an editable source installation. Use a clean
virtual environment, install the wheel into that environment, execute the CLI and package-resource
checks from outside the source tree, then run `uv pip check`. Astral documents virtual environments
as the default isolation boundary, `--python` for an explicit target environment, and `uv pip check`
for missing/incompatible dependencies and invalid metadata.

- [Creating and targeting virtual environments](https://docs.astral.sh/uv/pip/environments/)
- [`uv pip check` diagnostics](https://docs.astral.sh/uv/pip/compatibility/#pip-check)

## Build-only, never-publish release-check contract

The implementation contract is deliberately narrower than a release workflow:

1. Trigger on ordinary `pull_request`, protected-default-branch `push`, or manual
   `workflow_dispatch`; never use `pull_request_target`, a privileged `workflow_run`, or
   `release: published`.
2. Set only `permissions: contents: read`; checkout with the full SHA and
   `persist-credentials: false`.
3. Install the pinned uv, run `uv lock --check`, run the package tests, then
   `uv build --no-sources`.
4. Assert exactly the expected wheel and sdist, inspect their license/package-resource contents,
   install the wheel into a clean environment, run `uv pip check`, run `rtl-lens --help`, and import
   required packaged data from outside the checkout.
5. Generate checksums locally for inspection. If the project keeps workflow artifacts, upload only
   the explicit wheel, sdist, and checksum file with a unique check-only name and seven-day
   retention. This is remote Actions storage, not a GitHub Release or registry publication; omit
   even this step if the policy requires zero remote artifact storage.
6. Do not define or reference a GitHub environment, PAT, GitHub App key, PyPI token, registry token,
   signing key, or cloud credential. Do not grant `contents: write`, `packages: write`,
   `attestations: write`, `artifact-metadata: write`, or `id-token: write`.
7. The workflow and its transitive Actions must contain no `uv publish`, `twine upload`,
   `gh release create/upload`, `docker push`, registry login, Pages, deployment, or attestation
   step.
8. A future real publication must be a separate workflow with separate review, approval,
   credentials, and permissions. Never add a Boolean input that can turn this check workflow into a
   publisher.

This boundary makes accidental publication structurally impossible: verification has neither a
publishing command nor a credential or permission capable of authorizing one.
