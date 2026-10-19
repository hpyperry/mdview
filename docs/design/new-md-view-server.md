# 新版 mdview：Rust 单文件可执行 Markdown 预览服务器

**Status**: agreed（2026-10-19）
**Branch**: `refactor/new-md-view-server`
**Supersedes**: 旧 Python 单文件实现（`mdview.py` / `dist/mdview.min.py`）

这一页是本次重写的共同理解。实现以它为准；决策的理由与替代方案在
[`docs/adr/`](../adr/)。

## 1. 目标

1. **编译后的单文件可执行程序**：运行时不需要 Python、Node 或任何外部资源文件；
   前端 CSS/JS 全部嵌进二进制。
2. **静态文件服务器**：非二进制文件有预览页，所有类型都能下载；保留旧版的
   目录索引、全文搜索、源码视图、`--safe`、`--max-preview`、端口回退与 URL 契约。
3. **Markdown 渲染与 VS Code 一致**：以本机 VS Code 1.142.0 的预览为语义与视觉基准。

## 2. 已定决策

| 决策 | 结果 | 记录 |
|---|---|---|
| 实现栈 | Rust 原生重写；单 crate，产物单文件 | [ADR 0004](../adr/0004-rust-rewrite-and-dependencies.md) |
| 依赖边界 | 允许成熟 crate；Cargo.lock 入库；运行时仍完全离线 | ADR 0004 |
| 平台 | macOS arm64、Linux x86_64/arm64（musl 静态）、Windows x86_64（静态 CRT） | ADR 0004 |
| 服务器契约 | 保留旧 URL/CLI；新增 Trust 与安全级别参数 | ADR 0004 / 0006 |
| Markdown 解析器 | comrak 0.56 + 自定义渲染器补齐 VS Code 语义 | [ADR 0005](../adr/0005-vscode-1.142-as-oracle.md) |
| 语义基准 | **严格 VS Code**：不保留旧版解析偏离 | ADR 0005 |
| 视觉基准 | vendored VS Code `markdown.css` / `highlight.css` + Light+/Dark+ 变量，自动明暗 | ADR 0005 |
| 代码高亮 | 内嵌完整 highlight.js，浏览器端；与 VS Code 预览同一套 CSS | ADR 0005 |
| 裸 HTML | 始终透传；靠 Trust + CSP 约束 | [ADR 0006](../adr/0006-html-trust-and-csp.md) |
| Trust | 启动时按根目录询问；存用户配置目录；未信任时每次打开 `.md` 都拦 | ADR 0006 |
| 安全级别 | 完整复刻 VS Code 4 档（0/3/1/2），默认 Strict | ADR 0006 |
| 非二进制文本 | 统一源码查看页（行号、highlight.js、下载） | 本文 §8 |
| 旧实现/测试 | 替换 Python；旧断言审阅后移植；新增 golden 差分 | 本文 §11 |

## 3. 运行形态

```bash
mdview --root docs --host 127.0.0.1
```

- 一个可执行文件，内部嵌入 Markdown 渲染器、CSS、highlight.js、页面脚本。
- 默认 `0.0.0.0:8000`、根为当前目录，与旧版一致。
- 运行时零网络请求：页面只请求本站 `/_assets/…`，不访问 CDN。
- `--version` 输出 `mdview 2.0.0`。

## 4. 技术栈

| 层 | 选择 |
|---|---|
| HTTP | axum 0.8 + tokio 1 + tower-http 0.7 |
| CLI | clap 4 |
| Markdown | comrak 0.56（关闭 syntect/tasklist 等不需要的扩展） |
| YAML（front matter） | `serde_yml` 或 `yaml-rust2`，按 VS Code 的表格规则渲染 |
| 配置/Trust | `directories` + serde + TOML |
| 文件遍历/搜索 | `walkdir` + 标准库；搜索行为与旧版一致 |
| 前端高亮 | 完整 highlight.js 浏览器 bundle（构建期生成并入库） |
| 随机 nonce | `getrandom` / `rand` |

不引入重量级异步框架之外的东西；不使用 TLS（与旧版一致，必要时由反向代理负责）。

源码可以分模块（`src/server/`、`src/render/`、`src/assets/`、`src/trust/`），
**交付物**仍是单个二进制。

## 5. HTTP 契约

保留旧版路由与参数：

