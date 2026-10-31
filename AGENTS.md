# AGENTS.md —— mdview 改动指南

给在这个仓库里干活的 agent。用户文档看 `README.md`；文档地图看
[`docs/README.md`](docs/README.md)，功能编号与验收口径看
[`docs/reference/features.md`](docs/reference/features.md)，浏览器/自动化测试流程看
[`docs/testing/agent-guide.md`](docs/testing/agent-guide.md)。

## 这是什么

`mdview` 是 Rust 单文件离线 Markdown 预览服务器：渲染 `.md`/`.markdown`、为非
Markdown 文本提供源码查看页、检测文件编码、压缩包虚拟目录、其他文件按类型内联
或下载，并带全文搜索、Trust 拦截与 CSP。产物只有 `target/release/mdview`，运行时
零外部请求。

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

本机 `target/` 是本地副产物，不进交付物。体积基线、清理时机与命令见
[`docs/guides/build-hygiene.md`](docs/guides/build-hygiene.md)，取舍见
[ADR 0023](docs/architecture/adr/0023-dev-build-artifact-size.md)。

必须全绿：`cargo test`（88 单元 + 134 渲染兼容 + 27 golden）、274 项黑盒 HTTP、
9 项 pty 信任测试、238 项 headless Chrome 验收、4 项源码页性能预算。

## 协作流程

1. **需求先建 Issue**：写清目标、范围与验收标准；Issue 是需求的唯一入口。
2. **从 main 拉分支**：分支名用 `feat/…`、`fix/…`、`docs/…`、`chore/…` 或
   `release/…`；不在 main 上直接开发。
3. **feature/fix 配测试文档**：功能或修复完成前，在 `tests/` 下新增/更新一份人工
   复测文档。有夹具的 feature 用 `tests/fixtures/<slug>/README.md`，夹具根应能作为
   `--root` 启动（使用子目录 root 的在 README 写明确切命令）；没有新夹具的纯修复也
   建 README-only 目录，并在文档里给出实际使用的 root/入口。文档必须写清关联
   Issue/PR、启动命令、复测步骤与预期、自动化覆盖与已知限制。PR 描述链接它；新增/
   修改 F-xx 时 `docs/reference/features.md` 的测试映射也链接它。`docs/testing/`
   只放执行记录与报告，不复用为复测文档。
4. **PR 关联 Issue**：PR 描述写 `Closes #N`；CI 全绿、required checks 通过后合并。
   main 由 ruleset 保护：必须 PR、禁 force push/删除、禁止直接 push；审批数为 0
   （单人维护者可自我合并）；合并方式固定 **squash**，main 保持线性。
5. **CI 只在 PR 跑**：`ci.yml` 只监听 `pull_request`（可手动 `workflow_dispatch`）；
   main 合并后不再重复跑测试/构建；tag 的 Release workflow 负责 4 个 artifact。
6. **不直接推 main、不打 tag、不发 Release**：除非用户明确要求。
7. **发布节奏按需批量**：累计一组 feature/fix 后发 release PR，更新版本号、
   `CHANGELOG.md` 与 `docs/releases/<tag>.md`；合并后打 annotated tag；Release
   workflow 读取 notes 文件并核对 `SHA256SUMS`。不是每个 PR 都发版。
8. **紧急修复**也走 PR；直接推 main 或改历史必须得到用户明确授权。

## Agent skills

### Issue tracker

GitHub Issues in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles: `needs-triage` / `needs-info` / `ready-for-agent` /
`ready-for-human` / `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/architecture/adr/`. See
`docs/agents/domain.md`.

## 规格来源

按优先级读：

1. `docs/architecture/adr/0005-vscode-1.142-as-oracle.md`：Markdown 语义、代码高亮与渲染结构对齐 VS Code；
2. `docs/architecture/adr/0007-hard-edge-cases-use-comrak.md`：linkify / 引用定义 / front matter /
   URL 与 alt 的 accepted deviations；
