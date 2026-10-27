# mdview 2.1 —— 单文件离线 Markdown 预览服务器

用一个可执行文件，把一个目录变成可浏览的文档站：Markdown 渲染、文本源码查看、
压缩包虚拟目录、所有类型下载、全文搜索；不联网、不请求任何外部资源。Markdown 语义与代码高亮
对齐 **VS Code 1.142.0**，页面外壳采用文档站风格。

文档地图见 [`docs/README.md`](docs/README.md)，功能矩阵见
[`docs/reference/features.md`](docs/reference/features.md)，测试与浏览器验收见
[`docs/testing/`](docs/testing/)。

```bash
npm --prefix web ci
cargo build --release
./target/release/mdview --root docs --host 127.0.0.1
# 打开 http://127.0.0.1:8000/
```

产物是单个二进制（macOS arm64 约 **4.3 MB**，内嵌 CSS、highlight.js、岛屿前端与压缩包解码器）。
**运行时**不需要 Python、Node 或任何动态资源；**从源码构建**需要 Node 22 +
`web/` 的 npm 依赖，`build.rs` 会在编译时生成并嵌入 `app.js`/`app.css`。
跨平台 musl 构建可先执行 `npm --prefix web run build:web`，再用
`MDVIEW_WEB_PREBUILT=web/dist` 让 build script 复用预构建产物。

## 2.x 与旧 Python 版的关系

- 旧实现（`mdview.py`、Python 测试、`dist/`）已删除；历史与缺陷台账归档在
  [`docs/archive/selftest-python.md`](docs/archive/selftest-python.md)。
- 新实现是 Rust（edition 2024），允许成熟 crate，但产物仍是单文件。
- **行为变化**（均为决策，不是回归）：
  - 裸 HTML **原样透传**，由 Trust + CSP 约束（旧实现一律转义）；
  - 不生成标题 `id`，不渲染任务列表 checkbox；
  - 裸 URL / 引用定义 / front matter / URL 与 alt 的硬边角采用 comrak 行为；
  - 非 Markdown 文本统一进入**源码查看页**；
  - 压缩包以虚拟目录预览（ZIP、tar 家族、7z），包内条目复用 Markdown/HTML/源码/图片/下载管线；
    ZIP 容器（`.jar`/`.epub`/`.cbz` 等）按归档浏览；嵌套包不递归解压；
  - 增加 Trust 拦截页、4 档 CSP、`vscode:` 链接拒绝与 data URI 策略。

决策记录：[ADR 0004](docs/architecture/adr/0004-rust-rewrite-and-dependencies.md)（Rust 重写）、
[0005](docs/architecture/adr/0005-vscode-1.142-as-oracle.md)（VS Code 基准）、
[0006](docs/architecture/adr/0006-html-trust-and-csp.md)（HTML/CSP）、
[0007](docs/architecture/adr/0007-hard-edge-cases-use-comrak.md)（comrak 硬边角）、
[0008](docs/architecture/adr/0008-docs-shell-and-reading-typography.md)（文档站外壳与排版）、
[0009](docs/architecture/adr/0009-search-scope-and-form-csp.md)（搜索与同源表单）、
[0010](docs/architecture/adr/0010-three-column-layout-and-sticky-shell.md)（三列与 sticky 外壳）、
[0011](docs/architecture/adr/0011-chunked-source-viewer.md)（大源码全文分块）、
[0012](docs/architecture/adr/0012-island-frontend-architecture.md)（岛屿前端与全宽外壳）、
[0013](docs/architecture/adr/0013-full-site-navigation-island.md)（全站导航浮岛与默认收起）、
[0014](docs/architecture/adr/0014-markdown-line-target.md)（Markdown 搜索结果行定位到渲染块）、
[0015](docs/architecture/adr/0015-html-file-preview-and-sandbox.md)（HTML 文件双模式与沙箱预览）、
[0016](docs/architecture/adr/0016-archive-virtual-paths.md)（压缩包虚拟路径与解压缓存）、
[0017](docs/architecture/adr/0017-internal-url-query-disambiguation.md)（内部 URL 查询参数消歧）、
[0018](docs/architecture/adr/0018-markdown-extension-scope.md)（Markdown 扩展名口径）、
[0019](docs/architecture/adr/0019-file-encoding-detection.md)（文件编码检测与 UTF-8 预览）、
[0020](docs/architecture/adr/0020-nav-layered-preload.md)（全站导航三层预载与按需展开）、
[0021](docs/architecture/adr/0021-archive-format-expansion.md)（tar 家族与 ZIP 容器扩展）。