| 路由 | 行为 |
|---|---|
| `/`、`/<dir>/` | 目录索引（目录在前；名称/大小/mtime；面包屑；搜索框；每个文件带下载按钮） |
| `/<file>.md` | 渲染页；未信任根目录时先显示拦截面（见 §7） |
| `/<file>.md?open=<一次性令牌>` | 跳过本次拦截面，强制渲染；令牌用后立即失效 |
| `/<file>.md?raw=1` | 源码查看页（HTML；行锚点 `id="L<n>"`），不做 Markdown 渲染 |
| `/<file>.md?download=1` | 原始 Markdown 字节，`Content-Disposition: attachment` |
| `/<text-file>` | 统一源码查看页（HTML）；`?raw=1` 同为源码页；`?download=1` 下载原始字节 |
| `/<binary-file>` | 原样发送，正确 `Content-Type`；`?download=1` 强制附件 |
| `/search?q=…` | 全文搜索，只扫 `.md` |
| `/_assets/<hash>/<name>` | 嵌入式 CSS/JS，长缓存 |
| `/<dir>`（缺结尾 `/`） | 301 补斜杠 |
| 不存在 | 404 友好页 |
| `HEAD` | 与 `GET` 相同的头，不返回体 |

CLI：

```text
--host <addr>            默认 0.0.0.0
--port <port>            默认 8000；占用时向后重试
--port-tries <n>         默认 10
--root <dir>             默认当前目录
--safe                   只服务 .md + 图片
--max-preview <size>     默认 20M；0 = 不限制
--no-search              关闭搜索页
--trust                  本次运行强制信任
--untrusted              本次运行强制不信任
--security-level <0|3|1|2>
--version
```

`--trust` / `--untrusted` 只影响本次运行；启动时的交互回答才会写入配置。
`--security-level` 同时写入该根目录的配置项。

## 6. Markdown 渲染

### 6.1 严格 VS Code 语义

以 VS Code 1.142.0 内置的 markdown-it 14.3.2 为准，已实测：

- `中文*强调*中文` → `<em>`（CJK 强调本来就能生效，旧 README 的解释有误）。
- `2*3*4` → `2<em>3</em>4`；`a*b*c` → `a<em>b</em>c`。
- `文字` + `---` → `<h2>`（Setext），不再只当分隔线。
- 裸 URL 后的全角 `。，、；：！？` **属于 URL**；不再按句末标点剥掉。
- 任务列表 `- [x]` **不渲染勾选框**，按字面文本。
- 标题**不自动生成 `id`**；`[x](#标题)` 不会滚动到标题。
- 脚注、定义列表、数学、Mermaid、emoji shortcode 不支持。
- 裸 HTML 透传（安全模型见 §7）。
- front matter 在文档开头识别，默认渲染为表格。
- markdown-it 选项：`html: true`、`linkify: true`（`fuzzyLink: false`）、
  `typographer: false`、`breaks: false`、`langPrefix: "language-"`。

### 6.2 目标与协议

- 相对目标：先切 `?`/`#`，对路径**连续解码两次**，相对当前文档目录解析，
  再**编码一次**，输出根相对 URL。浏览器请求时还会解码一次，所以：
  - `![](desk%20top.jpg)` 命中 `desk top.jpg`（正常）；
  - 文件名**字面**含 `%20` 时，相对链接不可达（VS Code 同样如此）；
  - 直接访问编码后的 URL 仍可命中字面 `%xx` 文件。
- Markdown 生成的链接/图片目标过 markdown-it 的 `validateLink`：
  - 拒绝 `javascript:`、`vbscript:`、`file:`；
  - 拒绝一切 `data:`，**唯一例外**是 `data:image/(gif|png|jpeg|webp);…`
    （分号后不要求 `;base64`；链接与图片位置都放行，这是 VS Code 的实际行为）；
  - 裸 HTML 不经过这条校验，由 CSP 约束。
- 裸 URL 自动链接：`https://…` 会链接，裸邮箱会变成 `mailto:`
  （`fuzzyEmail` 默认开启）；`www.example.com` 不链接（`fuzzyLink: false`）。

### 6.3 comrak 需要补齐的地方

P0 差分（[报告](../spikes/comrak-vs-markdown-it.md)）确认 comrak 的核心解析可用，
但以下层必须自定义：

1. **Link/image 渲染**：套用 `validateLink` 与 §6.2 的目标重写；被拒目标按
   markdown-it 的字面/raw tail 回退（生产侧由 Trust/CSP 约束）。
2. **Linkify**：关闭 comrak 的 `extension.autolink`，用独立 pass 复刻
   markdown-it/linkify-it 的 `http(s)`、裸邮箱（`mailto:`）与边界规则；
   `www.` 不链接。
3. **Reference definition 预扫描**：合法尖括号目标（`[r]: <a b.md>`）归一化；
   被拒协议的整条定义不注册，保留为段落（与 markdown-it 一致）。
4. **Front matter**：文档开头的 `---` 块先切出，按 VS Code 规则渲染
   `<table class="frontmatter" title="Frontmatter"><tbody>…`。