3. `docs/architecture/adr/0006-html-trust-and-csp.md`：裸 HTML 透传与 Trust/CSP；
   [ADR 0008](docs/architecture/adr/0008-docs-shell-and-reading-typography.md) 文档站外壳/排版，
   [ADR 0009](docs/architecture/adr/0009-search-scope-and-form-csp.md) 搜索与同源表单；
   [ADR 0015](docs/architecture/adr/0015-html-file-preview-and-sandbox.md) HTML 文件双模式与沙箱，
   [ADR 0016](docs/architecture/adr/0016-archive-virtual-paths.md) 压缩包虚拟路径与解压缓存，
   [ADR 0017](docs/architecture/adr/0017-internal-url-query-disambiguation.md) 内部 URL 查询参数消歧，
   [ADR 0018](docs/architecture/adr/0018-markdown-extension-scope.md) Markdown 扩展名口径，
   [ADR 0019](docs/architecture/adr/0019-file-encoding-detection.md) 文件编码检测与 UTF-8 预览，
   [ADR 0020](docs/architecture/adr/0020-nav-layered-preload.md) 导航分层预载，
   [ADR 0021](docs/architecture/adr/0021-archive-format-expansion.md) 压缩包格式扩展；
4. `docs/architecture/overview.md` 与 `docs/architecture/adr/README.md`；历史重写计划在
   `docs/archive/rust-rewrite/execution-plan.md`；
5. `docs/research/comrak-vs-markdown-it.md`：P0 差分证据。

**不要“顺手修”记录在案的取舍。** 典型：标题无 id、任务列表字面量、全角句号进 URL、
`www.` 链接化、字面 `%xx` 文件名不可达。它们都有 ADR/测试钉着。

## 代码地图

| 文件 | 职责 |
|------|------|
| `src/main.rs` / `src/lib.rs` | 二进制入口；`lib.rs` 暴露模块给集成测试 |
| `src/cli.rs` | clap 参数与大小解析 |
| `src/trust.rs` | Trust 配置读写、flag/存储/询问优先级 |
| `src/server.rs` | axum 路由、目录索引、分层全站导航 JSON、源码页/大源码分块、搜索、下载、CSP、token、缓存 |
| `src/encoding.rs` | BOM/UTF-8/UTF-16 启发式/chardetng 检测、UTF-32 拒绝、UTF-8 解码与编码标签 |
| `src/render.rs` | comrak 配置 + 自定义 formatter（链接/图片/表格/删除线）+ URL 重写 |
| `src/assets.rs` | 内嵌 vendor 资产与 `OUT_DIR` 的 `app.js`/`app.css` |
| `src/archive.rs` | 压缩包检测、ZIP/tar 家族/7z 解压、路径/编码/上限、临时缓存与淘汰 |
| `build.rs` | 编译时执行 web 构建；支持 `MDVIEW_WEB_PREBUILT` |
| `web/src/` | TypeScript/Preact 岛屿源码与应用 CSS |
| `web/build.mjs` | esbuild 单入口 `app.ts` → `app.js` + `app.css` |
| `assets/` | VS Code CSS、highlight.js bundle |
| `tools/build-assets/` | 重建 highlight.js bundle |
| `tools/spike/` | P0 差分探针（不参与构建） |
| `scripts/git-hooks/` | 本地 git hooks：post-merge 在 `target/debug` 超阈值时清理 |

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
7. **搜索范围**：文件名覆盖所有文件；正文只扫 Markdown 文档（`.md`/`.markdown`）
   与文本文件，跳过隐藏目录、`SKIP_DIRS` 与超 `--max-preview` 的文件；结果按文件分组。
8. **大文本源码页全文分块**：>256 KB 仍由服务端输出全文，按 500 行分块，
   用 CSS `content-visibility: auto` 跳过离屏布局与绘制；行锚点与语法高亮由
   `web/src/islands/source.ts` 按可见块懒加载。不要恢复服务端截断、`?text=1`
   文本通道、`connect-src` 或 highlightAuto；无 JS 必须仍能读全文。
