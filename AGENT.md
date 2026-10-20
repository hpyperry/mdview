# AGENT.md —— mdview 改动指南

给在这个仓库里干活的 agent。用户文档看 `README.md`；这一页是改动路线图。

## 这是什么

`mdview` 是 Rust 单文件离线 Markdown 预览服务器：渲染 `.md`、为非 Markdown 文本
提供源码查看页、其他文件按类型内联或下载，并带全文搜索、Trust 拦截与 CSP。
产物只有 `target/release/mdview`，运行时零外部请求。

```bash
npm --prefix web ci
npm --prefix web run typecheck
cargo build --release
cargo test
cargo clippy --all-targets -- -D warnings
bash tests/selftest-rust.sh
```

`build.rs` 默认在编译时执行 `web/` 的 esbuild 构建；没有 Node/npm 依赖时先
`npm --prefix web ci`。跨平台 musl 构建用
`npm --prefix web run build:web` + `MDVIEW_WEB_PREBUILT=web/dist`。

必须全绿：`cargo test`（47 单元 + 134 渲染兼容 + 27 golden）、129 项黑盒 HTTP、
9 项 pty 信任测试、121 项 headless Chrome 验收、4 项源码页性能预算。

## 规格来源

按优先级读：

1. `docs/adr/0005-vscode-1.142-as-oracle.md`：Markdown 语义、代码高亮与渲染结构对齐 VS Code；
2. `docs/adr/0007-hard-edge-cases-use-comrak.md`：linkify / 引用定义 / front matter /
   URL 与 alt 的 accepted deviations；
3. `docs/adr/0006-html-trust-and-csp.md`：裸 HTML 透传与 Trust/CSP；
   [ADR 0008](docs/adr/0008-docs-shell-and-reading-typography.md) 文档站外壳/排版，
   [ADR 0009](docs/adr/0009-search-scope-and-form-csp.md) 搜索与同源表单；
4. `docs/design/new-md-view-server.md` 与 `docs/design/execution-plan.md`；
5. `docs/spikes/comrak-vs-markdown-it.md`：P0 差分证据。

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
   主网格；≥1360px 才增加 24px TOC 细轨，901–1359 单列，≤900 单列。全站导航
   是默认收起的浮层（桌面浮岛 / 移动抽屉），不占用正文列。内容面最大 1240、
   阅读行最大 1000。改布局后跑浏览器探针。
6. **目录 `rel` 带尾斜杠**：`list_dir` 入口会 `trim_end_matches('/')`；新增目录页逻辑
   注意不要拼出 `//` 或把 `/sub/` 的上级算成 `/sub/`。
7. **搜索范围**：文件名覆盖所有文件；正文只扫 Markdown/文本，跳过隐藏目录、
   `SKIP_DIRS` 与超 `--max-preview` 的文件；结果按文件分组。
8. **大文本源码页全文分块**：>256 KB 仍由服务端输出全文，按 500 行分块，
   用 CSS `content-visibility: auto` 跳过离屏布局与绘制；行锚点与语法高亮由
   `web/src/islands/source.ts` 按可见块懒加载。不要恢复服务端截断、`?text=1`
   文本通道、`connect-src` 或 highlightAuto；无 JS 必须仍能读全文。
9. **岛屿边界**：8 个岛（theme/nav/search/totop/toc/code/zoom/source）由
   `body[data-islands]` 清单控制；岛只接管自己的控制区，服务端 HTML 是权威。
   新增交互先判断是否能归入现有岛，不要回到一个全局 DOMContentLoaded 初始化器。
10. **全站导航**：`/_nav` 返回全站可见目录与所有文件；首次打开才 fetch，目录行
    只展开、文件行才导航；每次加载默认收起，展开状态才存 localStorage。导航
    不挤压正文。不要恢复“当前目录侧栏”或“目录/文件”分组文字。
11. 文档与提交信息用中文，提交前缀 `feat:` / `fix:` / `docs:` / `refactor:` /
    `style:` / `test:`。

## 改哪里

| 需求 | 落点 |
|------|------|
| 新 Markdown 语法/渲染差异 | `src/render.rs` 的 comrak options 或 formatter |
| 新链接/图片协议规则 | `is_safe_link` + `tests/render_compat.rs` 正反例 |
| URL 编码/相对路径 | `rewrite_target` + `%20/%2520/%23/%3F` 测试 |
| 新路由/页面 | `src/server.rs` 的 `app`/`handle` 与 `Page` 外壳 |
| 搜索范围/结果 | `search_files` / `render_search`；正文只扫文本文件 |
| 顶部栏/导航/页面 chrome/内容面 | `html_page`、`crumbs_html`、`nav.tsx` |
| TOC/代码条/主题/导航/大源码分块 | `web/src/islands/*` |
| 岛屿清单/水合策略 | `src/server.rs` 的 `data-islands` + `web/src/app.ts` |
| 全站导航树/接口 | `src/server.rs` 的 `/_nav` + `web/src/islands/nav.tsx` |
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
- **搜索只扫 `.md`**，跳过隐藏目录、`node_modules` 等；超过 `--max-preview` 的文件跳过。
- **`?raw=1` 是 HTML 源码查看页**，不是原始字节；原始字节用 `?download=1`。
- **`serve_file` 的 `Content-Disposition`** 已做 ASCII fallback + RFC 5987 编码；
  文件名来自磁盘，必须继续防 CR/LF/引号注入。
- **客户端代码在 `web/src/`**：不要再改/恢复 `assets/mdview.js`；改完先
  `npm --prefix web run typecheck`，`cargo build` 会自动重跑 esbuild。
- **岛清单**：`body[data-islands]` 与页面实际控制区必须一致；源码页不要挂 `toc`，
  非文档页不要挂 `toc`/`code`/`zoom`，否则会出现空岛或错误初始化。
- **导航不要回退**：`/_nav` 是懒加载全站树，导航只导航文件；目录行只展开。
  中间目录页是一张统一列表，没有“目录/文件”分组标题。

## 测试约定

- 渲染层断言放 `tests/render_compat.rs`；路由/安全放 `src/server.rs` 的测试模块；
  真二进制行为放 `tests/selftest-rust.sh`。
- 断言与实现冲突时，先核对 ADR；accepted deviation 必须在测试名/注释里写明。
- 修 bug 时先写能复现的断言，再修。
- 性能断言只拦平方级退化，上界故意宽松（debug 构建也要过）。
