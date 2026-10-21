# mdview 文档地图

这里是 2.0 文档的入口。根目录的 [`README.md`](../README.md) 是产品入口，
[`AGENT.md`](../AGENT.md) 是改动指南，[`GLOSSARY.md`](../GLOSSARY.md) 是术语表，
[`CHANGELOG.md`](../CHANGELOG.md) 记录版本变化。

## 按用途查找

| 目录 | 内容 | 入口 |
|---|---|---|
| `architecture/` | 设计方案、执行计划、ADR 决策记录 | [overview.md](architecture/overview.md) · [execution-plan.md](architecture/execution-plan.md) · [ADRs](architecture/adr/) |
| `guides/` | 安装/运行/Trust、渲染边界、代码块专项 | [install.md](guides/install.md) · [advanced.md](guides/advanced.md) · [code-blocks.md](guides/code-blocks.md) |
| `reference/` | 功能矩阵与追踪编号 | [features.md](reference/features.md) |
| `testing/` | 自测记录、浏览器验收报告、agent 测试指南、截图证据 | [selftest.md](testing/selftest.md) · [browser-report-2026-10-20.md](testing/browser-report-2026-10-20.md) · [browser-report-2026-10-21.md](testing/browser-report-2026-10-21.md) · [browser-report-2026-10-21-archives.md](testing/browser-report-2026-10-21-archives.md) · [agent-guide.md](testing/agent-guide.md) |
| `research/` | P0 comrak vs markdown-it 差分探针 | [comrak-vs-markdown-it.md](research/comrak-vs-markdown-it.md) |
| `archive/` | 旧 Python 实现历史台账 | [selftest-python.md](archive/selftest-python.md) |
| `index.md` + `preview/` | 作为服务根时使用的示例文档与夹具，不是产品文档 | [index.md](index.md) · [preview/](preview/) |

## 文档状态

- **current**：描述当前 Rust 实现，改代码时优先依据它。`README.md`、`AGENT.md`、
  `GLOSSARY.md`、`architecture/`、`guides/`、`reference/features.md`、`testing/`。
- **historical**：归档内容，保留当时的命令与计数，不代表当前行为。`archive/`、
  ADR 中标记为 superseded 的记录。
- **fixture**：用于演示渲染、目录、源码、搜索和二进制处理的样例。`index.md`、
  `guides/` 与 `preview/` 中的文件同时也是 `--root docs` 的演示内容。

## 维护规则

1. 改变用户可见行为时，更新 [`reference/features.md`](reference/features.md) 对应行的
   验收口径与测试映射；新功能追加新编号，不重排旧编号。
2. 做出难以回退、且未来读者会问“为什么”的选择时，新增 ADR；ADR 放在
   [`architecture/adr/`](architecture/adr/)，并更新相关指南。
3. 测试结果写入 [`testing/`](testing/)；自动化命令、临时服务、fixture 与浏览器证据
   见 [`testing/agent-guide.md`](testing/agent-guide.md)。
4. 文档内部链接由 `node tests/check-doc-links.mjs` 检查；移动文档后必须同时更新
   所有相对链接。
5. 历史文档不重写行为；如需修正，只加“历史说明”并指向当前文档。