9. **岛屿边界**：9 个岛（theme/nav/search/totop/toc/linetarget/code/zoom/source）
   由 `body[data-islands]` 清单控制；岛只接管自己的控制区，服务端 HTML 是权威。
   新增交互先判断是否能归入现有岛，不要回到一个全局 DOMContentLoaded 初始化器。
10. **全站导航（分层预载）**：`/_nav?__mdview=nav` 只预载根 + 三层目录；第 3 层目录是
    占位，展开未加载目录请求 `/_nav?__mdview=nav&dir=<相对路径>`，每次只取一层；带
    `active=<当前路径>` 时额外返回祖先链脊柱，深页一次定位。客户端在本页缓存已加载
    子树、合并同一目录的在途请求；桌面端悬停约 150ms 预热下一层。页面空闲预取只取
    三层 + 脊柱，不跨页缓存。`dir` 必须是根内真实目录：拒绝 `..`、绝对路径、反斜杠与
    NUL，逐段拒绝隐藏目录/`SKIP_DIRS`，canonicalize 后必须 `starts_with(root)`。不要
    恢复整树递归或全量预取。目录行只展开、文件行才导航；每次加载默认收起，展开状态
    才存 localStorage。导航不挤压正文。读不了的目录/条目跳过并返回 `partial: true`，
    只有根目录本身不可读才 500。不要恢复“当前目录侧栏”或“目录/文件”分组文字。
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
15. **压缩包虚拟路径**：`/a.zip/docs/x.md`；真实目录优先；只有第一个压缩包段是容器，
    嵌套包按普通文件下载，不递归。支持 ZIP 容器（`.zip`/`.jar`/`.epub`/`.cbz` 等
    自然归档扩展名）、tar 家族（`.tar`/`.tar.gz`/`.tar.bz2`/`.tar.xz`）与 `.7z`；
    `.tar.zst`/RAR/单文件压缩流/Office 容器不在范围，按普通文件下载。压缩包检测发生
    在 `--max-preview` 下载判断之前；包内条目仍受 `--max-preview` 限制。
16. **压缩包解压缓存**：进程私有 0700 临时根；按 (路径, mtime, size) 复用；
    包 200 MB / 解压 1 GB / 2 万条 / 单条 100 MB；拒绝加密、多卷、绝对路径、
    `..`、软链/硬链/设备、重复路径。新增格式沿用同一上限；`.tar.xz` 必须用
    `XzReader::new_mem_limit` 限制 128 MiB 解码器内存，不要为 `.tar.zst` 引入第二套
    zstd 解码器。`--safe` 下压缩包不可见。不要恢复“把临时目录直接暴露成站点路径”
    或“每次请求重新解压”。
17. 文档与提交信息用中文，提交前缀 `feat:` / `fix:` / `docs:` / `refactor:` /
    `style:` / `test:`。
18. **内部 URL 必须带标记**：`/search?__mdview=search`、`/_nav?__mdview=nav`、
    `/_assets/<name>?__mdview=asset`。不带标记的同路径是普通文件路径：真实文件/
    目录优先，缺失即 404；不要给这些路径加回内部回退或“保留命名空间”。搜索表单
    用隐藏字段 `__mdview=search`，因为 GET 表单会替换 action 的查询串。
19. **Markdown 文档只含 `.md`/`.markdown`**：两者渲染并进入 Doc 内容搜索；
    `.mdx` 是源码/MDX，不按 comrak 渲染。
20. **目录始终列目录**：不自动寻找 `index.html`/`index.htm`；文件路径带尾斜杠
    （字面或 `%2f`）返回 404，目录缺尾斜杠仍是 301。
