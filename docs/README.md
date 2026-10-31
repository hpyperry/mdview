# mdview 文档地图

这里是 2.2 文档的入口。根目录的 [`README.md`](../README.md) 是产品入口，
[`AGENTS.md`](../AGENTS.md) 是改动指南，[`GLOSSARY.md`](../GLOSSARY.md) 是术语表，
[`CHANGELOG.md`](../CHANGELOG.md) 记录版本变化。

## 按用途查找

| 目录 | 内容 | 入口 |
|---|---|---|
| `architecture/` | 设计方案与 ADR 决策记录 | [overview.md](architecture/overview.md) · [ADRs](architecture/adr/README.md) |
| `guides/` | 安装/运行/Trust、渲染边界、代码块专项、本地构建卫生 | [install.md](guides/install.md) · [advanced.md](guides/advanced.md) · [code-blocks.md](guides/code-blocks.md) · [build-hygiene.md](guides/build-hygiene.md) |
| `reference/` | 功能矩阵与追踪编号 | [features.md](reference/features.md) |
| `../tests/` | 自动化套件、feature/fix 人工复测文档与夹具 | [tests/README.md](../tests/README.md) · [fixtures/README.md](../tests/fixtures/README.md) |
| `testing/` | 当前自测记录、浏览器验收报告与截图证据 | [selftest.md](testing/selftest.md) · [reports/README.md](testing/reports/README.md) · [agent-guide.md](testing/agent-guide.md) |
| `research/` | P0 comrak vs markdown-it 差分探针 | [comrak-vs-markdown-it.md](research/comrak-vs-markdown-it.md) |
| `archive/` | 历史 Python 台账、旧浏览器验收与已完成的重写计划 | [README.md](archive/README.md) |
| `releases/` | 版本发布说明 | [2.2.2.md](releases/2.2.2.md) · [2.2.1.md](releases/2.2.1.md) · [2.2.0.md](releases/2.2.0.md) · [2.1.0.md](releases/2.1.0.md) · [2.0.1.md](releases/2.0.1.md) |
| `agents/` | Agent skills 配置：Issue tracker、triage 标签、domain docs | [issue-tracker.md](agents/issue-tracker.md) · [triage-labels.md](agents/triage-labels.md) · [domain.md](agents/domain.md) |
| `index.md` + `preview/` | 作为服务根时使用的示例文档与夹具，不是产品文档 | [index.md](index.md) · [preview/](preview/) |

## 文档状态

- **current**：描述当前 Rust 实现，改代码时优先依据它。`README.md`、`AGENTS.md`、
  `GLOSSARY.md`、`architecture/`、`guides/`、`reference/features.md`、`testing/`。
- **historical**：归档内容，保留当时的命令与计数，不代表当前行为。`archive/`、
  ADR 中标记为 superseded 的记录。
- **fixture**：用于演示渲染、目录、源码、搜索和二进制处理的样例。`index.md`、
  `guides/` 与 `preview/` 中的文件同时也是 `--root docs` 的演示内容。

## 维护规则

1. 改变用户可见行为时，更新 [`reference/features.md`](reference/features.md) 对应行的
   验收口径与测试映射；新功能追加新编号，不重排旧编号。
2. 每个 feature/fix 在 `tests/fixtures/<slug>/README.md` 留一份人工复测文档；有夹具
   时目录可服务，纯修复可只放 README。PR 与受影响 `F-xx` 链接它；`docs/testing/`
   只放执行记录与报告。
3. 做出难以回退、且未来读者会问“为什么”的选择时，新增 ADR；ADR 放在
   [`architecture/adr/`](architecture/adr/)，并更新相关指南。
4. 测试结果写入 [`testing/`](testing/)；自动化命令、临时服务、fixture 与浏览器证据
   见 [`testing/agent-guide.md`](testing/agent-guide.md)。
5. 文档内部链接由 `node tests/check-doc-links.mjs` 检查；移动文档后必须同时更新
   所有相对链接。
6. 历史文档不重写行为；如需修正，只加“历史说明”并指向当前文档。
