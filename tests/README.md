# tests/ —— 自测

Rust 实现的断言分多组：

| 文件 | 作用 | 命令 |
|------|------|------|
| `tests/render_compat.rs` | 渲染器回归（134 项）：内联/块/URL 重写/目标编码/引用式/data URI/裸 URL/放大包裹/属性转义/协议安全/性能 | `cargo test --test render_compat` |
| `tests/golden.rs` + `tests/golden/` | 27 条 curated golden 的逐字节输出（accepted deviation 带 `note`） | `cargo test --test golden` |
| `src/` 的 `#[cfg(test)]` | 模块内单元测试（45 项：render 10 / server 22 / trust 7 / cli 5 / assets 1） | `cargo test --lib` |
| `selftest-rust.sh` | 真二进制的 black-box HTTP 断言（110 项：目录/渲染/源码/下载/搜索/Trust/CSP/安全/文件系统边界） | `bash tests/selftest-rust.sh` |
| `trust-tty.sh` + `trust-tty.exp` | 真实 pty 下的信任询问、持久化、非 TTY 默认（9 项） | `bash tests/trust-tty.sh` |
| `browser-probe.mjs` | headless Chrome 验收（34 项）：高亮/复制/放大/回顶/主题/无 JS 降级/无外部请求 | `node tests/browser-probe.mjs` |
| `smoke-artifact.sh` | 对已构建二进制做目录/渲染/资产/下载/CSP 冒烟（7 项） | `bash tests/smoke-artifact.sh <二进制>` |

`selftest-rust.sh` 会自动 `cargo build --release`，起临时服务、跑完自清理；
可用 `MDVIEW_BIN=` 指向别的二进制，`PORT=` 换一组端口。
`browser-probe.mjs` 需要 Node 22 与 Chrome/Chromium（`CHROME=` 可指定路径）；
`trust-tty.sh` 需要 `expect`，缺失时跳过。

## 一套跑完

```bash
# 在仓库根执行
cargo test
cargo clippy --all-targets -- -D warnings
bash tests/selftest-rust.sh
bash tests/trust-tty.sh
node tests/browser-probe.mjs
bash tests/smoke-artifact.sh target/release/mdview
```

## `render_compat.rs` 覆盖什么

这是旧 `tests_render.py` 渲染类的 Rust 后继（P4-1），期望按
[ADR 0005](../docs/adr/0005-vscode-1.142-as-oracle.md)、
[ADR 0006](../docs/adr/0006-html-trust-and-csp.md)、
[ADR 0007](../docs/adr/0007-hard-edge-cases-use-comrak.md) 更新：

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
由 `assets/mdview.js` + `browser-probe.mjs` 覆盖。

## 其他套件

- **golden**：`tests/golden/cases.jsonl` 的 27 条输入与 `expected/*.html`
  逐字节比较。有意修改渲染器后运行
  `cargo run --example golden -- --update` 并审阅 diff；`note` 字段标记
  accepted deviation。P0 的 markdown-it 差分 oracle 仍在 `tools/spike/`。
- **browser-probe**：真实 headless Chrome 里验证 highlight.js 运行、复制按钮反馈、
  放大遮罩的打开/关闭/焦点归还、修饰键不拦截、明暗主题、目录/源码页回顶、
  无 JS 基线无死按钮且不着色、页面无外部资源请求。
- **trust-tty**：用 `expect` 在真实 pty 里回答 `y`，验证配置落盘、第二次不再询问、
  新 HOME + 非 TTY 默认 untrusted。
- **smoke-artifact**：只依赖 curl 与已构建二进制，用于 CI 里检查发布产物。

## 旧 Python 测试

旧 `tests_render.py`（217 项）与 `tests/selftest.sh`（345 项）已随 Python 实现删除。
它们的验证台账归档在 [`../docs/legacy/SELFTEST-python.md`](../docs/legacy/SELFTEST-python.md)，
行为参考（不是 oracle）仍在 git 历史里；新实现的判据是 ADR 0005/0007。

## 约定

- 新增测试优先放 `tests/` 或对应模块的 `#[cfg(test)]`；不要往仓库根加脚本。
- 断言若与实现冲突，先核对 ADR/规格，再改断言；accepted deviation 必须在
  测试名或注释里写明，不能沉默混入通过率。
- 改渲染器后至少跑 `cargo test`；改路由/安全后加跑 `selftest-rust.sh`。
