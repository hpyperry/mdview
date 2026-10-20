# mdview 2.0 —— 单文件离线 Markdown 预览服务器

用一个可执行文件，把一个目录变成可浏览的文档站：Markdown 渲染、文本源码查看、
所有类型下载、全文搜索；不联网、不请求任何外部资源。Markdown 语义与代码高亮
对齐 **VS Code 1.142.0**，页面外壳采用文档站风格。

```bash
npm --prefix web ci
cargo build --release
./target/release/mdview --root docs --host 127.0.0.1
# 打开 http://127.0.0.1:8000/
```

产物是单个二进制（macOS arm64 约 **3.4 MB**，内嵌 CSS、highlight.js 与岛屿前端）。
**运行时**不需要 Python、Node 或任何动态资源；**从源码构建**需要 Node 22 +
`web/` 的 npm 依赖，`build.rs` 会在编译时生成并嵌入 `app.js`/`app.css`。
跨平台 musl 构建可先执行 `npm --prefix web run build:web`，再用
`MDVIEW_WEB_PREBUILT=web/dist` 让 build script 复用预构建产物。

## 2.0 与旧 Python 版的关系

- 旧实现（`mdview.py`、Python 测试、`dist/`）已删除；历史与缺陷台账归档在
  [`docs/legacy/SELFTEST-python.md`](docs/legacy/SELFTEST-python.md)。
- 新实现是 Rust（edition 2024），允许成熟 crate，但产物仍是单文件。
- **行为变化**（均为决策，不是回归）：
  - 裸 HTML **原样透传**，由 Trust + CSP 约束（旧实现一律转义）；
  - 不生成标题 `id`，不渲染任务列表 checkbox；
  - 裸 URL / 引用定义 / front matter / URL 与 alt 的硬边角采用 comrak 行为；
  - 非 Markdown 文本统一进入**源码查看页**；
  - 增加 Trust 拦截页、4 档 CSP、`vscode:` 链接拒绝与 data URI 策略。

决策记录：[ADR 0004](docs/adr/0004-rust-rewrite-and-dependencies.md)（Rust 重写）、
[0005](docs/adr/0005-vscode-1.142-as-oracle.md)（VS Code 基准）、
[0006](docs/adr/0006-html-trust-and-csp.md)（HTML/CSP）、
[0007](docs/adr/0007-hard-edge-cases-use-comrak.md)（comrak 硬边角）、
[0008](docs/adr/0008-docs-shell-and-reading-typography.md)（文档站外壳与排版）、
[0009](docs/adr/0009-search-scope-and-form-csp.md)（搜索与同源表单）、
[0010](docs/adr/0010-three-column-layout-and-sticky-shell.md)（三列与 sticky 外壳）、
[0011](docs/adr/0011-chunked-source-viewer.md)（大源码全文分块）、
[0012](docs/adr/0012-island-frontend-architecture.md)（岛屿前端与全宽外壳）。

## 功能

### 文档站外壳与搜索

- 所有页面共用全宽顶部栏 + 平面目录栏 + 内容面；Markdown 页在 ≥1360px
  增加 24px TOC 细轨（232 / 1fr / 24），1200–1359px 为两列，≤900px 单列；
- 内容面最大 1240px、阅读行最大 1000px；代码块、表格随内容面变宽，正文行长受限；
- 目录栏只列**当前目录**的目录与文本文件，sticky、桌面可收起、窄屏抽屉；
- 顶部栏只保留产品名、搜索图标、主题三态和侧栏开关；页面路径放在正文头部；
- 搜索：图标 + 按需弹层（`/` 打开），提交进入搜索页；文件名覆盖所有文件，
  正文覆盖 Markdown/文本；结果按文件分组，Markdown 正文命中可“打开文档”或
  “源码 Ln”，文本命中直接进源码行；
- CSP 放行同源表单（`form-action 'self'`），无 JS 时搜索图标直接进入搜索页；
- 主题：跟随系统 / 浅色 / 深色，手动选择持久化；
- 页内目录由浏览器从 h2/h3 生成（服务端不生成标题 id）；宽屏 TOC 细轨
  支持刻度跳转、浮层展开和 scroll-spy；窄屏回正文顶部；代码块有语言条与复制按钮。

### Markdown 渲染

- CommonMark + GFM 表格 / 删除线 / 自动链接；`~~x~~` 输出 `<s>`；
- Markdown 语义与代码高亮对齐 VS Code；正文采用文档阅读排版：阅读行上限 1000px、
  16px、1.7 行高；
- 客户端高亮：highlight.js 11.11.1 完整语言包，仅对明确 `language-*` 的代码块
  高亮（不做自动语言探测）；大源码按可见分块懒高亮，单块仍有大小上限；代码块
  复制按钮、图片放大遮罩、回到顶部按钮都由脚本注入（禁用 JS 时没有死按钮）；
- 表格单元格输出 `style="text-align:…"`（与 VS Code 一致，不用 `align=`）；
- 协议校验：拒绝 `javascript:` / `vbscript:` / `file:` / 非法 `data:` /
  `vscode:` / `vscode-insiders:`；`data:image/*;…` 在链接与图片位置都放行
  （VS Code 1.142 的 `validateLink` 覆盖行为）；
- 相对链接/图片改写为根相对 URL：切 `?`/`#` → 解码两次 → 相对解析 → 编码一次。

### 服务器

