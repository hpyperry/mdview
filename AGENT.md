# AGENT.md —— mdview 改动指南

给在这个仓库里干活的 agent。用户文档看 `README.md`；文档地图看
[`docs/README.md`](docs/README.md)，功能编号与验收口径看
[`docs/reference/features.md`](docs/reference/features.md)，浏览器/自动化测试流程看
[`docs/testing/agent-guide.md`](docs/testing/agent-guide.md)。

## 这是什么

`mdview` 是 Rust 单文件离线 Markdown 预览服务器：渲染 `.md`、为非 Markdown 文本
提供源码查看页、其他文件按类型内联或下载，并带全文搜索、Trust 拦截与 CSP。
产物只有 `target/release/mdview`，运行时零外部请求。

```bash
npm --prefix web ci
npm --prefix web run typecheck
cargo build --release
bash tests/run-all.sh
```

`tests/run-all.sh` 包含 Rust 测试、fmt/clippy、文档链接检查、黑盒 HTTP、TTY Trust、
浏览器探针、性能预算与 artifact 冒烟；也可以按需单跑。

`build.rs` 默认在编译时执行 `web/` 的 esbuild 构建；没有 Node/npm 依赖时先
`npm --prefix web ci`。跨平台 musl 构建用
`npm --prefix web run build:web` + `MDVIEW_WEB_PREBUILT=web/dist`。

必须全绿：`cargo test`（56 单元 + 134 渲染兼容 + 27 golden）、183 项黑盒 HTTP、
9 项 pty 信任测试、192 项 headless Chrome 验收、4 项源码页性能预算。

## 规格来源

按优先级读：

1. `docs/architecture/adr/0005-vscode-1.142-as-oracle.md`：Markdown 语义、代码高亮与渲染结构对齐 VS Code；
2. `docs/architecture/adr/0007-hard-edge-cases-use-comrak.md`：linkify / 引用定义 / front matter /
   URL 与 alt 的 accepted deviations；
3. `docs/architecture/adr/0006-html-trust-and-csp.md`：裸 HTML 透传与 Trust/CSP；
   [ADR 0008](docs/architecture/adr/0008-docs-shell-and-reading-typography.md) 文档站外壳/排版，
   [ADR 0009](docs/architecture/adr/0009-search-scope-and-form-csp.md) 搜索与同源表单；
   [ADR 0015](docs/architecture/adr/0015-html-file-preview-and-sandbox.md) HTML 文件双模式与沙箱，
   [ADR 0016](docs/architecture/adr/0016-archive-virtual-paths.md) 压缩包虚拟路径（待实现）；
4. `docs/architecture/overview.md` 与 `docs/architecture/execution-plan.md`；
5. `docs/research/comrak-vs-markdown-it.md`：P0 差分证据。

**不要“顺手修”记录在案的取舍。** 典型：标题无 id、任务列表字面量、全角句号进 URL、
`www.` 链接化、字面 `%xx` 文件名不可达。它们都有 ADR/测试钉着。

## 代码地图

| 文件 | 职责 |
|------|------|
| `src/main.rs` / `src/lib.rs` | 二进制入口；`lib.rs` 暴露模块给集成测试 |
| `src/cli.rs` | clap 参数与大小解析 |
| `src/trust.rs` | Trust 配置读写、flag/存储/询问优先级 |
| `src/server.rs` | axum 路由、目录索引、全站导航 JSON、源码页/大源码分块、搜索、下载、CSP、token、缓存 |
| `src/render.rs` | comrak 配置 + 自定义 formatter（链接/图片/表格/删除线）+ URL 重写 |
| `src/assets.rs` | 内嵌 vendor 资产与 `OUT_DIR` 的 `app.js`/`app.css` |
| `build.rs` | 编译时执行 web 构建；支持 `MDVIEW_WEB_PREBUILT` |
| `web/src/` | TypeScript/Preact 岛屿源码与应用 CSS |
| `web/build.mjs` | esbuild 单入口 `app.ts` → `app.js` + `app.css` |
| `assets/` | VS Code CSS、highlight.js bundle |
| `tools/build-assets/` | 重建 highlight.js bundle |
| `tools/spike/` | P0 差分探针（不参与构建） |

## 硬约束

1. **单文件、零外部请求**：所有 CSS/JS/图片资产 `include_str!`/`include_bytes!`
   进二进制；页面不得出现外部 `<link>`/`<script src>`。
