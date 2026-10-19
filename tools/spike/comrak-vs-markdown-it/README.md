# P0 差分探针：comrak vs markdown-it

临时探针，用来回答 [ADR 0005](../../../docs/adr/0005-vscode-1.142-as-oracle.md)
的严格 VS Code 语义能否用 comrak 0.56 + 自定义渲染器达到。**不是产品代码。**

> **历史工具**：`extract_corpus.py` 依赖旧 Python 测试（已在 2.0 删除）。
> 完整重跑需要从 git 历史取回 Python 实现，或只用 `corpus/curated.json`；
> P0 报告与结论已固化在 `docs/spikes/`，日常测试不再依赖本目录。

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

协议：oracle 复刻 VS Code 1.142 的 `validateLink` 覆盖（base + `vscode:` +
`/^data:image\/.*?;/`）；probe 按服务器策略放行任意 `data:image/*;…`（链接与图片），
拒绝 `vscode:`/`vscode-insiders:`，其余危险协议继续拒绝。2 条 vscode 链接差异
标记为 `server_vscode_scheme_expected`。

语料里 `policy` 为 `stress` / `internal` 的条目不参与语义通过率；`front_matter`
单独分类，因为 front matter 表格是已知的自定义层。
