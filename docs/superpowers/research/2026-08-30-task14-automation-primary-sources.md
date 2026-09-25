# Task 14 Automation Primary-Source Research

Date: 2026-08-30

## Decision summary

- Keep the approved Ubuntu/Windows/macOS and Python 3.11/3.12/3.13 matrix.
- Give every workflow only `contents: read`; GitHub documents that unspecified scopes become
  `none` once any explicit permission is declared.
- Pin third-party Actions to full release commit SHAs, with the release tag in an adjacent comment
  so Dependabot can update both.
- Pin uv `0.12.7` and allow the matching `uv_build>=0.12.7,<0.13` backend range.
- Pin the reproducible container to Verilator tag `v5.040` and commit
  `51cdf52d0f3a3e59b51fd87762646a851e9f4aff`; describe it as the CI pin, never as latest.
- Use Dependabot ecosystems `github-actions`, `docker`, and `uv` at the repository root.

## GitHub Actions workflow and composite-action contracts

GitHub's workflow syntax states that `permissions` accepts per-scope `read`, `write`, or `none`,
and that declaring any scopes makes every omitted scope `none`. The same reference defines matrix
expansion over operating-system and language-version axes.

- [Workflow syntax: permissions and matrix](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

GitHub's action metadata reference requires `runs.using: composite`, supports both `run` and `uses`
steps, requires a shell for composite `run` steps, and supports step-scoped `env` plus conditional
steps. It recommends a full commit SHA as the safest Action reference.

- [Metadata syntax reference](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax)

The official repositories currently document major v7 for checkout, setup-python, and
upload-artifact. Read-only `git ls-remote` against those repositories resolved these release refs:

| Action | Full pin | Release documentation |
|---|---|---|
| `actions/checkout` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | [checkout](https://github.com/actions/checkout) |
| `actions/setup-python` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | [setup-python](https://github.com/actions/setup-python) |
| `actions/upload-artifact` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | [upload-artifact](https://github.com/actions/upload-artifact) |

The upload Action documents `if-no-files-found`, defaults hidden-file inclusion to false, and
warns that hidden files should be reviewed before enabling them. RTL Lens should upload only
explicit `report.json` and/or `report.html` paths, keep hidden-file inclusion false, and use
`if-no-files-found: error` when upload was explicitly requested.

- [upload-artifact inputs and security notes](https://github.com/actions/upload-artifact/blob/main/README.md)

## uv lock, build, and CI installation

Astral documents `uv lock --check` as an assertion that the existing lock would remain unchanged;
it is equivalent to locked mode. `uv build` builds an sdist and then a wheel from that sdist into
`dist/`. The official package guide recommends `--no-sources` for a publication-like build.

- [Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Building distributions](https://docs.astral.sh/uv/concepts/projects/build/)
- [Building and publishing a package](https://docs.astral.sh/uv/guides/package/)

The official installer documentation currently provides a versioned `0.12.7` installer. The
official setup-uv repository documents full-SHA pinning and cross-platform Python matrix use. Its
`v10.0.1` ref resolves to `20cfd1bf945f4377ade1205e4dbc17946fc9a30d`.

- [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- [setup-uv](https://github.com/astral-sh/setup-uv)

uv 0.12's official release notes state that there are no breaking `uv_build` configuration
changes and recommend widening the upper bound to `<0.13`. The current project still uses
`uv_build>=0.11.32,<0.12`, so Task 14 should move to `uv_build>=0.12.7,<0.13` and regenerate the
universal lockfile.

- [uv 0.12 release notes](https://github.com/astral-sh/uv/releases/tag/0.12.0)
- [uv build backend](https://docs.astral.sh/uv/configuration/build-backend/)

## Verilator 5.040 pin

Verilator `5.040` is an official historical release announced on 2025-08-30. The exact annotated
tag is `v5.040`; its tag object is `05e78d1d3a66cc0bab45f21ad855f96365966421` and it points to
commit `51cdf52d0f3a3e59b51fd87762646a851e9f4aff`. It is not the current latest release and has no
GitHub Releases object, so automation must not link a nonexistent release page or call it latest.

- [Official 5.040 announcement](https://github.com/verilator/verilator-announce/issues/78)
- [Official v5.040 source tree](https://github.com/verilator/verilator/tree/v5.040)
- [v5.040 installation guide](https://github.com/verilator/verilator/blob/v5.040/docs/guide/install.rst)

The tagged installation guide lists the required Ubuntu build toolchain: Git, help2man, Perl,
Python 3, make, g++, autoconf, flex, bison, `libfl2`, `libfl-dev`, `zlib1g`, and `zlib1g-dev`.
Building from a clean exact tag produces `Verilator 5.040 2025-08-30 rev v5.040`; archive builds
without `.git` can report `UNKNOWN.REV`, so the container should checkout the exact commit and
verify the complete version string.

- [Version definition](https://github.com/verilator/verilator/blob/v5.040/configure.ac)
- [Version rendering](https://github.com/verilator/verilator/blob/v5.040/src/V3Options.cpp#L985-L988)

## Dockerfile and dependency updates

Docker documents digest-qualified `FROM` values, multi-stage builds, `ARG` for non-secret build
parameters, `LABEL` for inspectable image metadata, and exec-form `ENTRYPOINT`. Build arguments
must never carry secrets because they can appear in history/provenance. RTL Lens uses build args
only for public version/commit pins and labels the final image with the exact Verilator version.

- [Dockerfile reference](https://docs.docker.com/reference/dockerfile)
- [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)

GitHub's supported-ecosystems table lists `uv`, `docker`, and `github-actions`. For SHA-pinned
Actions, an adjacent tag comment lets Dependabot update version documentation; local Actions are
ignored, which is expected for `uses: ./` smoke coverage.

- [Dependabot supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
- [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)

## Local verification boundary

The current Windows host has neither `uv` nor Docker installed, and its launcher does not expose a
local 3.11/3.12/3.13 matrix. Task 14 may provision a project-scoped uv executable for lock/build
checks. A real Docker build and Linux/multi-platform jobs must remain explicitly unverified until a
Docker-capable host or GitHub runner executes them; static contracts are not substitutes for those
runtime gates.