2. **安全边界是自定义层，不能交给 comrak**：
   - 链接/图片一律过 `is_safe_link`；拒绝 `javascript:`/`vbscript:`/`file:`/
     非法 `data:`/`vscode:`；`data:image/*;…` 是唯一放行例外；
   - 裸 HTML 虽然透传，但 CSP 的 `script-src` 只信任 per-response nonce，
     不得加 `'self'` 或 `'unsafe-inline'`；
   - 未信任目录的一次性令牌绑定路径、60 秒、消费一次；
   - 路径必须 canonicalize 后检查 `starts_with(root)`；拒绝 NUL/反斜杠。
3. **URL 管线只有 `rewrite_target` 一条路**：切 `?`/`#` → 解码两次 → 相对解析 →
   编码一次 → 根相对。链接与图片共用；不要在别处再实现一份。
4. **渲染缓存**键是 `(path, mtime, size)`；改动渲染器后确认
   `render_cache_invalidates_on_mtime_and_size` 仍绿。
5. **服务端不生成高亮 HTML**：只输出 `language-…` 类名，highlight.js 在浏览器执行；
   语言条、复制按钮、TOC 由 `web/src/` 的 island 运行时生成，服务端 Markdown 输出
   不得添加标题 id。

   外壳布局约束：`.app` 最大 1680、外边距 16；顶栏 sticky `top:12`；正文始终是
   主网格；≥1360px 才增加 24px TOC 细轨，悬停/聚焦展开带文字大纲；901–1359 单列，
   ≤900 单列。全站导航是默认收起的浮层（桌面浮岛 / 移动抽屉），不占用正文列。
   内容面最大 1240、阅读行最大 1000。改布局后跑浏览器探针。
6. **目录 `rel` 带尾斜杠**：`list_dir` 入口会 `trim_end_matches('/')`；新增目录页逻辑
   注意不要拼出 `//` 或把 `/sub/` 的上级算成 `/sub/`。
7. **搜索范围**：文件名覆盖所有文件；正文只扫 Markdown/文本，跳过隐藏目录、
   `SKIP_DIRS` 与超 `--max-preview` 的文件；结果按文件分组。
8. **大文本源码页全文分块**：>256 KB 仍由服务端输出全文，按 500 行分块，
   用 CSS `content-visibility: auto` 跳过离屏布局与绘制；行锚点与语法高亮由
   `web/src/islands/source.ts` 按可见块懒加载。不要恢复服务端截断、`?text=1`
   文本通道、`connect-src` 或 highlightAuto；无 JS 必须仍能读全文。
9. **岛屿边界**：9 个岛（theme/nav/search/totop/toc/linetarget/code/zoom/source）
   由 `body[data-islands]` 清单控制；岛只接管自己的控制区，服务端 HTML 是权威。
   新增交互先判断是否能归入现有岛，不要回到一个全局 DOMContentLoaded 初始化器。
10. **全站导航**：`/_nav` 返回全站可见目录与所有文件；页面空闲时预取，目录行
    只展开、文件行才导航；每次加载默认收起，展开状态才存 localStorage。导航
    不挤压正文。不要恢复“当前目录侧栏”或“目录/文件”分组文字。
11. **HTML 文件（Trust 门控）**：`trusted` 根下 `/x.html` 直接以原字节
    `text/html` 顶层返回，无 mdview 外壳、无 sandbox、无 CSP——这是 Python 版/
    静态服务器的行为，脚本、localStorage、同源 fetch、下载与顶层链接都正常。
    只有 `untrusted` 根才用外壳 + 沙箱 iframe；`?view=1` 在 untrusted 下是沙箱
    裸页，在 trusted 下就是原文。`?raw=1` 始终源码；`--safe` 只给源码。
    Trusted raw 是顶层同源，脚本能读站点数据；不要给未信任根 raw，也不要把
    Markdown 的一次性令牌扩展成 HTML raw。
12. **未信任 HTML 沙箱**：裸页必须带
    `Content-Security-Policy: sandbox ...; object-src 'none'`，iframe 带
    `sandbox="allow-scripts allow-forms allow-modals allow-popups"`。不要加
    `allow-same-origin`。`<object>`/`<embed>` 按 frame 导航处理，不能退化成无 CSP
    原始字节。外壳页只在 `PageKind::Html` 把 `frame-src` 放宽为 `'self'`；
    其他页面保持 `'none'`。沙箱只用于未信任根，不是可信文档的默认路径。
13. **HTML 子资源**：相对 CSS/JS/JSON 按 `Sec-Fetch-Dest`（退化看 `Accept`）返回
    原字节与真实 MIME；直接导航仍是源码页。`--max-preview` 只限制文档，不限制
    子资源。HTML 内容命中在搜索里必须链到 `?raw=1#L<n>`。