## 功能

### 文档站外壳与搜索

- 所有页面共用全宽顶部栏 + 内容面；Markdown 页在 ≥1360px 增加 24px TOC 细轨，
  悬停或键盘聚焦时向左展开带文字大纲；901–1359px 为单列，≤900px 单列；导航是
  默认收起的浮层，不占用正文网格；
- 内容面最大 1240px、阅读行最大 1000px；页头横跨内容面（左右 30px），正文仍
  保持阅读行；搜索页表单在页头右侧，窄屏自动换行；代码块、表格随内容面变宽；
- 全站导航树只预载根 + 三层目录，更深目录按需展开；空闲预取带当前路径脊柱，
  深页打开导航也能一次定位当前文件；目录行只展开/收起，文件行才导航；当前路径
  自动展开，用户展开状态本地记忆；桌面端悬停目录会预热下一层；
- 顶部栏只保留产品名、搜索图标、主题三态和导航开关；页面路径放在正文头部；
- 导航默认收起，每次加载都收起；桌面浮岛覆盖、不挤压正文，≤900px 为抽屉 + 遮罩；
- 搜索：图标 + 按需弹层（`/` 打开），提交进入搜索页；文件名覆盖所有文件，
  正文覆盖 Markdown/文本；每条结果整行是链接：Markdown 内容行跳到渲染页的
  对应块并高亮，文件标题与文件条目跳到文件开头；不再有独立的打开按钮；
- 文件大小统一按 1024 进制显示 KB/MB/GB，0 字节为 `0 KB`，1–1023 字节为 `<1 KB`；
- CSP 放行同源表单（`form-action 'self'`）与导航 JSON（`connect-src 'self'`），
无 JS 时搜索图标直接进入搜索页、导航入口隐藏；
- 主题：跟随系统 / 浅色 / 深色，手动选择持久化；点击后按钮旁短暂显示当前模式，
  存储写入失败也仍可继续切换；
- 页内目录由浏览器从 h2/h3 生成（服务端不生成标题 id）；宽屏 TOC 细轨支持刻度
  跳转、悬停展开文字大纲、固定/收起与 scroll-spy；窄屏回正文顶部；代码块有
  语言条与复制按钮。

### Markdown 渲染

- Markdown 文档指 `.md` / `.markdown`（大小写不敏感）；`.mdx` 是源码文本，不按
  Markdown 渲染；
- CommonMark + GFM 表格 / 删除线 / 自动链接；`~~x~~` 输出 `<s>`；
- Markdown 语义与代码高亮对齐 VS Code；正文采用文档阅读排版：阅读行上限 1000px、
  16px、1.7 行高；渲染页带 `data-sourcepos`，供搜索结果行定位到对应块；
- 客户端高亮：highlight.js 11.11.1 完整语言包，仅对明确 `language-*` 的代码块
  高亮（不做自动语言探测）；大源码按可见分块懒高亮，单块仍有大小上限；代码块
  复制按钮、图片放大遮罩、回到顶部按钮都由脚本注入（禁用 JS 时没有死按钮）；
- 表格单元格输出 `style="text-align:…"`（与 VS Code 一致，不用 `align=`）；
- 协议校验：拒绝 `javascript:` / `vbscript:` / `file:` / 非法 `data:` /
  `vscode:` / `vscode-insiders:`；`data:image/*;…` 在链接与图片位置都放行
  （VS Code 1.142 的 `validateLink` 覆盖行为）；
