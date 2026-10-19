# P0 差分探针：comrak vs markdown-it

临时探针，用来回答 [ADR 0005](../../../docs/adr/0005-vscode-1.142-as-oracle.md)
的严格 VS Code 语义能否用 comrak 0.56 + 自定义渲染器达到。**不是产品代码。**

```bash
./run.sh
node perf.mjs   # 生成 results/perf-corpus.jsonl 并测 markdown-it
./target/release/comrak-probe results/perf-corpus.jsonl results/perf-comrak.jsonl
```

产物：

- `corpus/corpus.jsonl`：从旧测试、docs、selftest、curated、CommonMark spec 合并的语料（生成物，不入库）。
- `results/oracle.jsonl`：markdown-it 14.3.2 + VS Code front matter 表格的输出。
- `results/comrak.jsonl`：comrak 探针输出。
- `results/summary.json` / `results/diffs.jsonl`：分类 diff。
- 报告写到 `docs/spikes/comrak-vs-markdown-it.md`。

安全：`docs/index.md` 里有 raw HTML `<script>`，探针只在字符串/DOM 层比较，**不要**
把输出丢进浏览器。

语料里 `policy` 为 `stress` / `internal` 的条目不参与语义通过率；`front_matter`
单独分类，因为 front matter 表格是已知的自定义层。
