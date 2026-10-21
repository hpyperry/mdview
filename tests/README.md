# tests/ —— 自测

Rust 实现的断言分多组：

| 文件 | 作用 | 命令 |
|------|------|------|
| `tests/render_compat.rs` | 渲染器回归（134 项）：内联/块/URL 重写/目标编码/引用式/data URI/裸 URL/放大包裹/属性转义/协议安全/性能 | `cargo test --test render_compat` |
| `tests/golden.rs` + `tests/golden/` | 27 条 curated golden 的逐字节输出（accepted deviation 带 `note`） | `cargo test --test golden` |
| `src/` 的 `#[cfg(test)]` | 模块内单元测试（67 项：render 11 / server 38 / trust 7 / cli 5 / assets 1 / archive 5） | `cargo test --lib` |
| `web/src/` | TypeScript 类型检查（岛运行时、Preact 组件、源码岛） | `npm --prefix web run typecheck` |
| `selftest-rust.sh` | 真二进制的 black-box HTTP 断言（198 项：目录/渲染/源码/大源码全文分块/导航 JSON/岛清单/下载/搜索/Trust/CSP/HTML 信任原文与未信任沙箱/子资源/压缩包虚拟目录与包内条目/SVG sandbox/安全/文件系统边界） | `bash tests/selftest-rust.sh` |
| `trust-tty.sh` + `trust-tty.exp` | 真实 pty 下的信任询问、持久化、非 TTY 默认（9 项） | `bash tests/trust-tty.sh` |
| `browser-probe.mjs` | headless Chrome 验收（203 项）：全宽内容面/全宽页头/导航空闲预取与树操作/目录只展开/文件导航/TOC 悬停文字大纲与 scroll-spy/搜索弹层与整行结果/渲染块行定位/源码页头/HTML 信任原文与未信任沙箱/源码切换/目录列对齐/压缩包虚拟目录与包内预览/SVG 直开脚本阻断/主题快速切换与状态反馈/岛水合/语言条/复制/放大/大源码分块/无 JS 全文 | `node tests/browser-probe.mjs` |
| `perf-source.mjs` | 源码页性能预算：100 KB / 1 MB / 10 MB / 1 MB Rust（真实 Chrome，含末行完整性检查） | `node tests/perf-source.mjs` |
| `smoke-artifact.sh` | 对已构建二进制做目录/渲染/资产/下载/CSP 冒烟（7 项） | `bash tests/smoke-artifact.sh <二进制>` |
| `check-doc-links.mjs` | 检查 Markdown 内部链接（跳过代码块、归档与站内根 URL） | `node tests/check-doc-links.mjs` |
| `run-all.sh` | 依次跑类型检查、fmt/clippy、Rust 测试、链接检查、黑盒、浏览器、性能与冒烟 | `bash tests/run-all.sh` |
| `fixtures/html-preview/` | 手动 HTML 夹具：trusted 原文、untrusted 沙箱、相对 CSS、SVG、链接与搜索探针 | 见 [fixtures/html-preview/README.md](fixtures/html-preview/README.md) |
| `fixtures/archives/` | 手动压缩包夹具：zip/tar.gz/7z、包内 Markdown/HTML/CSS、嵌套 zip | 见 [fixtures/archives/README.md](fixtures/archives/README.md) |

`selftest-rust.sh` 会自动 `cargo build --release`，起临时服务、跑完自清理；
可用 `MDVIEW_BIN=` 指向别的二进制，`PORT=` 换一组端口。
`browser-probe.mjs` 需要 Node 22 与 Chrome/Chromium（`CHROME=` 可指定路径）；
`trust-tty.sh` 需要 `expect`，缺失时跳过。

## 一套跑完

```bash
# 在仓库根执行
bash tests/run-all.sh
```

它按顺序跑类型检查、fmt/clippy、Rust 测试、文档链接检查、黑盒 HTTP、TTY Trust、
浏览器探针、性能预算与 artifact 冒烟。也可以手跑：

```bash
npm --prefix web ci
npm --prefix web run typecheck
node tests/check-doc-links.mjs
cargo test
cargo clippy --all-targets -- -D warnings
bash tests/selftest-rust.sh
bash tests/trust-tty.sh
node tests/browser-probe.mjs
node tests/perf-source.mjs
bash tests/smoke-artifact.sh target/release/mdview
```

Agent 自主测试的 fixture、browser-use 流程、截图证据和报告格式见
[`docs/testing/agent-guide.md`](../docs/testing/agent-guide.md)。