- 相对链接/图片改写为根相对 URL：切 `?`/`#` → 解码两次 → 相对解析 → 编码一次。

### 文件编码

- 预览与搜索先按 BOM、UTF-8 校验、UTF-16 启发式和 chardetng 检测文件编码，
  再解码成 Unicode 输出 UTF-8；GBK、Shift_JIS、UTF-16（BOM）等不再按 UTF-8
  lossy 显示。
- Markdown 页头与源码页显示检测编码；BOM 显示 ` BOM`，解码出现替换字符时显示
  `（有替换）`。
- 下载与 raw 子资源保留原始字节；非 HTML 文本的 `Content-Type` charset 使用检测
  值（流式响应只看前 64 KiB），HTML 响应保持 `text/html` 不带 charset，由 BOM/
  `meta charset` 决定。
- 检测是启发式的：短小 legacy 文件可能误判，无 BOM 且以非 ASCII 为主的中文
  UTF-16 可能识别失败；UTF-32 不预览，按二进制下载。本轮不提供手动编码覆盖。

### 服务器

| 请求 | 行为 |
|------|------|
| `GET /dir/` | 目录索引：无分组统一列表（目录在前）、名称/大小/时间/操作固定列、下载按钮；上级导航在面包屑；不自动寻找 `index.html`/`index.htm` |
| `GET /x.md` | 渲染为 HTML（未信任目录先出现一次确认页）；页头显示检测编码 |
| `GET /x.md?raw=1` | 源码查看页：文件名为标题，类型/大小/行数/编码名/时间标签、行号、`id="L<n>"` 行锚点、预览/下载入口 |
| `GET /x.md?download=1` | 原始字节 + `Content-Disposition`；非 HTML 文本 charset 用检测值 |
| `GET /x.html` | 已信任根：原字节 `text/html` 顶层返回，无外壳/沙箱；未信任根：外壳 + 沙箱 iframe（可切源码） |
| `GET /x.html?raw=1` | HTML 源码页；可信/未信任都可用 |
| `GET /x.html?view=1` | 裸页：已信任根是原文；未信任根是沙箱裸页（CSP `sandbox`） |
| `GET /x.html?download=1` | 原始字节 + `Content-Disposition`；保持 `text/html` 不带 charset |
| `GET /a.zip/` | 压缩包虚拟目录：包名/格式/大小/条目数与“下载压缩包”；包内目录与文件复用目录列表 |
| `GET /a.zip/docs/x.md` | 包内条目；Markdown/源码/图片/PDF/HTML 走现有管线；相对链接保持在包内 |
| `GET /a.zip?download=1` | 下载原压缩包 |
| `GET /a.zip/docs/x?download=1` | 下载解包后的条目 |
| 已知文本扩展名/文件名 | 源码查看页（文件名标题 + 类型/大小/行数/编码名/时间标签 + 行号与客户端高亮）；> 256 KB 全文分块 |
| 无扩展名 | 前 512 字节无 NUL → 文本；有 NUL → 下载 |
| 图片 / PDF | 按 MIME 内联；SVG 直开带 CSP `sandbox`，脚本不执行 |
| 其他 | `application/octet-stream` 下载 |
| `GET /search?__mdview=search&q=…` | 文件名搜所有文件；正文按检测编码解码后搜 Markdown 文档与文本；按文件分组；每条结果整行可点击；HTML 内容行到 `?raw=1#L<n>` |
| `GET /_nav?__mdview=nav` | 全站导航初始树 JSON：根 + 三层目录；可带 `active=<当前路径>` 附带祖先链；读不了的子树跳过并标记 `partial` |
| `GET /_nav?__mdview=nav&dir=<相对路径>` | 按需展开：只返回该目录的直接子项；`dir` 必须是根内真实目录，拒绝 `..`、绝对路径、反斜杠与 NUL |
| `HEAD` / `301` / `404` | 支持；目录缺尾斜杠返回 301；文件带尾斜杠（字面 `/` 或 `%2f`）返回 404 |