21. **文件编码检测**：BOM → UTF-8 校验 → UTF-16 启发式 → chardetng；只作用于
    mdview 生成的预览/搜索。HTML 原文/沙箱 iframe 不转码、不强制 charset；非 HTML
    文本的 raw/下载 charset 用检测值，UTF-32 按二进制下载；不做手动编码覆盖。
    无 BOM 中文 UTF-16 可能识别失败，检测标签必须如实写“检测编码”。
22. **`.xhtml`/`.xht`/`.mf` 是文本源码页**：包内 EPUB 章节与 JAR 清单只进源码页，
    不扩展 HTML 的 Trust/MIME 路径；不要把 `.epub` 做成阅读器，也不执行 `.jar`/`.apk`。
23. **CSS 基线是 Chromium 86**：`web/src/styles/` 与 `assets/*.css` 不得使用
    `light-dark()`、`color-mix()`、现代颜色函数、`inset` 简写、`:is`/`:where`/`:has`、
    `@container`、CSS 嵌套、`dvh` 等基线外语法。色板是静态双色板（`:root` 浅色 +
    `prefers-color-scheme` 与 `[data-theme="dark"]` 两份深色，必须逐项一致），
    半透明层次用 `--topbar-bg`/`--surface-translucent`/`--accent-wash`/`--hover`。
    改样式后跑 `node tests/check-css-baseline.mjs`（已接入 `run-all.sh`）；详见
    [ADR 0022](docs/architecture/adr/0022-browser-baseline-chromium-86.md)。旧内核
    会静默丢弃整条声明，Chrome 探针永远测不出来。

## 改哪里

| 需求 | 落点 |
|------|------|
| 新 Markdown 语法/渲染差异 | `src/render.rs` 的 comrak options 或 formatter |
| 新链接/图片协议规则 | `is_safe_link` + `tests/render_compat.rs` 正反例 |
| URL 编码/相对路径 | `rewrite_target` + `%20/%2520/%23/%3F` 测试 |
| 新路由/页面 | `src/server.rs` 的 `app`/`handle` 与 `Page` 外壳 |
| 文件编码检测/标签 | `src/encoding.rs` + `render_page`/`source_page`/`search_files`/`streaming_charset` |
| 搜索范围/结果 | `search_files` / `render_search`；正文按检测编码解码后只扫文本文件 |
| 目录行列对齐 | `list_dir` 的五列模板 + `web/src/styles/app.css` 的 `.dir-row` grid |
| 搜索结果行定位 | `render_markdown_with_sourcepos` + `web/src/islands/linetarget.ts` |
| 顶部栏/导航/页面 chrome/内容面 | `html_page`、`crumbs_html`、`nav.tsx` |
| TOC/行定位/代码条/主题/导航/大源码分块 | `web/src/islands/*` |
| 岛屿清单/水合策略 | `src/server.rs` 的 `data-islands` + `web/src/app.ts` |
| 全站导航树/接口 | `src/server.rs` 的 `/_nav?__mdview=nav`、`nav_payload`/`nav_dir_payload` + `web/src/islands/nav.tsx` |
| 内部 URL/搜索/资产路由 | `internal_marker` + `search`/`nav`/`asset_or_file`；表单用隐藏 `__mdview` 字段 |
| HTML 文件路由 | `handle` 的 `Kind::Html`、`html_trusted_document`、`html_preview_page`、`html_preview_document` |
| HTML 子资源 MIME | `fetch_kind` / `raw_mime`；直接导航仍走 `source_page` |
| HTML 页面样式 | `web/src/styles/app.css` 的 `.html-toolbar` / `.html-frame` |
| SVG 直开安全 | `serve_file` 的 `SVG_SANDBOX_CSP` |
| 压缩包虚拟路径/解压 | `src/archive.rs` + `handle`/`handle_archive`/`handle_file` |
| 新压缩格式/扩展名 | `src/archive.rs` 的 `ArchiveKind`/`ZIP_CONTAINER_EXT`/`extract_*`；先补夹具与 xz 内存上限 |
| .xhtml/.mf 源码页 | `src/server.rs` 的 `TEXT_EXT`/`source_language_label`/`highlight_language` |
| 压缩包页面 | `ArchiveView` + `list_dir_with` 的包根页头 |
| CSP/安全级别 | `csp_header` + `csp_levels` 测试 |
| Trust 配置 | `src/trust.rs` + 配置往返测试 |
| 页面样式 | `web/src/styles/app.css`；VS Code 样式在 `assets/*.css` |
| feature/fix 人工复测文档 | `tests/fixtures/<slug>/README.md`；纯修复可用 README-only 目录，PR 与 F-xx 链接 |
| 构建管线 | `build.rs`、`web/build.mjs`、`web/package.json` |
| 高亮语言包 | `tools/build-assets/`，重新生成 `assets/highlight.min.js` |