## `render_compat.rs` 覆盖什么

这是旧 `tests_render.py` 渲染类的 Rust 后继（P4-1），期望按
[ADR 0005](../docs/architecture/adr/0005-vscode-1.142-as-oracle.md)、
[ADR 0006](../docs/architecture/adr/0006-html-trust-and-csp.md)、
[ADR 0007](../docs/architecture/adr/0007-hard-edge-cases-use-comrak.md) 更新：

- **内联/块**：三连强调、`*` 词内强调、`_` 词内规则、相邻/未配对定界符、
  行内码与转义（无占位符泄漏）、代码块 HTML 转义、裸 HTML 透传、
  alt 纯文本、实体、Setext、列表松紧、任务列表字面量、标题无 id、
  表格 `style="text-align:…"`、front matter 消费。
- **URL 重写**：根相对输出、`../` 夹紧、CJK 编码、`#` 锚点编码、
  `%20`/`%2520` 双重解码、`%23`/`%3F` 先切后解、查询串逐字节保留、
  链接与图片同一规则、`<>` 目标、裸空格退化、混淆 scheme 只成为相对路径。
- **引用式与 data URI**：全文/折叠/简写引用、title、被拒协议移除（comrak）、
  尖括号引用定义的字面回退（accepted）、任意 `data:image/*;…` 在链接与图片
  位置放行、非图片/无分号拒绝、payload 引号转义、缩放链接与 `src` 逐字节相同。
- **裸 URL（comrak 行为）**：`https`/`http`、尾随半角标点、括号配平、查询串
  只转义一次；`www.`、裸邮箱、全角句号吞进 URL、`&copy;` 截断 URL 是
  ADR 0007 的 accepted deviations，测试里显式标注。
- **安全**：`javascript:`/`vbscript:`/`file:`/非法 `data:`/`vscode:` 拒绝，
  安全协议保留，生成的 `<a>`/`<img>` 属性白名单，alt/title 引号不能逃逸，
  autolink 注入被转义，NUL 不产生可执行 scheme。
- **性能**：`[x](` 串、未配对 `[`、超长定界符、链接+裸 URL 混合、1 MB 输入
  均有宽松上界，拦住平方级退化。

纯 JS/CSS 的旧断言（复制按钮、遮罩动画、主题变量）属于被重写的客户端资产，
由 `web/src/` + `browser-probe.mjs` 覆盖。

## 其他套件

- **golden**：`tests/golden/cases.jsonl` 的 27 条输入与 `expected/*.html`
  逐字节比较。有意修改渲染器后运行
  `cargo run --example golden -- --update` 并审阅 diff；`note` 字段标记
  accepted deviation。P0 的 markdown-it 差分 oracle 仍在 `tools/spike/`。
- **browser-probe**：真实 headless Chrome 里验证岛屿按页面水合、全宽内容面与页头、
  导航空闲预取、TOC 悬停文字大纲/固定/scroll-spy、搜索弹层与整行结果、
  渲染块行定位、源码页头、主题快速切换/状态反馈/写入失败降级、highlight.js 运行、
  复制按钮反馈、放大遮罩的打开/关闭/焦点归还、修饰键不拦截、明暗主题、目录/源码页回顶、
  大源码全文分块/末行可达/行锚点/懒高亮/长行横向滚动、无 JS 基线无死按钮、
  大源码仍可读全文且页面无外部资源请求。
- **trust-tty**：用 `expect` 在真实 pty 里回答 `y`，验证配置落盘、第二次不再询问、
  新 HOME + 非 TTY 默认 untrusted。
- **smoke-artifact**：只依赖 curl 与已构建二进制，用于 CI 里检查发布产物。

## 旧 Python 测试

旧 `tests_render.py`（217 项）与 `tests/selftest.sh`（345 项）已随 Python 实现删除。
它们的验证台账归档在 [`../docs/archive/selftest-python.md`](../docs/archive/selftest-python.md)，
行为参考（不是 oracle）仍在 git 历史里；新实现的判据是 ADR 0005/0007。

## 约定

- 新增测试优先放 `tests/` 或对应模块的 `#[cfg(test)]`；不要往仓库根加脚本。
- 断言若与实现冲突，先核对 ADR/规格，再改断言；accepted deviation 必须在
  测试名或注释里写明，不能沉默混入通过率。
- 改渲染器后至少跑 `cargo test`；改路由/安全后加跑 `selftest-rust.sh`。