压缩包支持 `.zip`、`.jar`/`.war`/`.ear`/`.apk`/`.aar`/`.whl`/`.nupkg`/`.vsix`/
`.xpi`/`.ipa`/`.aab`/`.epub`/`.cbz`/`.kmz`、`.tar`、`.tar.gz`/`.tgz`、
`.tar.bz2`/`.tbz2`/`.tbz`、`.tar.xz`/`.txz` 与 `.7z`。ZIP 容器按归档浏览，
`.epub` 不等同于电子书阅读器；`.xhtml`/`.mf` 按源码页打开。嵌套包按普通文件下载，
不递归解压。
解压到进程私有临时缓存（0700），按包路径/mtime/size 复用；安全上限为包 200 MB、
解压总量 1 GB、2 万条、单条 100 MB；加密包、多卷包、绝对路径、`..`、软链/硬链、
设备文件、重复路径整包拒绝。`.tar.xz` 解码器额外限制 128 MiB 内存；`--safe` 下
压缩包不可见。`.tar.zst`、RAR、单文件 `.gz/.bz2/.xz/.zst` 与 Office/ODF 容器
（`.docx` 等）不在本轮范围，按普通文件下载。

内部 URL（搜索页、导航 JSON、内嵌 CSS/JS）必须带 `?__mdview=search|nav|asset`。
不带标记的同路径是普通文件路径：磁盘上有同名文件/目录就服务它，缺失即 404；
旧的不带标记内部 URL 不再作为别名。目录始终列目录，不自动寻找 `index.html`/
`index.htm`。

超过 `--max-preview`（默认 20 MiB）的**文档**改为下载，`?raw=1` 也不例外；
HTML 文件内部的 CSS/JS/图片等子资源按真实 MIME 返回，不受该限制（否则大图或
相对样式表会把页面弄坏）。已信任根的 HTML 是顶层同源原文：脚本、localStorage、
同源 fetch、下载和顶层链接都正常，和 Python 版/静态服务器一致；它也能读到站点
内的同源数据，所以只对可信目录开放。未信任根才使用 opaque-origin 沙箱，脚本
读不到 `/_nav?__mdview=nav`、搜索、同源文件、localStorage 或父页面；`--safe`
下只提供源码。
超过 **256 KB** 的文本源码页仍由服务端输出**全文**，按 500 行分块并用
`content-visibility: auto` 跳过离屏布局与绘制；无 JS 时同样能读到全文。
行锚点与语法高亮由脚本按可见分块懒加载。
渲染结果按 `(path, mtime, size)` 缓存，上限 128 条。

## 命令行

| 参数 | 默认 | 说明 |
|------|------|------|
| `--host` | `0.0.0.0` | 监听地址；本机使用请填 `127.0.0.1` |
| `--port` | `8000` | 起始端口 |
| `--port-tries` | `10` | 端口占用时向后尝试次数 |
| `--root` | 当前目录 | 服务根目录 |
| `--safe` | 关 | 只放行 `.md`/`.markdown`、图片与 HTML 源码；不渲染 HTML 预览；压缩包与文本不可见，搜索也只覆盖放行类型 |
| `--max-preview` | `20M` | 超过则下载；`0` 不限制 |
| `--no-search` | 关 | 关闭搜索路由与搜索框 |
| `--trust` / `--untrusted` | — | 本次运行强制信任/不信任，不写配置 |
| `--security-level` | 配置或 `0` | CSP 级别 0–3 |
| `--verbose` | 关 | 把每个请求的方法、路径、`Sec-Fetch-Dest`、状态、`Content-Type/Length` 与耗时打到 stderr；启动时打印内嵌资产尺寸 |

## Trust 与 CSP

裸 HTML 透传意味着“是否信任目录”决定页面能执行什么：

- **trusted**：直接渲染；
- **untrusted**：每个 `.md` 首次打开出现确认页 → 一次性令牌（路径绑定、60 秒、
  消费一次）；`?raw=1` 与 `?download=1` 绕过。
- 首次启动在 TTY 里询问并持久化；非交互环境默认 untrusted。
- 配置写在用户配置目录的 `trust.toml`（`directories` crate）。

