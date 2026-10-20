# VS Code 1.142 作为 Markdown 语义与视觉基准

**Status**: accepted；linkify / reference definition / front matter / URL normalization /
image alt 的硬边角由 [ADR 0007](0007-hard-edge-cases-use-comrak.md) 改为 comrak 行为；
页面外壳与正文阅读排版由 [ADR 0008](0008-docs-shell-and-reading-typography.md)
改为文档站风格，本 ADR 的“视觉基准”收窄为 Markdown 语义、代码高亮与渲染结构
**Supersedes**: [ADR 0001](0001-markdown-target-encoding.md) 的百分号只解一次，
[ADR 0003](0003-data-uri-images.md) 的 data URI 放行范围

目标 3 是“与 VS Code 的表现方式一致”。本机安装的是 **VS Code 1.142.0**，内置
markdown-it **14.3.2**。本决定把“一致”钉成可验证的语义与视觉基准，并明确放弃
旧版有意保留、但与 VS Code 冲突的解析行为。

## 决定

### 1. 语义：严格跟随 VS Code

以 markdown-it 14.3.2 的实测输出为准：

| 输入 | VS Code 输出 | 旧 Python 行为 |
|---|---|---|
| `中文*强调*中文` | `中文<em>强调</em>中文` | 相同（旧 README 对 CommonMark 的解释有误） |
| `2*3*4` | `2<em>3</em>4` | 字面量 |
| `a*b*c` | `a<em>b</em>c` | 字面量 |
| `文字\n---` | `<h2>文字</h2>` | 分隔线 |
| `见 https://e.com/a。结束` | 整个 `a。结束` 进 URL | `。结束` 归句子 |
| `- [x] 完成` | 字面 `[x]`，无勾选框 | 渲染 checkbox |
| 标题 | 不自动生成 `id` | 自动生成锚点 |
| 裸 HTML | 透传 | 全部转义 |
| front matter | 默认渲染为表格 | 不支持 |

同时：

- 脚注、定义列表、数学、Mermaid、emoji shortcode **不支持**（VS Code 预览默认
  不带这些；数学/Mermaid 是独立扩展，本次明确不在范围）。
- markdown-it 选项：`html: true`、`linkify: true` 且 `fuzzyLink: false`、
  `typographer: false`、`breaks: false`、`langPrefix: "language-"`。
- 裸 URL 自动链接：`https://…` 会链接，裸邮箱会变成 `mailto:`（`fuzzyEmail` 默认开启）；
  `www.example.com` 不链接（`fuzzyLink: false`）。**实现改用 comrak autolink 后
  `www.` 会链接，见 ADR 0007。**

### 2. 目标路径与协议

- **百分号解码两次**。沿用 [ADR 0001](0001-markdown-target-encoding.md) 在 VS Code
  1.141 的实测结论：`Uri.parse` 一次、webview 资源宿主一次。必须注意：
  用户实测的 `![](desk%20top.jpg)` 在单解与双解下都能渲染，它不是区分点；
  区分点是磁盘上文件名**字面**含 `%20` 时，相对链接 `desk%2520top.jpg` 在双解下
  指向 `desk top.jpg`，因此字面文件不可达。直接访问编码后的 URL 仍可命中字面文件。
- **协议校验**：复刻 VS Code 1.142 预览的 `validateLink` **覆盖逻辑**（markdown-it
  默认 + VS Code 扩展；只查 markdown-it 默认会漏掉下面两条）：
  - 拒绝 `javascript:`、`vbscript:`、`file:`；
  - 拒绝 `data:`，唯一例外是 `data:image/*;…`（任意类型，含 svg/bmp/ico/avif；
    冒号后必须有分号；`;base64` 不是必要条件）；
  - **链接与图片位置都放行**这个 `data:image` 例外（VS Code 实际如此）；
  - VS Code 还放行 `vscode:` / `vscode-insiders:` 链接；**本站拒绝**（独立浏览器
    没有处理器，是服务器偏差；ADR 0007 的范围之外）；
  - 裸 HTML 不经过这条校验，由 CSP 约束。
