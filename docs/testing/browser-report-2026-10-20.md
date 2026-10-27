# 浏览器验收报告（2026-10-20）

> 历史快照：本报告的套件计数（50/151/163）记录当时状态；当前计数见
> [`selftest.md`](selftest.md)（82/236/210）。

**被测版本**：mdview 2.0.0，`refactor/new-md-view-server` 工作树
**验收日期**：2026-10-20
**验收方式**：真实浏览器交互 + 截图，对照
[`../reference/features.md`](../reference/features.md) 的 `F-xx` 验收要点。
**结论**：核心流程全部通过；发现 3 个 UI/交互缺口，均为非阻断问题，已在下方记录。

## 环境与准备

| 项 | 值 |
|---|---|
| 平台 | macOS 27.0.0 arm64 |
| Rust / Node | Rust 1.96 / Node 22 |
| 浏览器 | Chrome 155，ZCode In-app Browser（IAB） |
| 受信服务 | `http://127.0.0.1:8155`，`--root docs --trust`；大文件验收时加 `--max-preview 0` |
| 未信任服务 | `http://127.0.0.1:8156`，`--root docs --untrusted` |
| 视口 | 1440×1000 桌面、1200×900 中等宽度、390×844 移动 |
| 证据 | [`evidence/2026-10-20/`](evidence/2026-10-20/) |

准备操作：

- 启动受信/未信任两个临时服务；测试结束保留受信服务供预览，未信任服务可随时停止。
- 大文件验收临时把 `--max-preview` 设为 `0`，否则 22 MB 夹具按设计转为下载。
- 搜索、导航、主题、TOC 均通过可见 UI 操作；直接 URL 只用于已由页面/文档确认的固定路由。
- 测试期间未修改产品代码；截图由 browser-use 的真实页面状态生成并逐张查看。

## 覆盖结果

| 编号 | 功能 / 页面 | 操作与预期 | 结果 | 证据 |
|---|---|---|---|---|
| V1 | F-09 / F-16 / F-45 目录首页 | 10 个项目、目录在前、大小/时间/下载；页头横跨内容面 | 通过 | [F-09](evidence/2026-10-20/F-09_directory-desktop.png) |
| V2 | F-17 / F-50 / F-53 Markdown 页 | 标题、代码块语言条/复制、TOC 细轨、页头操作 | 通过 | [F-17](evidence/2026-10-20/F-17_markdown-desktop.png) |
| V3 | F-51 TOC 文字大纲 | 点击“本页目录”展开 9 个标题，面板可固定 | 通过 | [F-51](evidence/2026-10-20/F-51_toc-panel.png) |
| V4 | F-46 / F-47 / F-49 全站导航 | 打开浮岛、根目录、当前文件高亮；展开 `architecture` 不导航 | 通过 | [F-46](evidence/2026-10-20/F-46_nav-open.png) · [F-47](evidence/2026-10-20/F-47_nav-expand.png) |
| V5 | F-42 搜索弹层 | 搜索图标打开弹层；占位符“搜索文件名和内容”；Enter/Esc 键帽 | 通过 | [F-42](evidence/2026-10-20/F-42_search-popover.png) |
| V6 | F-38 / F-39 搜索结果 | 2 个文件/3 条结果；文件标题整行链接；无“命中/实时扫描” | 通过 | [F-38](evidence/2026-10-20/F-38_search-results.png) |
| V7 | F-39 文件标题跳转 | 点击 `guides/install.md` 标题行 → `/guides/install.md`，滚动到顶部 | 通过 | [F-39](evidence/2026-10-20/F-39_file-header-link.png) |
| V8 | F-40 Markdown 行定位 | 点击“第 94 行” → `/guides/install.md#L94`，目标标题高亮且滚动 | 通过 | [F-40](evidence/2026-10-20/F-40_markdown-line-target.png) |
| V9 | F-29 / F-30 / F-35 源码页 | 文件名标题、类型/大小/行数/时间标签、145 个行锚点、预览/下载 | 通过 | [F-29](evidence/2026-10-20/F-29_source-page.png) |
| V10 | F-31 大源码 | 22 MB 单行夹具：提示“已加载完整内容”，无实现说明 | 通过（夹具不是多行分块代表） | [F-31](evidence/2026-10-20/F-31_large-source.png) |
| V11 | F-25 图片放大 | 点击图片 → modal dialog、标题、焦点在 dialog | 通过 | [F-25](evidence/2026-10-20/F-25_image-zoom.png) |
| V12 | F-54 主题反馈 | 点击主题 → 切换浅色，右下短暂显示“主题：浅色” | 通过 | [F-54](evidence/2026-10-20/F-54_theme-feedback.png) |
| V13 | F-56 移动端首页 | 390×844 无横向溢出；目录可读 | 通过（长文件名换行见发现 3） | [F-56](evidence/2026-10-20/F-56_mobile-root.png) |
| V14 | F-48 移动导航 | 292px 抽屉 + 遮罩；根目录/文件可见 | 通过 | [F-48](evidence/2026-10-20/F-48_mobile-nav.png) |
| V15 | F-52 窄屏 TOC | 1200px 细轨隐藏、内联“本页目录（9）”显示 | 通过 | [F-52](evidence/2026-10-20/F-52_inline-toc.png) |
| V16 | F-15 404 页 | 标题“页面不存在”、说明、返回首页 | 通过（无面包屑见发现 2） | [F-15](evidence/2026-10-20/F-15_error-404.png) |
| V17 | F-58 Trust 拦截面 | “此目录尚未受信任”、文件名、取消/仍要打开 | 通过（无面包屑见发现 2） | [F-58](evidence/2026-10-20/F-58_trust.png) |
| V18 | F-41 文本行跳转 | 点击文本内容命中 → 源码页 `#L2`，行号被聚焦 | 通过（无目标行高亮见发现 1） | [F-41](evidence/2026-10-20/F-41_text-line-jump.png) |