14. **SVG 直开**：`image/svg+xml` 响应必须带
    `Content-Security-Policy: sandbox allow-top-navigation-by-user-activation`；
    `<img>` 内嵌不受影响。
15. 文档与提交信息用中文，提交前缀 `feat:` / `fix:` / `docs:` / `refactor:` /
    `style:` / `test:`。

## 改哪里

| 需求 | 落点 |
|------|------|
| 新 Markdown 语法/渲染差异 | `src/render.rs` 的 comrak options 或 formatter |
| 新链接/图片协议规则 | `is_safe_link` + `tests/render_compat.rs` 正反例 |
| URL 编码/相对路径 | `rewrite_target` + `%20/%2520/%23/%3F` 测试 |
| 新路由/页面 | `src/server.rs` 的 `app`/`handle` 与 `Page` 外壳 |
| 搜索范围/结果 | `search_files` / `render_search`；正文只扫文本文件 |
| 目录行列对齐 | `list_dir` 的五列模板 + `web/src/styles/app.css` 的 `.dir-row` grid |
| 搜索结果行定位 | `render_markdown_with_sourcepos` + `web/src/islands/linetarget.ts` |
| 顶部栏/导航/页面 chrome/内容面 | `html_page`、`crumbs_html`、`nav.tsx` |
| TOC/行定位/代码条/主题/导航/大源码分块 | `web/src/islands/*` |
| 岛屿清单/水合策略 | `src/server.rs` 的 `data-islands` + `web/src/app.ts` |
| 全站导航树/接口 | `src/server.rs` 的 `/_nav` + `web/src/islands/nav.tsx` |
| HTML 文件路由 | `handle` 的 `Kind::Html`、`html_trusted_document`、`html_preview_page`、`html_preview_document` |
| HTML 子资源 MIME | `fetch_kind` / `raw_mime`；直接导航仍走 `source_page` |
| HTML 页面样式 | `web/src/styles/app.css` 的 `.html-toolbar` / `.html-frame` |
| SVG 直开安全 | `serve_file` 的 `SVG_SANDBOX_CSP` |
| 压缩包（待实现） | ADR 0016；新增 archive 模块 + `handle` 虚拟路径解析 |
| CSP/安全级别 | `csp_header` + `csp_levels` 测试 |
| Trust 配置 | `src/trust.rs` + 配置往返测试 |
| 页面样式 | `web/src/styles/app.css`；VS Code 样式在 `assets/*.css` |
| 构建管线 | `build.rs`、`web/build.mjs`、`web/package.json` |
| 高亮语言包 | `tools/build-assets/`，重新生成 `assets/highlight.min.js` |

## 容易踩的坑

- **图片被包 `<a class="zoom">`**：父节点是链接时不包（徽章）；href 必须与 src
  逐字节相同。
- **表格对齐**：必须输出 `style="text-align:…"`，不是 `align="…"`。
- **`<s>` 不是 `<del>`**。
- **被拒链接**只渲染标签文本，不产出 `href`；被拒图片只渲染 alt 文本。
- **front matter 空块** `---\n---` 不是 front matter，会输出两个 `<hr>`。
- **尖括号引用定义** `[r]: <a b.md>` 是 accepted comrak deviation，不要加预扫描。
- **搜索正文**只扫 Markdown 与按文本处理的文件，跳过隐藏目录、`node_modules`
  等；超过 `--max-preview` 的文件跳过。Markdown 内容行链接到渲染页 `#L<n>`，
  文本内容行到源码行，文件标题/文件条目到文件开头；不要恢复独立的
  “打开文档/源码 Ln”操作按钮。UI 文案用“结果”，不要写“命中”。
- **`?raw=1` 是 HTML 源码查看页**，不是原始字节；原始字节用 `?download=1`。
- **`serve_file` 的 `Content-Disposition`** 已做 ASCII fallback + RFC 5987 编码；
  文件名来自磁盘，必须继续防 CR/LF/引号注入。
- **客户端代码在 `web/src/`**：不要再改/恢复 `assets/mdview.js`；改完先
  `npm --prefix web run typecheck`，`cargo build` 会自动重跑 esbuild。
- **岛清单**：`body[data-islands]` 与页面实际控制区必须一致；源码页不要挂 `toc`，
  非文档页不要挂 `toc`/`linetarget`/`code`/`zoom`，否则会出现空岛或错误初始化。