## 容易踩的坑

- **内部 URL**：内部请求必须带 `__mdview=search|nav|asset`；无标记的 `/search`、
  `/_nav`、`/_assets/*` 是普通文件路径，真实文件优先、缺失 404。GET 搜索表单用
  隐藏字段，不要把标记只放在 action 查询串里。
- **Markdown 扩展名**：只有 `.md`/`.markdown` 渲染并进 Doc 搜索；`.mdx` 是源码/MDX，
  不要按 comrak 渲染。
- **尾斜杠与 index**：文件路径带尾斜杠（含 `%2f`）404；目录缺尾斜杠 301；目录始终
  列目录，不自动寻找 `index.html`/`index.htm`。
- **文件编码**：预览/搜索先按检测编码解码再输出 UTF-8；HTML 原文不转码；非 HTML
  文本 raw/下载 charset 用检测值（小写，如 `charset=gbk`），HTML 不带 charset；
  UTF-32 不预览。标签写“编码”，不要承诺“真实编码”。
- **图片被包 `<a class="zoom">`**：父节点是链接时不包（徽章）；href 必须与 src
  逐字节相同。
- **表格对齐**：必须输出 `style="text-align:…"`，不是 `align="…"`。
- **`<s>` 不是 `<del>`**。
- **被拒链接**只渲染标签文本，不产出 `href`；被拒图片只渲染 alt 文本。
- **front matter 空块** `---\n---` 不是 front matter，会输出两个 `<hr>`。
- **尖括号引用定义** `[r]: <a b.md>` 是 accepted comrak deviation，不要加预扫描。
- **搜索正文**只扫 Markdown 文档（`.md`/`.markdown`）与按文本处理的文件，跳过隐藏
  目录、`node_modules` 等；超过 `--max-preview` 的文件跳过。Markdown 内容行链接到
  渲染页 `#L<n>`，文本内容行到源码行，文件标题/文件条目到文件开头；不要恢复独立的
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
- **导航不要回退**：`/_nav?__mdview=nav` 只预载三层 + 当前路径脊柱，展开走
  `&dir=` 单层接口；`children` 缺失是“未加载”，`children: []` 才是空目录。`dir`
  必须逐段校验（`..`/绝对路径/反斜杠/NUL/隐藏目录/`SKIP_DIRS`）并 canonicalize；
  `active` 只用于选脊柱，无效就忽略。导航只导航文件；目录行只展开。中间目录页
  是一张统一列表，没有“目录/文件”分组标题。
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
- **safe 模式**：`.md`/`.markdown` 渲染，`.html` 只给源码；压缩包与文本仍 404；
  搜索也只覆盖放行类型。不要把 HTML 预览放进 safe。
- **触屏目录行**：`.dir-row .dl` 由 `@media (hover: none)` 常显；不要改回只靠 hover。目录操作只用图标，用 `title` + `aria-label` 提供悬浮/无障碍文本；每个图标点击区 36×36、间距 8，不要贴在一起；不要再加行内“下载”文字，否则会破坏固定列。
- **目录行固定列**：桌面是 `图标 / 名称 / 大小 / 修改时间 / 操作` 五列；HTML 的源码图标不能挤动大小/时间列。`list_dir` 的行模板必须保持五个 grid 子项（目录行用 `row-kind` 跨 3–4 列），≤720px 才隐藏大小/时间。
- **压缩包路径**：URL 里的条目路径也要过 `safe_entry_path`；不要只依赖解压时的
  canonicalize，否则 `..` 会变成同一包内的别名 URL。
