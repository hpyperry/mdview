# Agent 自主测试指南

这份指南给在 mdview 仓库里自主测试的 agent。目标不是“跑几条 curl”，而是用
**功能矩阵 + 自动断言 + 真实浏览器交互/截图** 证明当前实现符合产品预期。

## 1. 先读什么

1. [`../reference/features.md`](../reference/features.md)：功能编号 `F-xx`、验收要点、
   已有测试映射。测试计划从这里的编号取，不重新发明需求。
2. [`../../tests/README.md`](../../tests/README.md)：现有自动套件怎么跑、各自覆盖什么。
3. [`selftest.md`](selftest.md)：最近一次自动套件结果。
4. [`../../AGENTS.md`](../../AGENTS.md)：代码边界与硬约束；测试时不要改产品代码，
   除非本轮任务明确要求修复。
5. `browser-use` 的 `control-browser` 与 `web-gui-tester` skill：真实浏览器操作的
   工具规则和黑盒测试方法。

## 2. 测试分三层

| 层 | 目的 | 工具 | 证据 |
|---|---|---|---|
| 单元/渲染 | 解析器、URL、协议、缓存、Trust | `cargo test`、`render_compat`、`golden` | 测试输出 |
| HTTP 黑盒 | 真二进制上的路由、目录、搜索、下载、CSP、安全边界 | `tests/selftest-rust.sh`、`trust-tty.sh`、`smoke-artifact.sh` | 断言日志 |
| 浏览器/视觉 | 页面是否真的可用、布局/文案/交互是否符合预期 | `tests/browser-probe.mjs` + browser-use/Computer Use | 断言日志 + 截图 |

`browser-probe.mjs` 是回归探针，覆盖 160+ 条 DOM/行为断言；browser-use 负责
“人眼会怎么看、真实点击会怎样”的验收。两者不能互相替代。

## 3. 环境准备

```bash
# 在仓库根
npm --prefix web ci            # 首次
cargo build --release
npm --prefix web run typecheck
```

准备一个临时根目录时，优先复用现有 fixture，而不是手写一堆文件：

- `tests/browser-probe.mjs` 的 `writeFixture()`：页面、源码、图片、大文件、宽行、
  子目录、40 个文件等。
- `docs/`：真实示例文档，适合查看 Markdown/目录/搜索/源码页。
- `docs/preview/`：二进制、图片、配置、代码、大文件夹具。

启动被测服务：

```bash
./target/release/mdview --root docs --host 127.0.0.1 --port 8155 --trust
```

需要 Trust 拦截面时，另起一个：

```bash
./target/release/mdview --root docs --host 127.0.0.1 --port 8156 --untrusted
```

使用空闲端口，测试结束杀掉进程；不要占用用户已有服务。

## 4. 自动套件

```bash
node tests/check-doc-links.mjs
cargo test
cargo clippy --all-targets -- -D warnings
cargo fmt --all --check
bash tests/selftest-rust.sh
bash tests/trust-tty.sh
node tests/browser-probe.mjs
node tests/perf-source.mjs
bash tests/smoke-artifact.sh target/release/mdview
```

或直接：

```bash
bash tests/run-all.sh
```

`trust-tty.sh` 依赖 `expect`；缺失时它会跳过，报告里要写明。Windows 上跳过 pty、
浏览器和性能套件是已知矩阵差异。

## 5. 用 browser-use 做视觉/交互验收

### 5.1 基本流程

1. 加载 `browser-use:control-browser` 与 `browser-use:web-gui-tester` skill。
2. 在 `mcp__node_repl__js` 里按 control-browser 的 bootstrap 初始化
   `setupBrowserRuntime`，通过 `agent.browsers.getForUrl(target)` 选择浏览器。
3. 先 `browser.tabs.list()` / `browser.tabs.get(id)` 确认目标 tab；不要凭记忆使用 tab id。
4. 用 `tab.playwright.domSnapshot()` 读页面结构；需要判断布局/视觉时才截图。
5. 用 snapshot 提供的 role/name 构造 locator，真实点击、输入、按键、滚动。
6. 每次动作后同时做 DOM 观察和必要截图；每个测试点至少保留一张已查看的截图。
7. 截图保存到 `docs/testing/evidence/2026-10-20/`，文件名带功能编号，例如
   `F-39_file-header-link.png`。