## 自动化套件

本轮在同一工作树运行：

| 套件 | 结果 |
|---|---|
| `cargo test` | 50 单元 + 134 渲染兼容 + 27 golden |
| `selftest-rust.sh` | 151 项通过 |
| `browser-probe.mjs` | 163 项通过 |
| `perf-source.mjs` | 100 KB 113ms / 1 MB 72ms / 10 MB 118ms / 1 MB Rust 88ms，预算内 |
| `trust-tty.sh` | 9 项通过 |
| `smoke-artifact.sh` | 7 项通过 |
| `typecheck` / `clippy` / `fmt` | 通过 |
| `check-doc-links.mjs` | 238 条链接通过 |

自动化套件覆盖了解析器、URL、安全、Trust、CSP、源码分块、搜索、无 JS 基线与性能；
本报告只补充真实浏览器中的视觉/交互判断，不用截图替代断言。

## 发现

### 1. 小源码的行定位没有目标行高亮（F-34，P2）

- **复现**：搜索 `sample` → 点击 `preview/code/sample.h` 第 2 行。
- **预期**：跳到 `sample.h#L2`，目标行有 `.source-target-line` 高亮。
- **实际**：URL 与原生行锚点正确，行号 2 被聚焦；`.source-target-line` 数量为 0。
- **原因范围**：`web/src/islands/source.ts` 只在分块源码分支里处理 `#L<n>` 与目标行
  覆盖层；小源码分支在 `highlightSmallSource` 后直接返回。
- **影响**：小文本文件的搜索结果能跳行，但没有目标行视觉强调；分块源码不受影响。
- **证据**：[F-41](evidence/2026-10-20/F-41_text-line-jump.png)

### 2. 错误页与 Trust 页没有面包屑（F-11，P2）

- **复现**：访问 `/nope`，或未信任服务打开 `/index.md`。
- **预期**：按功能矩阵“错误页/Trust 页有路径”应显示面包屑。
- **实际**：两张页面都只有内容卡片，没有 `.crumbs`。
- **影响**：用户在这些页面失去返回路径的上下文；不影响核心跳转。
- **证据**：[F-15](evidence/2026-10-20/F-15_error-404.png) · [F-58](evidence/2026-10-20/F-58_trust.png)

### 3. 390px 目录长文件名换行难读（F-56，P3）

- **复现**：390×844 打开根目录。
- **实际**：`index.md` 显示为 `index.` / `md`，`README.md` 显示为 `READ` / `ME.md`；
  右侧还有大小、日期和下载入口。
- **影响**：没有横向溢出，但文件名被拆成多行，扫读困难。
- **证据**：[F-56](evidence/2026-10-20/F-56_mobile-root.png)

### 4. 归档文档仍会出现在搜索结果（观察项，P3）

- 搜索 `图片相对路径` 时，`archive/selftest-python.md` 与 `guides/install.md` 一起出现。
- 这是当前“搜索覆盖所有 Markdown”行为的直接结果，不是渲染错误；如果产品希望
  历史归档不出现在搜索中，需要新增排除规则（本轮未改）。

### 5. Enter 键验收的工具层注意点（非产品 Bug）

- IAB 的 Playwright `press("Enter")` 与 CUA `keypress` 在搜索框上没有触发隐式表单提交；
  但独立 Chrome CDP 使用带 `text: "\r"` 的真实 Enter 键事件后，URL 变为
  `/search?q=TOC`，表单正常提交。`browser-probe.mjs` 已把这条路径固定成
  “搜索 Enter 提交”断言。
- 结论：搜索的 Enter 提交是正常的；问题在浏览器自动化工具没有发送 Enter 的文本负载。
  后续 agent 测试应使用可见的“搜索”按钮作为视觉路径，或用真实键盘事件复核，不要
  直接把它记成产品 Bug。

## 覆盖缺口

| 功能 | 状态 | 说明 |
|---|---|---|
| F-57 打印样式 | ○ | 没有浏览器打印预览/PDF 截图断言 |
| F-66 Release tag | ○ | 需要打 `v*` tag 才能验证 release workflow |
| F-73 减少动态效果 | ○ | 没有 `prefers-reduced-motion` 的专门断言 |
| F-33 超大代码块 | 自动 | `browser-probe.mjs` 覆盖；`docs/preview/large/big.md` 不是代表性大代码块夹具 |
| F-31 分块源码 | 自动 | 22 MB 夹具是单行；15000 行分块与目标行高亮由浏览器探针覆盖 |
| F-64/F-65 构建/CI | ◐ | 本地/远程 CI 结果需在推送后确认；Windows/musl 不能在本机执行 |
| F-11 / F-34 / F-56 | ◐ | 本报告发现 1–3 |

## 提交建议

- 本轮发现不阻断核心流程；如果要求“零已知 UI 缺口”再发布，应先修发现 1–3，
  再重跑本报告中的 V9、V13、V16、V17、V18。
- 发现 4 需要产品决策：是否把 `docs/archive/` 排除出搜索。
- 发现 5 应写入 agent 测试指南，而不是产品缺陷列表。
