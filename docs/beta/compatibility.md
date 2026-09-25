# Pinned RTL compatibility observations

These are **file-subset analysis observations, not ten whole-project certifications**.
`complete` means analysis completed, not clean RTL or verified hardware. No simulation,
synthesis, timing validation, false-positive adjudication, or external beta feedback is
represented by this table.

## Observation environment

- Observed on **2026-09-15**, Windows, using runner revision `e126817`.
- Python **3.12.13**, RTL Lens **0.1.0.dev0**, PySlang **11.0.0**.
- Git **2.54.0.windows.1**; environment provisioned with uv **0.12.7**.
- Explicit `--engine-mode disabled`: requested and completed engines are both
  `["pyslang"]`. Verilator and Docker were unavailable; dual-engine/container
  compatibility is **not run**, not passed.
- Every entry expected `complete` and actually returned `complete`, CLI exit `0`,
  `redacted=true`, and an empty `failures` list. No failed/partial/not-run row was
  removed or replaced to improve the record.

The [manifest](../../compatibility.toml) is the executable source of truth for exact
SHA-1 commits, selected files, license SHA-256 hashes, top modules and scope. All
include directories and defines are empty; staged `source_roots` is `["."]`.
The runner checks checkout identity, selected Git blob bytes and license hash, then
scans an immutable byte snapshot in a private temporary directory. It neither
fetches sources nor executes upstream builds, scripts, hooks or submodules.

## Results

Elapsed milliseconds measure each local CLI subprocess, excluding cache validation
and staging. They are single-run observations, **not benchmarks or project rankings**.
"Unknown" counts engine-native findings lacking a curated explanation; their original
diagnostic details remain in the redacted reports. A finding is not a proven defect.

| Project scope | Sources | Findings | Unknown | Elapsed ms | State | Redacted |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| picorv32 | 1 | 92 | 68 | 1908 | complete | true |
| verilog-uart | 3 | 1 | 0 | 1418 | complete | true |
| verilog-i2c | 1 | 16 | 2 | 1436 | complete | true |
| verilog-axis | 1 | 8 | 8 | 1441 | complete | true |
| verilog-axi | 1 | 12 | 2 | 1422 | complete | true |
| verilog-ethernet | 2 | 14 | 11 | 1357 | complete | true |
| aes | 7 | 2 | 2 | 2225 | complete | true |
| sha256 | 4 | 6 | 5 | 1830 | complete | true |
| sha512 | 5 | 2 | 1 | 1896 | complete | true |
| chacha | 3 | 4 | 3 | 1784 | complete | true |

Totals: **28 source files, 157 findings, 102 unknown**, leaving 55 findings with
curated mappings. Earlier exploratory direct-CLI scans of these same pinned subsets
produced the same per-entry source/finding/unknown counts; those exploratory results
were not substituted for this runner execution. No scan scope changed between them.

## Pinned sources, licenses and boundaries

Links below address immutable upstream commits. Attribution, full license hashes,
all selected-file links and acquisition details are retained in the
[primary-source research note](../superpowers/research/2026-09-14-task16-compatibility-corpus.md).
Upstream license files and source notices are copied into each private scan stage;
upstream RTL is not vendored into this repository.