独立 `.html` 由 Trust 决定：**已信任根**直接以 `text/html` 顶层返回原字节，无
mdview 外壳、无沙箱、无 CSP；脚本同源运行，链接、localStorage、同源 fetch 与
下载都像 Python 版/静态服务器。**未信任根**才用外壳 + 沙箱 iframe（`?view=1`
是沙箱裸页），脚本处于 opaque origin，读不到本站同源数据。`?raw=1` 始终是源码页；
`--safe` 下只显示源码。独立 HTML 不走 Markdown 的一次性令牌拦截面。
压缩包条目沿用服务根 Trust：trusted 包内 HTML 是原文，untrusted 包内 HTML 走沙箱。
SVG 直开始终带 `CSP: sandbox`，`<script>` 不执行（`<img>` 内嵌不受影响）。

CSP 四档：0 Strict（默认）、1 允许 HTTP、2 关闭（不推荐）、3 允许 localhost HTTP。
所有 mdview 生成页面带 `X-Content-Type-Options: nosniff`；`script-src` 只信任每个
响应新生成的 nonce，**没有 `'self'`**；`frame/base/object 'none'`（未信任 HTML
外壳仅把 `frame-src` 放宽为 `'self'`，用于自己的沙箱 iframe）；`form-action 'self'`
（仅用于本站搜索表单）。已信任 HTML 原文不套这条 CSP；未信任沙箱预览用自己的
`sandbox` CSP。

## 与 VS Code 的一致性

P0 差分探针（comrak 0.56 vs markdown-it 14.3.2）在 1035 条计分语料上
**1015 条精确匹配（98.07%），0 条未解释差异**。剩余 25 条是记录在案的
accepted deviations：

- 23 条来自 comrak 的 linkify / reference definition / front matter / URL 与 alt；
- 2 条是服务器拒绝 `vscode:` / `vscode-insiders:`（VS Code 放行，但本服务器没有处理器）。

完整分类与反例见 [`docs/research/comrak-vs-markdown-it.md`](docs/research/comrak-vs-markdown-it.md)。
新增差异必须修掉或在 ADR 中记录，不能沉默带过。

## 构建与平台

```bash
cargo build --release --locked
```

CI（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）覆盖：

| 平台 | target |
|------|--------|
| macOS arm64 | `aarch64-apple-darwin` |
| Linux x86_64 musl | `x86_64-unknown-linux-musl` |
| Linux arm64 musl | `aarch64-unknown-linux-musl` |
| Windows x86_64 | `x86_64-pc-windows-msvc`（static CRT） |

macOS / Linux / Windows 三平台跑 `cargo test` 与黑盒 HTTP 套件。

推送 `v*` tag 时，[`release.yml`](.github/workflows/release.yml) 会为四个目标构建
`.tar.gz`/`.zip`（含 `LICENSE`、README、`THIRD-PARTY-NOTICES.md`），生成
`SHA256SUMS` 并上传到 GitHub Release。CI 还会运行 `cargo audit` 与
`cargo deny check`。

## 测试

```bash
npm --prefix web ci
npm --prefix web run typecheck
cargo test                      # 88 单元 + 134 渲染兼容 + 27 golden
cargo clippy --all-targets -- -D warnings
bash tests/selftest-rust.sh     # 274 项真二进制 HTTP 断言
node tests/browser-probe.mjs      # 238 项 headless Chrome 验收
node tests/perf-source.mjs        # 4 项源码页性能预算
bash tests/trust-tty.sh           # 9 项真实 pty 信任测试
```

- `tests/render_compat.rs`：旧 217 项渲染断言的 Rust 后继，期望按 ADR 0005/0007 更新；
- `src/server.rs`：路由、Trust、CSP、symlink、下载头、跨平台路径；
- `tests/selftest-rust.sh`：目录/301/源码/渲染/下载/搜索/MIME/嗅探/上限/端口回退/
  Trust/CSP/FIFO/symlink/编码检测与 charset/导航分层预载与 `dir` 路径校验；
