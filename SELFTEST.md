# SELFTEST —— Rust 实现验证记录

本文件只记录**当前 Rust 实现**跑出来的结果。旧 Python 实现的 217 + 345 项台账
已归档到 [`docs/legacy/SELFTEST-python.md`](docs/legacy/SELFTEST-python.md)。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-19 |
| 分支 | `refactor/new-md-view-server` |
| 平台 | macOS 27.0.0 arm64 |
| Rust | 1.96（edition 2024，`rust-version = 1.89`） |
| 产物 | `target/release/mdview`，约 **3.3 MB**（LTO + strip，内嵌 highlight.js） |

## 自动化结果

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元/集成 | `cargo test --lib` | **45 passed** |
| Golden | `cargo test --test golden` | **27 cases passed** |
| 渲染兼容 | `cargo test --test render_compat` | **134 passed** |
| 静态检查 | `cargo clippy --all-targets -- -D warnings` | **通过** |
| 格式 | `cargo fmt --all --check` | **通过** |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | **PASS=110 FAIL=0** |
| 浏览器验收 | `node tests/browser-probe.mjs` | **PASS=34 FAIL=0** |
| TTY 信任 | `bash tests/trust-tty.sh` | **PASS=9 FAIL=0** |
| artifact 冒烟 | `bash tests/smoke-artifact.sh target/release/mdview` | **PASS=7 FAIL=0** |
| 依赖漏洞 | `cargo audit` | **134 deps，无漏洞** |
| 许可证/来源 | `cargo deny check advisories licenses bans sources` | **全部 ok** |

`cargo test` 总耗时约 1.5 秒（debug）；黑盒套件约 15 秒（含 release 构建）。

## 黑盒覆盖

- 目录索引：文件/目录列表、大小、下载按钮只给文件、上级目录、空目录、301 编码；
- Markdown：标题/粗体/删除线/任务列表字面量/裸 HTML/表格 `style`/标题无 id；
- 源码页：行锚点、第 5 行内容、`看渲染结果`、下载入口；
- 下载：Content-Disposition、原始字节、Markdown 类型；
- 搜索：正文/文件名/大小写/中文/跳过隐藏目录与 `node_modules`；
- MIME 与嗅探：JSON/TS/Makefile/Dockerfile/.gitignore/无扩展名文本与二进制；
- URL 现场往返：空格目录、中文文件名、`%23`、尖括号目标；
- 安全：路径穿越、FIFO 404、symlink 逃逸 403、根内 symlink 200、`--safe`；
- Trust：拦截面、一次性令牌、复用拒绝、raw/download 绕过；
- CSP：nonce、`base-uri`、nosniff；
- 参数：`--no-search`、`--max-preview`（超限下载 + 搜索跳过）、端口占用回退。

## 渲染一致性

P0 差分报告：1035 条计分语料 **1015 条精确匹配（98.07%）**，0 条未解释差异。
25 条 accepted deviations（23 comrak + 2 vscode）已由 `tests/render_compat.rs`
的正反断言固定，分类见 [`docs/spikes/comrak-vs-markdown-it.md`](docs/spikes/comrak-vs-markdown-it.md)。

后续复核修正了一条记录：尖括号引用定义 `[r]: <a b.md>` 只在**文件末尾没有换行**
时 comrak 解析失败；有结尾换行的正常文件会解析，markdown-it 也能解析。
对应断言已拆成“行尾换行可解析”与“EOF quirk”两条。

## 浏览器验证

`tests/browser-probe.mjs` 在真实 headless Chrome 里跑 **34 项**断言：

- highlight.js 实际着色、复制按钮注入与剪贴板反馈；
- 图片放大：`href === src`、`showModal()`、焦点落在 dialog、关闭后焦点归还、
  修饰键不拦截；
- 明/暗主题类切换；
- 目录页/源码页的回到顶部按钮与平滑滚动；
- 无 JS 基线：无 `<dialog>`/复制/回顶死按钮，保留 `data-totop` 标记，正文可读，
  服务端不输出高亮 span；
- 页面请求全部是本机资源，无外部请求。

另用 headless Chrome 截图核对过 VS Code `markdown.css` 排版、vs/vs2015 配色、
源码页行号与深色模式。

## CI（GitHub Actions）

- 运行：`CI · 39274836191`（2026-10-19），**全部 job 绿色**：
  macOS 14 / Ubuntu / Windows 测试矩阵、依赖审计、4 目标构建。
- 测试矩阵覆盖：`cargo test`、黑盒 110、TTY 9、浏览器 34；Windows 跳过
  pty/浏览器，其余全跑。
- artifact 冒烟：macOS arm64、Linux x86_64 musl、Windows x86_64 通过；
  Linux arm64 musl 只构建（x86 runner 无法执行 arm64）。
- 4 个 artifact 大小：macOS 2.85 MB、Windows 3.31 MB、Linux x64 3.34 MB、
  Linux arm64 3.05 MB。
- tag `v*` 触发的 `release.yml`（SHA256SUMS + GitHub Release）尚未实跑。

## 尚未验证 / 待办

- `release.yml` 需要一次 tag 才能验证；当前只验证了 CI 打包。
- 完整 P0 语料的 golden 生成器仍以 `tools/spike/` 为准（当前为 27 条 curated golden）。

## 复现

```bash
cargo test
cargo clippy --all-targets -- -D warnings
cargo fmt --all --check
bash tests/selftest-rust.sh
bash tests/trust-tty.sh
node tests/browser-probe.mjs
bash tests/smoke-artifact.sh target/release/mdview
```

黑盒脚本可用 `MDVIEW_BIN=` 指向已有二进制、`PORT=` 换端口组。