- **压缩包临时根**：macOS 的 `/var` 与 `/private/var` 会让 `starts_with` 误判；
  缓存里存 canonical 后的 root，再和条目 canonical 比较。
- **压缩包与 max-preview**：容器可以大于 `--max-preview` 仍可浏览；条目预览仍按
  `--max-preview` 下载。检测顺序不要反过来。
- **嵌套压缩包**：只把第一个压缩包段当容器；包内 `.zip` 只当普通文件，不能再解压。
- **压缩包格式识别**：tar 别名（`.tbz2`/`.tbz`/`.txz`）先于 `.tar` 判断；ZIP 容器
  只认 `ZIP_CONTAINER_EXT` 白名单；`.tar.zst`、RAR、单文件流、Office 容器不要误加。
  标签：tar 别名归一为 `tar.bz2`/`tar.xz`，ZIP 容器显示扩展名（`JAR`/`EPUB`/`CBZ`）。
- **xz 解码内存**：`.tar.xz` 必须用 `XzReader::new_mem_limit`（128 MiB），不要退回
  无上限的 `XzReader::new`；高字典包应整包拒绝。
- **`.xhtml`/`.mf`**：只加入 `TEXT_EXT` 走源码页，不要加进 `is_html_path`；`.epub`
  不是阅读器，`.jar`/`.apk` 不执行。
- **文件大小**统一走 `format_size`：1024 进制、KB 起步、1 位小数去尾零；
  不要直接输出 B/KiB。
- **`target/` 体积**：Cargo 不回收陈旧指纹，长期工作副本能到数 GB（干净基线约
  700 MB）。超过 2 GB 或 `deps/` 里指纹套数多于 2–3 套就 `cargo clean` 或
  `rm -rf target/debug`；重建只要几十秒。dev profile 是 `debug = 1`，需要变量级
  调试时用 `CARGO_PROFILE_DEV_DEBUG=2 cargo build`，用完清掉那套指纹。
  仓库带一个 post-merge hook，装一次（`bash scripts/install-git-hooks.sh`）就会在
  合并后按同一阈值自动清；没装时只有文档约定。

## 测试约定

- 功能验收先看 [`docs/reference/features.md`](docs/reference/features.md) 的 `F-xx`；
  新功能追加编号，不重排旧编号。
- 渲染层断言放 `tests/render_compat.rs`；路由/安全放 `src/server.rs` 的测试模块；
  真二进制行为放 `tests/selftest-rust.sh`。
- 每个 feature/fix 的人工复测文档放 `tests/fixtures/<slug>/README.md`；有夹具时目录
  带启动命令和可直接服务的文件，纯修复可 README-only。README 是复测文档（步骤、
  预期、自动化覆盖、已知限制），不是 `docs/testing/` 的执行报告；PR 与 `F-xx` 链接它。
- 自动测试从夹具目录复制，不把唯一夹具散落在临时脚本里。
- 全量本地验收跑 `bash tests/run-all.sh`；文档移动/改链接后先跑
  `node tests/check-doc-links.mjs`。
- 浏览器/视觉验收遵循 [`docs/testing/agent-guide.md`](docs/testing/agent-guide.md)：
  browser-use/Computer Use + 截图证据；自动探针与视觉验收不能互相替代。
- 断言与实现冲突时，先核对 ADR；accepted deviation 必须在测试名/注释里写明。
- 修 bug 时先写能复现的断言，再修。
- 性能断言只拦平方级退化，上界故意宽松（debug 构建也要过）。
- 用户没有明确要求时，不 push、不触发远程 CI。
