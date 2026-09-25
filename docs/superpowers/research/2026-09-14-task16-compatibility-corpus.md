# Task 16 compatibility-corpus research

Date: 2026-09-14

## Bounded result

This note records only repositories whose exact commit, license bytes, and selected RTL paths were independently checked by the Task 16 controller using an anonymous, depth-one detached Git fetch. No upstream build, test, script, submodule, or generated-code flow was run. The proposed scopes are deliberately smaller than the repositories: they are source-only PySlang inputs and do not establish simulation correctness, synthesis correctness, whole-repository compatibility, maintenance status, or Verilator compatibility.

All ten repository pins below were independently verified by the controller. The final six scopes were then checked only against those already-acquired local checkout trees; no further network acquisition occurred.

## Verified entries

### `picorv32`

- Repository: <https://github.com/YosysHQ/picorv32>
- Exact commit: [`ef203c2b0a3fb793280f5114941416c425c5b461`](https://github.com/YosysHQ/picorv32/tree/ef203c2b0a3fb793280f5114941416c425c5b461)
- License: `ISC`; file [`COPYING`](https://github.com/YosysHQ/picorv32/blob/ef203c2b0a3fb793280f5114941416c425c5b461/COPYING); raw immutable bytes: <https://raw.githubusercontent.com/YosysHQ/picorv32/ef203c2b0a3fb793280f5114941416c425c5b461/COPYING>
- License SHA-256: `041ebc727233e5bf096dd41260cbb81014d3d29ca007a15f3b1807d4e9ff288e`
- Attribution: Claire Xenia Wolf and PicoRV32 contributors; retain the pinned `COPYING` notice verbatim.
- Selected files / top files: [`picorv32.v`](https://github.com/YosysHQ/picorv32/blob/ef203c2b0a3fb793280f5114941416c425c5b461/picorv32.v) (94,657 bytes) / `picorv32.v`
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["picorv32"]`.
- Scope: standalone PicoRV32 processor module only. The repository was archived on 2026-09-08; this is a historical compatibility sample, not evidence of active maintenance.

### `verilog-uart`

- Repository: <https://github.com/alexforencich/verilog-uart>
- Exact commit: [`1b867e53af738e4a8bc7c839ca2f1c07f40382dc`](https://github.com/alexforencich/verilog-uart/tree/1b867e53af738e4a8bc7c839ca2f1c07f40382dc)
- License: `MIT`; file [`COPYING`](https://github.com/alexforencich/verilog-uart/blob/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/COPYING); raw immutable bytes: <https://raw.githubusercontent.com/alexforencich/verilog-uart/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/COPYING>
- License SHA-256: `e976f1560229f2e4259c993745637435e2d8f969c91bf73651443aea4438d142`
- Attribution: Alex Forencich and verilog-uart contributors; retain the pinned `COPYING` notice.
- Selected files: [`rtl/uart.v`](https://github.com/alexforencich/verilog-uart/blob/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/rtl/uart.v), [`rtl/uart_rx.v`](https://github.com/alexforencich/verilog-uart/blob/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/rtl/uart_rx.v), [`rtl/uart_tx.v`](https://github.com/alexforencich/verilog-uart/blob/1b867e53af738e4a8bc7c839ca2f1c07f40382dc/rtl/uart_tx.v).
- Top files / module: `rtl/uart.v` / `uart`.
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["uart"]`.
- Scope: the three-file AXI4-Stream UART wrapper plus its receive/transmit modules; excludes testbenches, synthesis examples, and other integration collateral.

### `verilog-i2c`

- Repository: <https://github.com/alexforencich/verilog-i2c>
- Exact commit: [`a65be4045e898a52e791c6ee71f8f79a7cd2e129`](https://github.com/alexforencich/verilog-i2c/tree/a65be4045e898a52e791c6ee71f8f79a7cd2e129)
- License: `MIT`; file [`COPYING`](https://github.com/alexforencich/verilog-i2c/blob/a65be4045e898a52e791c6ee71f8f79a7cd2e129/COPYING); raw immutable bytes: <https://raw.githubusercontent.com/alexforencich/verilog-i2c/a65be4045e898a52e791c6ee71f8f79a7cd2e129/COPYING>
- License SHA-256: `9a3d2d9df500459598f939d20f659191c73881eb8d88fd24d0f81a12438320ea`
- Attribution: Alex Forencich and verilog-i2c contributors; retain the pinned `COPYING` notice.
- Selected/top file: [`rtl/i2c_master.v`](https://github.com/alexforencich/verilog-i2c/blob/a65be4045e898a52e791c6ee71f8f79a7cd2e129/rtl/i2c_master.v).
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["i2c_master"]`.
- Scope: standalone generic I2C master RTL only; excludes AXI/Wishbone wrappers, testbenches, examples, and integration collateral.

### `verilog-axis`

- Repository: <https://github.com/alexforencich/verilog-axis>
- Exact commit: [`48ff7a7e2ef782cf778d47910cf85835c64b1bce`](https://github.com/alexforencich/verilog-axis/tree/48ff7a7e2ef782cf778d47910cf85835c64b1bce)
- License: `MIT`; file [`COPYING`](https://github.com/alexforencich/verilog-axis/blob/48ff7a7e2ef782cf778d47910cf85835c64b1bce/COPYING); raw immutable bytes: <https://raw.githubusercontent.com/alexforencich/verilog-axis/48ff7a7e2ef782cf778d47910cf85835c64b1bce/COPYING>
- License SHA-256: `8ea57f95365e9b16a5b516f422b71269183a1ae53bab5878ae6d69039e58fe77`
- Attribution: Alex Forencich and verilog-axis contributors; retain the pinned `COPYING` notice.
- Selected/top file: [`rtl/axis_fifo.v`](https://github.com/alexforencich/verilog-axis/blob/48ff7a7e2ef782cf778d47910cf85835c64b1bce/rtl/axis_fifo.v).
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["axis_fifo"]`.
- Scope: standalone AXI-stream FIFO RTL only; excludes the repository's many other components, benches, synthesis examples, and generated wrappers.
- Additional first-party verification: the GitHub repository API reported default branch `master`, exact SHA `48ff7a7e2ef782cf778d47910cf85835c64b1bce`, SPDX `MIT`, and `archived: false` during this research pass.

### `verilog-axi`

- Repository: <https://github.com/alexforencich/verilog-axi>
- Exact commit: [`516bd5dadc3365b7f9e225d2af8fe0b8d804fe53`](https://github.com/alexforencich/verilog-axi/tree/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53)
- License: `MIT`; file [`COPYING`](https://github.com/alexforencich/verilog-axi/blob/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53/COPYING); raw immutable bytes: <https://raw.githubusercontent.com/alexforencich/verilog-axi/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53/COPYING>
- License SHA-256: `ba81481b2d63a33e0dce336d9e736130709549feeaf6cd424b34beba712baa50`
- Attribution: Alex Forencich and verilog-axi contributors; retain the pinned `COPYING` notice and source header.
- Selected/top file: [`rtl/axi_ram.v`](https://github.com/alexforencich/verilog-axi/blob/516bd5dadc3365b7f9e225d2af8fe0b8d804fe53/rtl/axi_ram.v).
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["axi_ram"]`.
- Scope: standalone AXI RAM RTL only; excludes the repository's adapters, interconnects, DMA engines, benches, and integration collateral.

### `verilog-ethernet`

- Repository: <https://github.com/alexforencich/verilog-ethernet>
- Exact commit: [`77320a9471d19c7dd383914bc049e02d9f4f1ffb`](https://github.com/alexforencich/verilog-ethernet/tree/77320a9471d19c7dd383914bc049e02d9f4f1ffb)
- License: `MIT`; file [`COPYING`](https://github.com/alexforencich/verilog-ethernet/blob/77320a9471d19c7dd383914bc049e02d9f4f1ffb/COPYING); raw immutable bytes: <https://raw.githubusercontent.com/alexforencich/verilog-ethernet/77320a9471d19c7dd383914bc049e02d9f4f1ffb/COPYING>
- License SHA-256: `8ea57f95365e9b16a5b516f422b71269183a1ae53bab5878ae6d69039e58fe77`
- Attribution: Alex Forencich and verilog-ethernet contributors; retain the pinned `COPYING` notice and source headers.
- Selected files: [`rtl/axis_eth_fcs.v`](https://github.com/alexforencich/verilog-ethernet/blob/77320a9471d19c7dd383914bc049e02d9f4f1ffb/rtl/axis_eth_fcs.v) and its [`rtl/lfsr.v`](https://github.com/alexforencich/verilog-ethernet/blob/77320a9471d19c7dd383914bc049e02d9f4f1ffb/rtl/lfsr.v) dependency.
- Top file / module: `rtl/axis_eth_fcs.v` / `axis_eth_fcs`.
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["axis_eth_fcs"]`.
- Scope: AXI-stream Ethernet FCS calculator plus its LFSR dependency only; excludes MAC/PHY/IP/UDP blocks, examples, submodules, and benches.

### `aes`

- Repository: <https://github.com/secworks/aes>
- Exact commit: [`80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc`](https://github.com/secworks/aes/tree/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc)
- License: `BSD-2-Clause`; file [`LICENSE`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/LICENSE); raw immutable bytes: <https://raw.githubusercontent.com/secworks/aes/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/LICENSE>
- License SHA-256: `81899e14798bc6a06e02f48959e1825b9e631f0415bccf5b74e589dabd7c7f80`
- Attribution: Joachim Strömbergson and Secworks AES contributors; retain the pinned license and notices in the source headers.
- Selected files: [`src/rtl/aes.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes.v), [`aes_core.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_core.v), [`aes_decipher_block.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_decipher_block.v), [`aes_encipher_block.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_encipher_block.v), [`aes_inv_sbox.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_inv_sbox.v), [`aes_key_mem.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_key_mem.v), and [`aes_sbox.v`](https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_sbox.v).
- Top file / module: `src/rtl/aes.v` / `aes`.
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["aes"]`.
- Scope: the seven files in the repository's AES RTL implementation; excludes testbenches, software, documentation, and integration collateral.

### `sha256`

- Repository: <https://github.com/secworks/sha256>
- Exact commit: [`837c5cc396f001d18f2c765721c585716eb439ae`](https://github.com/secworks/sha256/tree/837c5cc396f001d18f2c765721c585716eb439ae)
- License: `BSD-2-Clause`; file [`LICENSE`](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/LICENSE); raw immutable bytes: <https://raw.githubusercontent.com/secworks/sha256/837c5cc396f001d18f2c765721c585716eb439ae/LICENSE>
- License SHA-256: `943866e8c0449b472dfebe4d10f0641240abb37778165eb4e68200ce1180890d`
- Attribution: Joachim Strömbergson and Secworks SHA-256 contributors; retain the pinned license and source notices.
- Selected files: [`src/rtl/sha256.v`](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256.v), [`sha256_core.v`](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256_core.v), [`sha256_k_constants.v`](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256_k_constants.v), and [`sha256_w_mem.v`](https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256_w_mem.v).
- Top file / module: `src/rtl/sha256.v` / `sha256`.
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["sha256"]`.
- Scope: the four files in the core SHA-256 RTL directory; excludes AXI/stream wrappers, testbenches, and software.

### `sha512`

- Repository: <https://github.com/secworks/sha512>
- Exact commit: [`e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd`](https://github.com/secworks/sha512/tree/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd)
- License: `BSD-2-Clause`; file [`LICENSE`](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/LICENSE); raw immutable bytes: <https://raw.githubusercontent.com/secworks/sha512/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/LICENSE>
- License SHA-256: `81899e14798bc6a06e02f48959e1825b9e631f0415bccf5b74e589dabd7c7f80`
- Attribution: Joachim Strömbergson and Secworks SHA-512 contributors; retain the pinned license and source notices.
- Selected files: [`src/rtl/sha512.v`](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512.v), [`sha512_core.v`](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512_core.v), [`sha512_h_constants.v`](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512_h_constants.v), [`sha512_k_constants.v`](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512_k_constants.v), and [`sha512_w_mem.v`](https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512_w_mem.v).
- Top file / module: `src/rtl/sha512.v` / `sha512`.
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["sha512"]`.
- Scope: the five files in the SHA-512 RTL implementation; excludes testbenches, software, and documentation.

### `chacha`

- Repository: <https://github.com/secworks/chacha>
- Exact commit: [`7eaba360df9fed9fc2db98d5f3df81cf01e5b604`](https://github.com/secworks/chacha/tree/7eaba360df9fed9fc2db98d5f3df81cf01e5b604)
- License: `BSD-2-Clause`; file [`LICENSE`](https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/LICENSE); raw immutable bytes: <https://raw.githubusercontent.com/secworks/chacha/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/LICENSE>
- License SHA-256: `1d49794412fbcb73a87e6175a0a9c8c6f362dc0902b3e69b0f92fe8765c514ee`
- Attribution: Joachim Strömbergson and Secworks ChaCha contributors; retain the pinned license and source notices.
- Selected files: [`src/rtl/chacha.v`](https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/src/rtl/chacha.v), [`chacha_core.v`](https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/src/rtl/chacha_core.v), and [`chacha_qr.v`](https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/src/rtl/chacha_qr.v).
- Top file / module: `src/rtl/chacha.v` / `chacha`.
- Suggested scan values: `source_roots = ["."]`, `include_dirs = []`, `defines = []`, `top_modules = ["chacha"]`.
- Scope: the three files in the ChaCha RTL implementation; excludes testbenches, software, and documentation.

## Considered but not adopted

`olofk/serv`, `ultraembedded/core_jpeg`, `Arlet/verilog-6502`, `lowRISC/ibex`, `pulp-platform/common_cells`, and `pulp-platform/axi` were considered during the interrupted discovery pass but were not needed after the controller verified the ten entries above. No SHA or licensing assertion is made for them here. `ZipCPU/wbuart32` was intentionally not recommended because its licensing was not established as one of the manifest's allowed permissive identifiers. Generated LiteX designs were avoided because they conflict with the source-only, no-upstream-build boundary.

## Provenance and limitations

- Exact commit, license hash, license-file path, and source-file existence for all ten entries come from the controller's separate anonymous shallow-fetch inspection on 2026-09-14. The GitHub commit/blob/raw links above are immutable primary-source references for review.
- The GitHub REST response for `alexforencich/verilog-axis` was obtained directly from `api.github.com`; remaining REST requests were rate limited with HTTP 403, while controller-owned anonymous Git HTTPS shallow fetches succeeded.
- Suggested scan configuration is an engineering recommendation for the Task 16 staging runner, not an upstream claim. `source_roots = ["."]` assumes the runner preserves the listed repository-relative paths in its private staging directory.
- No compatibility result has been asserted here. A `complete` observation must come only from the offline runner over verified checkout bytes; diagnostics and failures must be preserved even if adverse.