| 请求 | 行为 |
|------|------|
| `GET /dir/` | 目录索引：目录/文件分组、大小/时间、下载按钮；上级导航在侧栏/面包屑 |
| `GET /x.md` | 渲染为 HTML（未信任目录先出现一次确认页） |
| `GET /x.md?raw=1` | 源码查看页：行号、`id="L<n>"` 行锚点、回渲染/下载入口 |
| `GET /x.md?download=1` | 原始字节 + `Content-Disposition` |
| 已知文本扩展名/文件名 | 源码查看页（行号 + 客户端高亮）；> 256 KB 全文分块 |
| 无扩展名 | 前 512 字节无 NUL → 文本；有 NUL → 下载 |
| 图片 / PDF | 按 MIME 内联 |
| 其他 | `application/octet-stream` 下载 |
| `GET /search?q=…` | 文件名搜所有文件；正文搜 Markdown/文本；按文件分组 |
| `HEAD` / `301` / `404` | 支持；目录缺尾斜杠返回 301 |

超过 `--max-preview`（默认 20 MiB）的文件一律改为下载，`?raw=1` 也不例外。
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
| `--safe` | 关 | 只放行 `.md` 与图片 |
| `--max-preview` | `20M` | 超过则下载；`0` 不限制 |
| `--no-search` | 关 | 关闭搜索路由与搜索框 |
| `--trust` / `--untrusted` | — | 本次运行强制信任/不信任，不写配置 |
| `--security-level` | 配置或 `0` | CSP 级别 0–3 |

## Trust 与 CSP

裸 HTML 透传意味着“是否信任目录”决定页面能执行什么：

- **trusted**：直接渲染；
- **untrusted**：每个 `.md` 首次打开出现确认页 → 一次性令牌（路径绑定、60 秒、
  消费一次）；`?raw=1` 与 `?download=1` 绕过。
- 首次启动在 TTY 里询问并持久化；非交互环境默认 untrusted。
- 配置写在用户配置目录的 `trust.toml`（`directories` crate）。

CSP 四档：0 Strict（默认）、1 允许 HTTP、2 关闭（不推荐）、3 允许 localhost HTTP。
所有响应带 `X-Content-Type-Options: nosniff`；`script-src` 只信任每个响应新生成的
nonce，**没有 `'self'`**；`frame/base/object 'none'`；`form-action 'self'`
（仅用于本站搜索表单）。

## 与 VS Code 的一致性

P0 差分探针（comrak 0.56 vs markdown-it 14.3.2）在 1035 条计分语料上
**1015 条精确匹配（98.07%），0 条未解释差异**。剩余 25 条是记录在案的
accepted deviations：

- 23 条来自 comrak 的 linkify / reference definition / front matter / URL 与 alt；
- 2 条是服务器拒绝 `vscode:` / `vscode-insiders:`（VS Code 放行，但本服务器没有处理器）。

完整分类与反例见 [`docs/spikes/comrak-vs-markdown-it.md`](docs/spikes/comrak-vs-markdown-it.md)。
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
cargo test                      # 46 单元 + 134 渲染兼容 + 27 golden
cargo clippy --all-targets -- -D warnings
bash tests/selftest-rust.sh     # 125 项真二进制 HTTP 断言
node tests/browser-probe.mjs      # 85 项 headless Chrome 验收
node tests/perf-source.mjs        # 4 项源码页性能预算
bash tests/trust-tty.sh           # 9 项真实 pty 信任测试
```

- `tests/render_compat.rs`：旧 217 项渲染断言的 Rust 后继，期望按 ADR 0005/0007 更新；
- `src/server.rs`：路由、Trust、CSP、symlink、下载头、跨平台路径；
- `tests/selftest-rust.sh`：目录/301/源码/渲染/下载/搜索/MIME/嗅探/上限/端口回退/
  Trust/CSP/FIFO/symlink。

测试说明见 [`tests/README.md`](tests/README.md)。

## 目录结构

```text
md-preview/
├─ Cargo.toml / Cargo.lock / build.rs
├─ src/
│  ├─ main.rs / lib.rs
│  ├─ cli.rs        # 参数
│  ├─ trust.rs      # Trust 配置与优先级
│  ├─ server.rs     # 路由、目录、搜索、CSP、下载
│  ├─ render.rs     # comrak + VS Code 定制层
│  └─ assets.rs     # 内嵌 vendor 资产与 web 构建产物
├─ web/             # TypeScript/Preact 岛屿源码 + esbuild
│  ├─ src/islands/  # 8 个岛
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
- 搜索每次实时扫盘：文件名覆盖所有文件，正文覆盖 Markdown/文本；无索引、无编辑保存。
- 超过 256 KB 的源码页全文输出并按 500 行分块渐进绘制；无 JS 可读全文，但精确
  行号深链与懒高亮需要 JS。首次响应会携带完整源码，网络传输量随文件增大。
- Trust 判定按根目录路径字符串保存；移动目录后需要重新确认。
- 从源码构建需要 Node 22 与 `web/` 的 npm 依赖；运行时不需要。
- 无 JS 时没有 TOC 细轨/浮层、代码工具条与图片放大；正文与搜索页仍可读。
- 许可证为 MIT，见 [`LICENSE`](LICENSE)；第三方组件见 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)。

更细的边界见 [`docs/guide/advanced.md`](docs/guide/advanced.md)。