### 5.2 黑盒边界

- 只通过可见 UI 操作；不要用 JavaScript 注入改 DOM/触发事件/改 localStorage。
- 不用修改 URL 的方式绕过失败操作；导航/刷新只用于切换测试点。
- 页面失败时记录截图和复现步骤，跳过依赖它的测试点，继续其他测试点。
- 测试期间不改代码；先完成测试报告，再决定是否修复。

### 5.3 从功能矩阵生成测试点

对每个 `F-xx`：

1. 读验收要点。
2. 选择已有自动断言是否足够；不足的进入 browser-use 清单。
3. 写清“操作 → 期望页面状态”。
4. 至少覆盖：页面存在、关键文案、交互后的状态、布局/遮挡。
5. 失败时记录：功能编号、步骤、实际状态、预期、截图路径、控制台错误（如果工具有）。

推荐按功能域分批，避免一次打开十几个 tab：

| 批次 | 功能编号 | 页面 |
|---|---|---|
| 目录与外壳 | F-09–F-16、F-45 | `/`、子目录、404 |
| Markdown | F-17–F-27、F-50–F-53 | `/index.md`、指南页 |
| 源码 | F-28–F-35 | `/index.md?raw=1`、大文本 |
| 搜索 | F-36–F-44 | `/search?__mdview=search&q=…`、搜索结果行 |
| 编码 | F-89–F-90 | GBK/UTF-16 预览、编码标签、下载/raw charset |
| 导航与主题 | F-46–F-49、F-54–F-56 | 桌面浮岛、移动抽屉、主题 |
| 安全 | F-58–F-63 | 未信任服务、错误页 |

### 5.4 截图与证据

- 每个测试点至少一张截图；瞬时状态（toast、抽屉、搜索结果跳转）用同一脚本先
  截图 → 操作 → 等待状态 → 再截图。
- 报告用相对路径引用：`evidence/2026-10-20/F-39_file-header-link.png`。
- 截图必须真的被阅读/查看过；只生成不查看不算证据。
- 完整日志放 `target/test-runs/`，不提交；只提交报告引用的关键截图。

### 5.5 工具层注意点

- IAB 的 `press("Enter")` / CUA `keypress` 在搜索框上可能不会带 `text` 负载，因而
  不触发隐式表单提交；这不等于产品 Bug。`tests/browser-probe.mjs` 已用带
  `text: "\r"` 的真实 CDP 键盘事件覆盖“搜索 Enter 提交”，可参考它的写法。
- 搜索框的 Enter、Esc 是功能；不要用 JavaScript 直接调用 `requestSubmit()` 代替
  视觉验收。按钮点击是正常 UI 路径，可以作为 Enter 的替代路径，但报告里要写清。
- 瞬时 toast/抽屉/焦点状态必须在同一个脚本里完成“操作 → 等待 → 截图”，否则会
  错过状态。
- 报告里的每个失败项都要有可复现步骤和已查看的截图；没有截图的结论不算完成。

## 6. 一轮测试的记录格式

```text
环境：分支、commit、OS、Rust、Node、Chrome、root、端口
自动套件：命令 → PASS/FAIL（数量）
视觉验收：F-xx → 通过/失败/受阻 → 截图
发现：编号、复现步骤、预期、实际、证据
覆盖缺口：未测功能、平台差异、需要 tag/人工的操作
结论：是否可以进入下一阶段
```

## 7. 提交前检查

1. `tests/run-all.sh` 全绿（或明确记录跳过项）。
2. `node tests/check-doc-links.mjs` 无 missing。
3. 功能矩阵中受影响的行已更新。
4. 报告引用的截图存在且路径正确。
5. 不把临时服务、fixture、日志、node_modules 带进提交。
6. 用户没有明确要求时，不 push、不触发远程 CI。