5. **表格对齐**：单元格输出 `style="text-align:…"`，不是 `align="…"`。
6. **图像 alt**：复刻 markdown-it 的纯文本提取（跳过实体 token）。
7. **代码块**：输出 `<pre><code class="language-…">`，不在服务端高亮；
   `~~x~~` 输出 `<s>`（不是 `<del>`）。
8. **任务列表**：关闭 comrak 的 tasklist 扩展；标题不生成 `id`。
9. **Raw HTML**：`render.unsafe = true`。
10. **列表紧凑度、HTML block**：用 golden 差分找出剩余差异，逐条对齐；
    不在文档里声称未验证的等价性。

P0 的 26 条已知差异已在报告里逐类列出并给出修复顺序；P2 的 golden 语料必须
逐条覆盖它们。

### 6.4 视觉

- 直接使用 VS Code 1.142.0 的 `media/markdown.css` 与 `media/highlight.css`
  （MIT / BSD-3-Clause），补一套 Light+/Dark+ 的 `--vscode-*` 变量。
- `prefers-color-scheme` 自动切换；无 JS 时默认亮色，内容仍可读。
- 页面内容包在 `.markdown-body` 中；服务端 chrome（面包屑、下载、回到顶部）
  用独立 class，不复用 Markdown 内容选择器。
- 代码块使用 VS Code 的复制按钮外观；不再保留旧版的“语言条 + 代码区”两段式。
- 图片放大、回到顶部、下载按钮是本服务器的附加功能，不属于 VS Code 预览；
  它们不改变 Markdown 内容语义，但会改变图片外层的 DOM（`<a class="zoom">`）。

## 7. Trust 与 CSP

### 7.1 启动与配置

- 启动时对 `--root`（或当前目录）做一次信任询问，仅在 stdin 是 TTY 且配置里
  没有该根目录的记录时发生。
- 配置放在用户配置目录：
  - macOS：`~/Library/Application Support/mdview/trust.toml`
  - Linux：`$XDG_CONFIG_HOME/mdview/trust.toml`（默认 `~/.config/…`）
  - Windows：`%APPDATA%\mdview\trust.toml`
- 按规范化后的根目录路径记录：

```toml
[roots."/Users/hpy/docs"]
trusted = true
security_level = 0
```

- 非 TTY：使用已存记录；没有记录则默认**未信任**，打印一行提示。
- `--trust` / `--untrusted` 覆盖本次运行；交互回答才持久化。

### 7.2 未信任时的拦截面

- 每个渲染 `.md` 请求都先显示：

  > 此 Markdown 文件位于未信任目录中。仍要打开吗？
  > [取消] [仍要打开]

- 「仍要打开」= 当前 URL 加一个**一次性令牌**（`?open=<随机值>`），只对本次请求
  放行；令牌用后即失效，刷新同一 URL 或打开下一页面都会再次拦截
  （与 VS Code 每次打开预览都提示一致）。
- 令牌在服务端内存中保存（路径 + 过期时间，短 TTL），不写成可收藏的永久开关。
- `?raw=1` 与 `?download=1` 不渲染裸 HTML，不需要拦截。
- 非 md 源码查看页只做转义展示，不拦截。
- 信任状态只影响“渲染 Markdown 时是否拦”，不改变文件可读范围。

### 7.3 安全级别与 CSP

| 级别 | 名称 | CSP |
|---|---|---|
| 0 | Strict（默认） | `default-src 'none'; img-src 'self' https: data:; media-src 'self' https: data:; script-src 'nonce-<随机>'; style-src 'self' 'unsafe-inline' https: data:; font-src 'self' https: data:; frame-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'` |
| 3 | 允许 localhost HTTP | 在 0 的基础上给 img/media/style/font 加 `http://localhost:* http://127.0.0.1:*` |
| 1 | 允许 HTTP | 在 0 的基础上加 `http:` |
| 2 | Disable | 不发送 CSP，允许文档脚本执行（不推荐） |

- `script-src` **只**用 nonce，不用 `'self'`：否则磁盘上的任意 `.js` 都能被
  裸 HTML 以同源脚本加载。
- 我们的脚本标签带同一 nonce；highlight.js 也从 `/_assets/` 以 nonce 加载。
- 所有 HTML 响应加 `X-Content-Type-Options: nosniff`。
- 级别 2 只应由明确知道风险的人使用；启动横幅会警告。
- 没有 Web UI 修改安全级别（VS Code 有预览工具栏选择器）；用
  `--security-level` 或配置文件修改。这是有意的收敛，避免远程用户改安全设置。

## 8. 非二进制文件的源码查看页

- 文本判定沿用旧版三层：白名单 → MIME 表 → 前 512 字节 NUL 嗅探。
- 普通 URL 返回 HTML 查看页：服务端逐行输出 `<span id="L<n>">` 行锚点，
  highlight.js 在浏览器端着色；禁用 JS 时是带行号的纯文本。