- `tests/fixtures/<slug>/README.md`：每个 feature/fix 的人工复测文档；有夹具时目录
  可直接作为 `--root`，纯修复可只放 README；PR 与 `F-xx` 链接它。

一次跑完用 `bash tests/run-all.sh`。测试说明见 [`tests/README.md`](tests/README.md)；
最近一次浏览器验收见
[`docs/testing/browser-report-2026-10-27-encodings.md`](docs/testing/browser-report-2026-10-27-encodings.md)，
自主测试流程见 [`docs/testing/agent-guide.md`](docs/testing/agent-guide.md)。

## 目录结构

```text
md-preview/
├─ Cargo.toml / Cargo.lock / build.rs
├─ src/
│  ├─ main.rs / lib.rs
│  ├─ cli.rs        # 参数
│  ├─ trust.rs      # Trust 配置与优先级
│  ├─ server.rs     # 路由、目录、搜索、CSP、下载
│  ├─ encoding.rs   # 文件编码检测、BOM/UTF-32、UTF-8 解码
│  ├─ render.rs     # comrak + VS Code 定制层
│  └─ assets.rs     # 内嵌 vendor 资产与 web 构建产物
├─ web/             # TypeScript/Preact 岛屿源码 + esbuild
│  ├─ src/islands/  # 9 个岛
│  └─ src/styles/   # app.css
├─ assets/          # markdown.css / highlight.css / highlight.min.js
├─ tests/           # render_compat.rs + selftest-rust.sh + 浏览器/性能探针
├─ docs/            # 示例文档、ADR、设计、归档
├─ tools/build-assets/  # 重建 highlight.js bundle
└─ tools/spike/         # P0 差分探针
```

## 已知限制

- 标题不生成 `id`；任务列表是字面量；脚注/数学公式不渲染。
- linkify 用 comrak：`www.` 与裸邮箱会链接化，全角句号会进 URL，`&copy;` 会截断 URL。
- 引用定义的尖括号目标（`[r]: <a b.md>`）在文件末尾没有换行时可能解析失败（EOF quirk）；正常以换行结尾的文件可解析。
- front matter 被消费，不渲染成 VS Code 的表格。
- 文件名里字面含 `%xx` 的文件不能通过相对 Markdown 目标到达（双重解码的代价）。
- 文件编码检测是启发式的：短小 legacy 文件可能被误判（例如短 GBK 片段判成
  EUC-KR/Big5），无 BOM 且以非 ASCII 为主的中文 UTF-16 可能识别失败；UTF-32
  按二进制下载。本轮不提供手动编码覆盖。
- 搜索每次实时扫盘：文件名覆盖所有文件，正文覆盖 Markdown 文档/文本；无索引、无编辑保存。
- 超过 256 KB 的源码页全文输出并按 500 行分块渐进绘制；无 JS 可读全文，但精确
  行号深链与懒高亮需要 JS。首次响应会携带完整源码，网络传输量随文件增大。
- Trust 判定按根目录路径字符串保存；移动目录后需要重新确认。
- 从源码构建需要 Node 22 与 `web/` 的 npm 依赖；运行时不需要。
- 导航默认收起；无 JS 时不显示导航。目录行只展开，不进入目录页。
- 压缩包不递归解包；`.tar.zst`、RAR/RAR5、单文件压缩流与 Office/ODF 容器不在
  本轮范围。ZIP 容器只做包内容浏览，不渲染 `.epub`/`.docx` 等原生格式；
  `.xhtml` 按源码页显示，不扩展 HTML 预览。
- `.tar.xz` 的字典/解码内存上限为 128 MiB；异常大字典的包会被拒绝。大型
  `.apk`/`.jar` 仍受 2 万条目与 1 GB 解压总量限制。
- 无 JS 时没有 TOC 细轨/浮层、代码工具条与图片放大；正文与搜索页仍可读。
- 许可证为 MIT，见 [`LICENSE`](LICENSE)；第三方组件见 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)。

更细的边界见 [`docs/guides/advanced.md`](docs/guides/advanced.md)。
