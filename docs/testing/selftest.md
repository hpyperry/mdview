# SELFTEST —— Rust 实现验证记录

本文件只记录**当前 Rust 实现**跑出来的结果。旧 Python 实现的 217 + 345 项台账
已归档到 [`../archive/selftest-python.md`](../archive/selftest-python.md)。最近一次
真实浏览器验收见 [`browser-report-2026-10-20.md`](browser-report-2026-10-20.md)；
自主测试流程见 [`agent-guide.md`](agent-guide.md)。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-20 |
| 分支 | `refactor/new-md-view-server` |
| 平台 | macOS 27.0.0 arm64 |
| Rust | 1.96（edition 2024，`rust-version = 1.89`） |
| 产物 | `target/release/mdview`，约 **3.4 MB**（LTO + strip，内嵌 highlight.js 与岛屿前端） |

## 自动化结果

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元/集成 | `cargo test --lib` | **67 passed** |
| Golden | `cargo test --test golden` | **27 cases passed** |
| 渲染兼容 | `cargo test --test render_compat` | **134 passed** |
| 静态检查 | `cargo clippy --all-targets -- -D warnings` | **通过** |
| 格式 | `cargo fmt --all --check` | **通过** |
| Web 类型 | `npm --prefix web run typecheck` | **通过** |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | **PASS=198 FAIL=0** |
| 浏览器验收 | `node tests/browser-probe.mjs` | **PASS=203 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | **4 项预算通过** |
| TTY 信任 | `bash tests/trust-tty.sh` | **PASS=9 FAIL=0** |
| artifact 冒烟 | `bash tests/smoke-artifact.sh target/release/mdview` | **PASS=7 FAIL=0** |
| 依赖漏洞 | `cargo audit` | **195 deps，无漏洞** |
| 许可证/来源 | `cargo deny check advisories licenses bans sources` | **全部 ok** |

`cargo test` 总耗时约 1.5 秒（debug）；黑盒套件约 15 秒（含 release 构建）。

## 黑盒覆盖

- 目录索引：无分组的统一列表（目录在前）、大小、下载按钮只给文件、面包屑、空目录、301 编码；
- Markdown：标题/粗体/删除线/任务列表字面量/裸 HTML/表格 `style`/标题无 id；
- 源码页：文件名为标题、类型/大小/行数/修改时间标签、行锚点、第 5 行内容、`预览`、下载入口；大于 256 KB 的文件
  全文输出为 24 个分块、服务端保留末行、无 `?text=1` 文本通道；
- 岛屿清单：文档页 `theme nav search totop toc linetarget code zoom`，源码页
  `theme nav search totop source`，搜索页与 `--no-search` 各自收敛；
- 导航 JSON：全站树、目录优先、所有文件、隐藏目录过滤、safe 模式过滤；
- 下载：Content-Disposition、原始字节、Markdown 类型；
- 搜索：正文/文件名/大小写/中文/跳过隐藏目录与 `node_modules`；表单真实提交、
  按文件分组、每条结果整行可点击；Markdown 内容行到渲染页 `#L<n>`，文本内容行
  到源码行，文件标题/文件条目到文件开头；
- 文案：目录统计用“个项目”，搜索页用“条结果”且不出现“命中/实时扫描”，
  404/Trust 页面使用用户语言；
- MIME 与嗅探：JSON/TS/Makefile/Dockerfile/.gitignore/无扩展名文本与二进制；
- URL 现场往返：空格目录、中文文件名、`%23`、尖括号目标；
- 安全：路径穿越、FIFO 404、symlink 逃逸 403、根内 symlink 200、`--safe`；
- Trust：拦截面、一次性令牌、复用拒绝、raw/download 绕过；
- CSP：nonce、`form-action 'self'`、`base-uri`、nosniff；
- 参数：`--no-search`、`--max-preview`（超限下载 + 搜索跳过）、端口占用回退。

## 渲染一致性

P0 差分报告：1035 条计分语料 **1015 条精确匹配（98.07%）**，0 条未解释差异。
25 条 accepted deviations（23 comrak + 2 vscode）已由 `tests/render_compat.rs`
的正反断言固定，分类见 [`../research/comrak-vs-markdown-it.md`](../research/comrak-vs-markdown-it.md)。

后续复核修正了一条记录：尖括号引用定义 `[r]: <a b.md>` 只在**文件末尾没有换行**
时 comrak 解析失败；有结尾换行的正常文件会解析，markdown-it 也能解析。
对应断言已拆成“行尾换行可解析”与“EOF quirk”两条。

