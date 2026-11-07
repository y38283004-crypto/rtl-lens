# SARIF fixtures

`verilator-width.sarif.json` is a compact schema fixture using the concrete
`WIDTHTRUNC` code emitted by the pinned Verilator 5.040 assignment checker.

`verilator-empty-rules.sarif.json` is intentionally invalid JSON: it reproduces
the missing comma between `tool` and `invocations` when the producer has no named
rules. The pinned [`V3OutJsonFile::end()`](https://github.com/verilator/verilator/blob/51cdf52d0f3a3e59b51fd87762646a851e9f4aff/src/V3File.h)
does not mark a closed empty container as a value in its parent scope; the
[`SARIF emitter`](https://github.com/verilator/verilator/blob/51cdf52d0f3a3e59b51fd87762646a851e9f4aff/src/V3DiagSarif.cpp)
closes empty `driver.rules` immediately before starting `invocations`.

Tests permit one comma insertion at that exact boundary only, followed by strict
JSON decoding, Verilator 5.040 producer checks, and the usual SARIF validation. Other malformed
reports remain errors. The native container tests also exercise a clean file
with no named diagnostics.
