# Changelog

## 2.0.0（未发布）

Rust 重写。旧 Python 单文件实现已删除，历史台账见
[`docs/archive/selftest-python.md`](docs/archive/selftest-python.md)。

### 新增

- 单文件原生二进制（macOS arm64 / Linux x86_64+arm64 musl / Windows x86_64 static CRT）；
  内嵌 VS Code `markdown.css`、`highlight.css`、highlight.js 11.11.1 与岛屿前端。
- 源码构建引入 `web/`（TypeScript + esbuild + Preact）与 Node 22；运行时仍不需要
  Node。CI 的 musl 构建使用 `MDVIEW_WEB_PREBUILT` 复用 host 产物。
- Markdown 语义与代码高亮对齐 VS Code 1.142.0；页面外壳改为文档站风格；
  P0 差分 98.07%（1015/1035），25 条 accepted deviations 有记录。
- Trust 模型：目录级信任、未信任 `.md` 的一次性令牌拦截面、用户配置持久化。
- 4 档 CSP：nonce-only `script-src`、`frame/base/object 'none'`、
  `form-action 'self'`（仅搜索表单）、nosniff。
- 非 Markdown 文本统一源码查看页（文件名为标题、类型/大小/行数/时间标签、行号、
  行锚点、客户端高亮）。
- `data:image/*;…` 在链接与图片位置放行（VS Code 1.142 行为）；拒绝 `vscode:` 链接。
- 岛屿前端：TypeScript + esbuild 单入口，Preact 用于 TOC/代码工具条/图片放大/全站导航；
  `body[data-islands]` 控制 9 个岛，外壳立即水合、重岛空闲/可见时启动。
- 内容主导的全宽外壳：内容面最大 1240px、阅读行最大 1000px；页头横跨内容面
  （左右 30px），搜索页表单在页头右侧；≥1360px 为正文 + 24px TOC 细轨，
  901–1359px 与 ≤900px 都为单列；搜索改成顶栏图标 + 弹层，路径移入正文头部。
- 全站导航浮岛：默认收起、页面空闲时预取 `/_nav`，包含所有可见目录与文件；
  目录行只展开、文件行导航，当前路径展开、用户展开状态记忆；桌面浮岛不挤压正文，
  ≤900px 为抽屉 + 遮罩。目录页改为无分组的统一列表。
- 搜索覆盖 Markdown/文本正文与所有文件名，结果按文件分组；每条结果整行可点击，
  Markdown 内容行跳到渲染页对应块并高亮，文件标题与文件条目跳到文件开头；
  不再有独立的“打开文档/源码 Ln”按钮。
- 页内目录（运行时 h2/h3、细轨 + 悬停文字大纲 + 固定 + scroll-spy）、代码块语言条、
  目录统一列表、源码页“预览”回链。
- 渲染页输出 `data-sourcepos`，由 `linetarget` 岛把搜索 `#L<n>` 映射到包含该行的
  最小渲染块；块级近似，无 JS 时仍打开文档但不滚动。
- 文件大小统一按 1024 进制显示 KB/MB/GB，1 位小数去尾零；0 字节为 `0 KB`，
  1–1023 字节为 `<1 KB`。
- 主题三态改为当前页面内存状态：localStorage 写入失败仍能继续切换；每次点击在
  按钮旁短暂显示“跟随系统/浅色/深色”。
- 前端文案去技术化：搜索结果统一用“条结果”，文件标题整行可点击；目录统计用
  “个项目”，错误页、Trust 拦截面、源码大文件提示与代码块提示改为用户语言。
- 文档按用途重组为 `architecture/`、`guides/`、`reference/`、`testing/`、
  `research/`、`archive/`；新增功能矩阵 `docs/reference/features.md`、浏览器验收
  报告与 agent 自主测试指南；`tests/run-all.sh` 和文档链接检查加入本地验收。
- 大文本源码页全文分块：>256 KB 仍输出全文，按 500 行分块并用
  `content-visibility: auto` 跳过离屏绘制；1 MB 文本从约 42 s 降到约 0.08 s，
  10 MB 约 0.11 s（本机基准）。行锚点与高亮由 JS 按可见块懒加载。
- 关闭 highlight.js 自动语言探测，仅对明确 `language-*` 的代码块高亮；
  大源码的每个可见块单独高亮，单块上限 256 KB。
- 资产 URL 内容哈希（`?v=<FNV-1a>`）+ `immutable` 缓存。

### 变更（与 1.x 不兼容）

- 裸 HTML **原样透传**，安全性由 Trust + CSP 承担（旧版一律转义）。
- 不生成标题 `id`；任务列表按字面量显示；`~~x~~` 输出 `<s>` 而非 `<del>`。
- linkify / reference definition / front matter / URL 与 alt 采用 comrak 行为：
  `www.` 与裸邮箱会链接化，全角句号进 URL，front matter 被消费。
- 相对路径解码两次：文件名里字面含 `%xx` 的文件不能通过相对 Markdown 目标到达。
- 非 Markdown 文本不再直接以 `text/plain` 发送，而是源码查看页。
- 删除 Python 实现、`dist/`、`tools/minify.py` 与 Python 测试。
- 不再支持缩进式代码块之外的旧自定义解析边角（转义装饰、标题锚点等）。

### 测试

- `cargo test`：50 项单元/集成 + 134 项渲染兼容 + 27 条 golden。
- `bash tests/selftest-rust.sh`：151 项黑盒 HTTP 断言；`trust-tty.sh` 9 项；
  `browser-probe.mjs` 163 项；性能预算 4 项；artifact 冒烟 7 项。
- CI：macOS / Linux / Windows 测试矩阵、4 目标构建、`cargo audit`。

### 已知后果

见 [README 已知限制](README.md#已知限制) 与
[ADR 0007](docs/architecture/adr/0007-hard-edge-cases-use-comrak.md)。