- 相对目标先切 `?`/`#`，再解码两次，相对当前文档目录解析，最后编码一次，
  输出根相对 URL。

### 3. 解析器与实现

- 使用 **comrak 0.56**，关闭 tasklist 扩展，开启 table / strikethrough / autolink /
  front matter；`render.unsafe = true` 透传裸 HTML。
- comrak 默认**不校验链接协议**，必须自定义 link/image 渲染器套用上表规则。
- comrak 与 markdown-it 的边角差异（列表紧凑度、HTML block、linkify 边界等）
  用 golden 差分逐条发现、逐条对齐；不在文档里声称未验证的等价性。
- Front matter：文档开头 `---` 包裹的块；默认按 VS Code 的
  `<table class="frontmatter" title="Frontmatter">` 规则渲染。值的渲染规则：
  null 为空、数组为嵌套 `<ul>`、对象为 `<code>{yaml}</code>`、日期为 ISO 字符串。
  VS Code 私有的 `data-vscode-context` 属性不生成。
- 标题不生成 `id`；任务列表不渲染 checkbox。

### 4. 视觉与高亮

- vendored VS Code 1.142.0 的 `media/markdown.css` 与 `media/highlight.css`
  （MIT / BSD-3-Clause），补 Light+/Dark+ 的 `--vscode-*` 变量，
  `prefers-color-scheme` 自动切换。
- 代码高亮使用**完整 highlight.js**（约 190 种语言）在浏览器端执行；
  CSS 用 VS Code 的 `highlight.css`，语言别名映射照 VS Code 的预览逻辑。
- 不使用 syntect / TextMate 语法，也不在服务端高亮。没有 JS 时代码块是纯文本，
  仍可阅读。
- 页面的服务端 chrome（目录、面包屑、下载、回到顶部、图片放大）不属于 VS Code
  内容；它们可以保留，但不得改变 Markdown 内容的语义。

### 5. 测试

- 新增 **golden 差分**：Node 22 + `markdown-it@14.3.2` + `linkify-it@5` + YAML
  解析，按 VS Code 选项生成期望 HTML；Rust 渲染器对比。
- 旧 217 项渲染断言逐条审阅，冲突处按本 ADR 改期望。
- 345 项 HTTP 断言改为跑新二进制。

## 考虑过的替代方案

- **markdown-it-rs 0.7**：声称 100% markdown-it 兼容，自带 linkify/CJK 选项；
  但只有 2 stars、112 下载、1.0 API 未稳定，是个人 fork。作为核心解析器风险过高。
- **pulldown-cmark**：最成熟、最快，但 GFM 扩展与 front matter 要自己接，
  自定义代码更多。
- **自研移植旧解析器**：最贴近旧行为，但与核心 VS Code 目标冲突，且工作量最大。
- **自研近似 CSS**：不直接搬 VS Code 样式；会持续漂移，视觉回归成本更高。
- **服务端 syntect 高亮**：语言覆盖好，但输出与 VS Code 的 highlight.js 不同，
  还会引入 onig/C 依赖与语法数据体积。

## 后果

- 中文文档里 URL 后的全角句末标点会被吞进链接；`2*3*4` 会强调；
  `文字` + `---` 会变大标题。
- 任务列表勾选框与标题自动锚点消失；`[x](#标题)` 不会滚动。
- 文件名里字面含 `%xx` 的文件无法用相对链接打开。
- `data:image/*;…`（含 svg/bmp/ico/avif）在 Markdown 链接与图片位置都放行
  （VS Code 1.142 的 `validateLink` 覆盖）；`vscode:`/`vscode-insiders:` 链接
  VS Code 放行、本站拒绝。
- 这些后果是核心语义的 VS Code 对齐结果；linkify、reference definition、
  front matter、URL normalization、图像 alt 的硬边角按
  [ADR 0007](0007-hard-edge-cases-use-comrak.md) 采用 comrak 行为。
