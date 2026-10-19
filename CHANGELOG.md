# Changelog

## 2.0.0（未发布）

Rust 重写。旧 Python 单文件实现已删除，历史台账见
[`docs/legacy/SELFTEST-python.md`](docs/legacy/SELFTEST-python.md)。

### 新增

- 单文件原生二进制（macOS arm64 / Linux x86_64+arm64 musl / Windows x86_64 static CRT）；
  内嵌 VS Code `markdown.css`、`highlight.css`、highlight.js 11.11.1 与客户端脚本。
- Markdown 语义与代码高亮对齐 VS Code 1.142.0；页面外壳改为文档站风格；
  P0 差分 98.07%（1015/1035），25 条 accepted deviations 有记录。
- Trust 模型：目录级信任、未信任 `.md` 的一次性令牌拦截面、用户配置持久化。
- 4 档 CSP：nonce-only `script-src`、`frame/base/object 'none'`、
  `form-action 'self'`（仅搜索表单）、nosniff。
- 非 Markdown 文本统一源码查看页（行号、行锚点、客户端高亮）。
- `data:image/*;…` 在链接与图片位置放行（VS Code 1.142 行为）；拒绝 `vscode:` 链接。
- 文档站外壳：顶部栏、可折叠 sticky 侧栏、面包屑、主题三态、移动端抽屉；
  Markdown 页 ≥1360px 为 240/780/220 三列，右侧 TOC 支持 scroll-spy 与独立收起。
- 搜索覆盖 Markdown/文本正文与所有文件名，结果按文件分组；Markdown 正文命中
  可打开文档或源码行。
- 页内目录（运行时 h2/h3）、代码块语言条、目录分组列表、源码页“查看渲染页”回链。
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

- `cargo test`：45 项单元/集成 + 134 项渲染兼容 + 27 条 golden。
- `bash tests/selftest-rust.sh`：110 项黑盒 HTTP 断言；`trust-tty.sh` 9 项；
  `browser-probe.mjs` 58 项；artifact 冒烟 7 项。
- CI：macOS / Linux / Windows 测试矩阵、4 目标构建、`cargo audit`。

### 已知后果

见 [README 已知限制](README.md#已知限制) 与
[ADR 0007](docs/adr/0007-hard-edge-cases-use-comrak.md)。