## 浏览器验证

`tests/browser-probe.mjs` 在真实 headless Chrome 里跑 **203 项**断言：

- 岛屿：文档页按需水合 toc/linetarget/code/zoom，源码页只挂 source；
- HTML 文件：trusted 根原文顶层、脚本/localStorage/同源 fetch 正常；untrusted 根沙箱 iframe 内脚本运行/相对 CSS 生效、localStorage 与同源 fetch 被阻断；源码页切换、SVG 直开脚本不执行、目录大小/时间列对齐；
- 压缩包：包根页、包内 Markdown/HTML/源码、相对图片、嵌套 zip 不递归、整包/条目下载；压缩包虚拟目录/包内 Markdown/HTML/源码/下载；
- 文档站外壳：全宽内容面、横跨内容面的页头、默认收起的全站导航浮岛、完整面包屑、
  代码语言条、移动端抽屉与遮罩；
- 布局：≥1360 的正文 + 24px TOC 细轨、顶栏/TOC sticky、TOC 悬停文字大纲/固定/scroll-spy；
  1200 单列并回到内联目录；导航浮层不挤压正文；搜索表单在页头右侧。
- 分块源码页：全文 31 块、末行可达、`#L` 深链与目标行高亮、无自动语言探测、
  可见块懒高亮、长行横向滚动；
- 性能预算：100 KB/1 MB/10 MB/1 MB Rust 源码页。
- 导航空闲预取/全站树/目录只展开/文件导航/展开记忆/默认收起/移动抽屉；
- 搜索图标弹层、统一键帽提示、真实提交、搜索页独立表单、结果分组与查询词高亮；
  搜索结果整行点击、Markdown 渲染块行定位与滚动/高亮；
- 源码页文件名标题、类型/大小/行数/时间标签、预览/下载入口与 H1 无下划线；
- highlight.js 实际着色、复制按钮与剪贴板反馈；
- 图片放大：`href === src`、`showModal()`、焦点落在 dialog、关闭后焦点归还、
  修饰键不拦截；
- 主题三态切换、快速连点循环、状态提示反馈，以及 localStorage 写入失败时仍能前进；
- 目录页/源码页的回到顶部按钮与平滑滚动；
- 无 JS 基线：无 `<dialog>`/复制/语言条/回顶/目录死按钮，隐藏主题开关，
  正文可读，服务端不输出高亮 span；大源码仍读得到末行与总行数；
- 页面请求全部是本机资源，无外部请求。

另用 headless Chrome 截图核对过文档站外壳、780/16/1.7 阅读排版、vs/vs2015 代码配色、
源码页行号、深色/浅色与移动端布局。

## CI（GitHub Actions）

- 最近一次远程完整绿色：`CI · 39450506481`（2026-10-20，`b3a133a`），8/8 job
  成功；macOS/Ubuntu/Windows 测试、Node 类型检查、4 目标构建全绿。
- 本地 `run-all.sh` 当前为 198/203；远程 CI 最近一次绿色仍是 `b3a133a` 的 151/163。
- Release 由 tag `v2.0.0` 触发 `release.yml`；发布结果以该 GitHub Release 为准。
- 岛屿架构首跑 `39421064321` 暴露两个 CI 问题：Linux Chrome 因新增的
  headless 启动参数没有在 15s 内暴露 DevTools；musl 的 cross 容器默认不传递
  `MDVIEW_WEB_PREBUILT`，导致 build.rs 在容器内找 npm。修复为移除多余启动
  参数、DevTools 超时 30s，并加 `Cross.toml` 透传预构建路径。
- 更早的 `39285530389` 曾受 GitHub Actions `degraded_performance` 影响，
  8 个 job 长时间 queued；那是平台事件，不是代码失败。
- 测试矩阵覆盖：`cargo test`、黑盒 198、TTY 9、浏览器 203、源码页性能 4；
  Windows 跳过 pty/浏览器/性能，其余全跑。
- artifact 冒烟：macOS arm64、Linux x86_64 musl、Windows x86_64 通过；
  Linux arm64 musl 只构建（x86 runner 无法执行 arm64）。
- 4 个 artifact 大小：macOS 2.8 MB、Windows 3.3 MB、Linux x64 3.3 MB、
  Linux arm64 3.0 MB。
- tag `v2.0.0` 首次触发 `release.yml`（SHA256SUMS + GitHub Release）；
  产物列表与校验和以该 Release 页面为准。

## 尚未验证 / 待办

- v2.0.0 Release 的 artifact 下载与 SHA256SUMS 需在发布后核对一次。
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