- 行号放在独立 gutter，代码块整体交给 highlight.js，避免高亮破坏行锚点。
- 页面提供：下载按钮、复制按钮、回到顶部、面包屑。
- 超过 `--max-preview` 的文本不再预览，改为下载（沿用旧规则）。
- 图片/PDF/音视频等按浏览器可预览的 MIME 原样发送；`?download=1` 强制附件。
- `?raw=1` 对 `.md` 与普通文本统一为“源码查看页”；要磁盘原文用 `?download=1`。

## 9. 资产与单文件

- 嵌入：VS Code `markdown.css`、`highlight.css`、主题变量表、完整 highlight.js
  bundle、`mdview.js`（复制/放大/回到顶部）。
- 资产 URL 带内容哈希：`/_assets/<hash>/<name>`，`Cache-Control: immutable`。
- 二进制内不保留任何外部资源路径；启动后不读写自身目录之外的资产。
- Third-party notices：VS Code CSS（MIT）、highlight.js（BSD-3-Clause）、
  Rust crates 的许可证清单随发布包提供。

## 10. 构建与发布

- Profile：LTO、`codegen-units = 1`、`strip`；优先体积可控。
- 目标：
  - `aarch64-apple-darwin`
  - `x86_64-unknown-linux-musl`
  - `aarch64-unknown-linux-musl`
  - `x86_64-pc-windows-msvc` + `+crt-static`
- GitHub Actions matrix 构建并上传 artifact；不依赖本机交叉工具链。
- Cargo.lock 入库；CI 用 `--locked`。
- 运行时可离线；构建时需要 crates.io（或预热的 vendor 目录）。

## 11. 测试与验收

1. **Rust 单元/集成测试**：URL 重写、协议校验、front matter、源码页、
   trust/CSP、路径夹紧、MIME 判定。
2. **Golden 差分**：Node 22 + `markdown-it@14.3.2` + `linkify-it@5` + YAML 解析，
   按 VS Code 选项与 front matter 插件生成期望 HTML；Rust 渲染器对比。
   允许忽略纯空白差异与我们主动跳过的 VS Code 私有属性（如 `data-line`），
   其余结构/属性必须一致。golden 与生成脚本入库。
3. **移植旧测试**：217 项渲染断言逐条审阅，冲突处按 ADR 0005 改期望；
   345 项 HTTP 断言改为跑新二进制，并补 Trust/CSP/源码页/资产断言。
4. **安全测试**：`javascript:`/`vbscript:`/`file:`/非法 `data:` 拒绝；
   `data:image/(gif|png|jpeg|webp);` 放行；CSP 头逐级正确；nonce 每响应不同；
   路径穿越不外泄；`--safe` 生效。
5. **浏览器探针**：highlight.js 是否着色、复制/放大/回到顶部、无 JS 降级。
6. **跨平台**：CI 在 macOS/Linux/Windows 跑测试；路径分隔符与 Unicode 文件名。

## 12. 迁移步骤

可执行的工作包、决策门、依赖与粗估见
[`execution-plan.md`](execution-plan.md)。生产顺序：

1. 建 Cargo 项目；先落 CLI、静态服务、trust/config 与测试骨架。
2. 接 comrak 与自定义渲染器；golden 差分收敛。
3. 嵌入 VS Code CSS + highlight.js；实现源码查看页与前端功能。
4. 移植测试、重写 selftest.sh；更新示例语料与 README/AGENT/GLOSSARY。
5. 删除 `mdview.py`、`dist/`、`tools/minify.py`、Python 测试；旧 `SELFTEST.md`
   作为历史归档到 `docs/legacy/`，新台账重新开始。
6. 建立跨平台 CI 与发布 artifact。

## 13. 已知后果（有意接受）

- 全角句末标点会被吞进 URL；`desk%2520top.jpg` 这类相对链接不可达。
- `2*3*4` 会被强调；`文字` + `---` 会变成二级标题。
- 任务列表没有勾选框；标题没有自动 `id`，页内锚点失效。
- 裸 HTML 会渲染；安全性由 Trust/CSP 承担，级别 2 可执行文档脚本。
- 非 md 文本的普通 URL 从 `text/plain` 变成 HTML 查看页；原文用 `?download=1`。
- 二进制体积显著大于 Python 单文件；构建需要 crates.io。
- 旧的“零第三方依赖”身份结束；运行时离线与单文件交付保持不变。

## 14. 不在本次范围

- 数学（KaTeX）、Mermaid、emoji shortcode、脚注。
- 浏览器内编辑/保存。
- TLS、认证、多用户权限。
- VS Code 的滚动同步、编辑器选中映射、预览工具栏安全选择器。
