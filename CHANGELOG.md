# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Development-time CLI analysis, configuration, dual-engine diagnostics, and
  generated report capabilities currently available in this checkout.
- Local, pinned PySlang-only compatibility observations for ten public RTL file
  subsets, with exact scope, provenance and limitations recorded.
- Installed-release-candidate checks that build wheel and source distributions,
  install each in an isolated environment, validate dependencies and import origin,
  and scan a clean redacted fixture through the packaged console command.
- Honest external-beta feedback guidance and a release checklist that keeps unmet
  platform, remote, adoption and publication gates open.

### Changed

- Public onboarding and governance documentation for the pre-release project.
- Refresh pinned setup-python, setup-uv, and upload-artifact Actions. Workflow
  tests still require immutable commit pins and consistent versions across files,
  while permitting reviewed dependency updates.

### Fixed

- Include the license when building the container's Python package and bootstrap
  pip in the test target's isolated environment.
- Preserve LF line endings for generated rule guides on Windows checkouts.
- Isolate invalid upstream PySlang 11 Linux stubs from strict project type checks.
- Run release checks on the public `main` branch and ignore coverage worker files.
- Read Verilator's unnamed located errors and count-checked exit summaries without
  discarding valid findings; keep unlocated unexplained errors as engine failures.
- Translate GNU realpath flags in the macOS Action test harness while retaining
  actual filesystem and symlink resolution.
