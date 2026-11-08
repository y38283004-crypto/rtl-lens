# One width warning, then an explicit fix

From the repository root after installation, run these commands separately:

```powershell
uv run rtl-lens scan examples/width-demo
uv run rtl-lens scan examples/width-demo --config examples/width-demo/fixed.toml
```

| Scan | Findings | Expected exit code | Local HTML report |
| --- | --- | --- | --- |
| Default, `failing/` | 1 width warning | `1` (intentional warning policy block) | `.rtl-lens/failing/report.html` |
| `fixed.toml`, `fixed/` | 0 | `0` | `.rtl-lens/fixed/report.html` |

Report paths in this table are relative to `examples/width-demo/`. Both scans
also write JSON, complete with PySlang only, and extract two modules with one
`demo_top` → `width_stage` relationship. Verilator is not required for this demo.
Open the HTML file in a browser to inspect the bilingual explanation, severity
filters, and module relationship search. Generated `.rtl-lens/` folders are ignored
by Git.

## What changes?

The example's intended output is the low four bits of the input. The original
assignment leaves that truncation implicit:

```systemverilog
assign nibble_o = sample_i;
```

The fixed assignment documents that choice:

```systemverilog
assign nibble_o = sample_i[3:0];
```

If a real design must preserve all eight bits, widen the destination instead.
A clean lint result does not establish functional correctness.

Both configurations enable redaction. The committed [demo reports](../../docs/demo/README.md)
are snapshots from these synthetic sources; regenerate local reports with the
commands above. Durations and timestamps will vary between runs.

## 简体中文

第一条命令故意触发一次位宽截断告警，因此返回 `1`；它仍会生成完整报告。
第二条使用显式位选保留低四位，返回 `0`，当前诊断数为零。
报告在本目录的 `.rtl-lens/failing/` 和 `.rtl-lens/fixed/` 中，双击 HTML 即可查看。
示例仅使用 PySlang，展示静态诊断、双语解释和模块关系；真实设计应先确认是否允许丢弃高四位。