| Repository at pinned commit | License notice | Top file | Exact boundary |
| --- | --- | --- | --- |
| [YosysHQ/picorv32 — ef203c2](https://github.com/YosysHQ/picorv32/tree/ef203c2b0a3fb793280f5114941416c425c5b461) | [ISC](https://github.com/YosysHQ/picorv32/blob/ef203c2b0a3fb793280f5114941416c425c5b461/COPYING) | [picorv32.v](https://github.com/YosysHQ/picorv32/blob/ef203c2b0a3fb793280f5114941416c425c5b461/picorv32.v) | One file, top `picorv32`; no other tops, firmware or benches. |
| [alexforencich/verilog-uart — 1b867e5](https://github.com/alexforencich/verilog-uart/tree/1b867e53af738e4a8bc7c839ca2f1c07f40382dc) | [MIT](https://github.com/alexforencich/verilog-uart/blob/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/COPYING) | [rtl/uart.v](https://github.com/alexforencich/verilog-uart/blob/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/rtl/uart.v) | Wrapper plus `rtl/uart_rx.v`, `rtl/uart_tx.v`; no benches/examples. |
| [alexforencich/verilog-i2c — a65be40](https://github.com/alexforencich/verilog-i2c/tree/a65be4045e898a52e791c6ee71f8f79a7cd2e129) | [MIT](https://github.com/alexforencich/verilog-i2c/blob/a65be4045e898a52e791c6ee71f8f79a7cd2e129/COPYING) | [rtl/i2c_master.v](https://github.com/alexforencich/verilog-i2c/blob/a65be4045e898a52e791c6ee71f8f79a7cd2e129/rtl/i2c_master.v) | Generic master only; no AXI/Wishbone wrappers or benches. |
| [alexforencich/verilog-axis — 48ff7a7](https://github.com/alexforencich/verilog-axis/tree/48ff7a7e2ef782cf778d47910cf85835c64b1bce) | [MIT](https://github.com/alexforencich/verilog-axis/blob/48ff7a7e2ef782cf778d47910cf85835c64b1bce/COPYING) | [rtl/axis_fifo.v](https://github.com/alexforencich/verilog-axis/blob/48ff7a7e2ef782cf778d47910cf85835c64b1bce/rtl/axis_fifo.v) | FIFO only; no other components, wrappers or benches. |
| [alexforencich/verilog-axi — 516bd5d](https://github.com/alexforencich/verilog-axi/tree/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53) | [MIT](https://github.com/alexforencich/verilog-axi/blob/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53/COPYING) | [rtl/axi_ram.v](https://github.com/alexforencich/verilog-axi/blob/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53/rtl/axi_ram.v) | RAM only; no adapters, interconnects, DMA engines or benches. |
| [alexforencich/verilog-ethernet — 77320a9](https://github.com/alexforencich/verilog-ethernet/tree/77320a9471d19c7dd383914bc049e02d9f4f1ffb) | [MIT](https://github.com/alexforencich/verilog-ethernet/blob/77320a9471d19c7dd383914bc049e02d9f4f1ffb/COPYING) | [rtl/axis_eth_fcs.v](https://github.com/alexforencich/verilog-ethernet/blob/77320a9471d19c7dd383914bc049e02d9f4f1ffb/rtl/axis_eth_fcs.v) | FCS calculator plus `rtl/lfsr.v`; no MAC/PHY/IP/UDP blocks or benches. |
| [secworks/aes — 80dc471](https://github.com/secworks/aes/tree/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc) | [BSD-2-Clause](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/LICENSE) | [src/rtl/aes.v](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes.v) | Seven manifest-listed RTL files; no benches, software or integration collateral. |
| [secworks/sha256 — 837c5cc](https://github.com/secworks/sha256/tree/837c5cc396f001d18f2c765721c585716eb439ae) | [BSD-2-Clause](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/LICENSE) | [src/rtl/sha256.v](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256.v) | Four manifest-listed core files; no AXI/stream wrappers, benches or software. |
| [secworks/sha512 — e4cdf33](https://github.com/secworks/sha512/tree/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd) | [BSD-2-Clause](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/LICENSE) | [src/rtl/sha512.v](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512.v) | Five manifest-listed RTL files; no benches, software or documentation. |
| [secworks/chacha — 7eaba36](https://github.com/secworks/chacha/tree/7eaba360df9fed9fc2db98d5f3df81cf01e5b604) | [BSD-2-Clause](https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/LICENSE) | [src/rtl/chacha.v](https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/src/rtl/chacha.v) | Three manifest-listed RTL files; no benches, software or documentation. |

Attribution: Claire Xenia Wolf and PicoRV32 contributors; Alex Forencich and the
respective project contributors; Joachim Strömbergson and the respective Secworks
contributors. Consult each pinned notice for its exact terms.

All selected inputs are **Verilog**, drawn from only **three maintainer groups**.
This small, deliberately scoped corpus cannot establish broad SystemVerilog coverage,
independent user adoption, active upstream maintenance or performance superiority.
PicoRV32 was recorded as archived during source research; its inclusion is a historical
sample, not an endorsement of current maintenance.

## Reproduce

Complete the development setup in [Getting started](../getting-started.md) first.
Use the project's Python environment for `python` below. There is no published package
installation implied by these commands.

### Acquire inputs separately (explicit network step)

The scan runner is offline. Populate `<cache>/<id>/<commit>/` separately, using the
repository URL and full commit from the manifest. In a fresh PowerShell session, the
following creates new checkouts and leaves existing ones untouched; the runner later
verifies any reused checkout. A failed acquisition is not a scan success. Inspect an
incomplete cache manually instead of resetting/deleting it automatically.

```powershell
$ErrorActionPreference = 'Stop'
$cacheRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'rtl-lens-compatibility-cache'
$projects = python -c "import json,tomllib; print(json.dumps(tomllib.load(open('compatibility.toml','rb'))['projects']))" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot read the manifest' }
# Keep Git configuration/credentials out of this fresh acquisition session.
Get-ChildItem Env:GIT_* | ForEach-Object { Remove-Item -LiteralPath ('Env:' + $_.Name) }
$env:GIT_CONFIG_NOSYSTEM = '1'
$env:GIT_CONFIG_GLOBAL = 'NUL'
$env:GIT_TERMINAL_PROMPT = '0'
foreach ($project in $projects) {
    $checkout = Join-Path (Join-Path $cacheRoot $project.id) $project.commit
    if (Test-Path -LiteralPath $checkout) { continue }
    New-Item -ItemType Directory -Path $checkout -Force | Out-Null
    git --no-replace-objects -c core.hooksPath=NUL -C $checkout init --template= --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Git init failed' }
    git --no-replace-objects -c credential.helper= -c core.askPass= -c core.hooksPath=NUL -C $checkout fetch --depth=1 --no-tags $project.repository $project.commit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned fetch failed' }
    git --no-replace-objects -c core.hooksPath=NUL -c core.autocrlf=false -c filter.lfs.process= -c filter.lfs.smudge= -c filter.lfs.required=false -C $checkout checkout --detach --quiet FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Detached checkout failed' }
}
```

No submodule update, upstream script or build command is part of acquisition. The
checked license and source bytes must match the manifest's pinned Git objects.

### Run locally, without fetching

The formal run used an external cache with the preceding layout and this command
(replace `<cache-root>` with its actual directory):

```text
python scripts/scan_compatibility.py --manifest compatibility.toml --cache-dir <cache-root> --output .artifacts/compatibility/2026-09-15-pyslang-01 --engine-mode disabled
```

For a new run choose a fresh output directory, for example:

```powershell
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
python scripts/scan_compatibility.py --manifest compatibility.toml --cache-dir $cacheRoot --output ".artifacts/compatibility/$runId" --engine-mode disabled
```

The recorded run returned exit0. Missing caches produce `not-run` with null counts;
partial/failed/not-run results return aggregate exit1. Invalid input/output returns
exit2. Existing nonempty outputs are refused, so stale reports cannot be reused as
new success. Preserve unsuccessful observations when investigating a new run.

Local outputs are `results.json`, `summary.md`, and per-project `result.json`,
`report.json`, `report.html` under the chosen run directory. They are ignored by Git
and are not a hosted demo or published dataset. Redaction does not make arbitrary
private RTL reports safe to share: review them and follow [Privacy](../privacy.md).

Offline regression command (no upstream cache required):

```text
python -m pytest tests/integration/test_compatibility_runner.py tests/integration/test_compatibility_manifest.py -q -p no:cacheprovider
```

This record does not close the installed-wheel/sdist, pinned-Verilator/container,
remote CI or external beta release gates.