- **页头统一逻辑**：所有页头用 `.head-inner` 横跨内容面（左右 30px），正文阅读行
  仍由 `.markdown-body` 限制为 1000px；搜索页表单在页头右侧。不要再给页头套
  `max-width: 1000px` 的容器。
- **搜索结果行**：整条 `.hit` 是链接；Markdown 内容行到渲染页 `#L<n>`，文件标题
  与文件条目到文件开头。不要恢复独立的“打开文档/源码 Ln”按钮。
- **行定位**：`render_markdown` 默认不带 sourcepos，保持 golden/render_compat 不变；
  只有服务端渲染页调用 `render_markdown_with_sourcepos`。`linetarget` 只认块级
  元素，定位是块级近似。
- **主题切换**：模式以当前页面内存为准，localStorage 只负责持久化；写入失败不能
  卡住循环。按钮旁的状态提示是“看起来有没有生效”的反馈，不要删。
- **导航不要回退**：`/_nav` 是页面空闲时预取的全站树，导航只导航文件；目录行只展开。
  中间目录页是一张统一列表，没有“目录/文件”分组标题。
- **源码页头**：H1 是文件名，不是“源码”；下方类型/大小/行数/修改时间用标签展示，
  操作是“预览/下载”。不要恢复 `查看渲染页` 或把参数重新堆成一行纯文本。
- **H1 下划线**：`assets/markdown.css` 给全局 `h1` 加了 `border-bottom`；
  `web/src/styles/app.css` 的 `h1` 重置负责外壳标题。新增页面标题不要绕开它。
- **HTML 信任目录**：`/x.html` 必须是原字节顶层原文，不能套外壳/沙箱/CSP；
  这是 Python 版和静态服务器的行为。未信任根才走沙箱外壳。
- **HTML 编码**：原文强制 `text/html` 但不加 charset，让文档自己的 BOM/meta
  决定编码；不要恢复 Python 的强制 UTF-8。
- **HTML 源码**：`?raw=1` 才是源码页；trusted 的源码页“预览”tab 指向 `/x.html`
  原文，untrusted 指向沙箱外壳。
- **HTML 子资源**：`style.css` 直接访问是源码页，只有 `Sec-Fetch-Dest: style`
  之类请求才返回 `text/css`；不要把所有文本文件都改成原始 MIME。
- **HTML 搜索行**：HTML 内容命中要到 `?raw=1#L<n>`；默认 `/x.html` 现在是预览页，
  不带行锚点。
- **SVG**：`serve_file` 对 SVG 加了 CSP sandbox；不要把它挪到所有二进制响应，
  也不要删掉，否则直开 SVG 会恢复同源脚本执行。
- **safe 模式**：`.html` 只给源码；压缩包与文本仍 404。不要把 HTML 预览放进 safe。
- **触屏目录行**：`.dir-row .dl` 由 `@media (hover: none)` 常显；不要改回只靠 hover。目录操作只用图标，用 `title` + `aria-label` 提供悬浮/无障碍文本；每个图标点击区 36×36、间距 8，不要贴在一起；不要再加行内“下载”文字，否则会破坏固定列。
- **目录行固定列**：桌面是 `图标 / 名称 / 大小 / 修改时间 / 操作` 五列；HTML 的源码图标不能挤动大小/时间列。`list_dir` 的行模板必须保持五个 grid 子项（目录行用 `row-kind` 跨 3–4 列），≤720px 才隐藏大小/时间。
- **文件大小**统一走 `format_size`：1024 进制、KB 起步、1 位小数去尾零；
  不要直接输出 B/KiB。

## 测试约定

- 功能验收先看 [`docs/reference/features.md`](docs/reference/features.md) 的 `F-xx`；
  新功能追加编号，不重排旧编号。
- 渲染层断言放 `tests/render_compat.rs`；路由/安全放 `src/server.rs` 的测试模块；
  真二进制行为放 `tests/selftest-rust.sh`。
- 全量本地验收跑 `bash tests/run-all.sh`；文档移动/改链接后先跑
  `node tests/check-doc-links.mjs`。
- 浏览器/视觉验收遵循 [`docs/testing/agent-guide.md`](docs/testing/agent-guide.md)：
  browser-use/Computer Use + 截图证据；自动探针与视觉验收不能互相替代。
- 断言与实现冲突时，先核对 ADR；accepted deviation 必须在测试名/注释里写明。
- 修 bug 时先写能复现的断言，再修。
- 性能断言只拦平方级退化，上界故意宽松（debug 构建也要过）。
- 用户没有明确要求时，不 push、不触发远程 CI。
