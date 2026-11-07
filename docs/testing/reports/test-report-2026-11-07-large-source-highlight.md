# 大源码高亮空闲调度测试报告（2026-11-07）

- 关联：Issue [#70](https://github.com/hpyperry/mdview/issues/70) / PR [#71](https://github.com/hpyperry/mdview/pull/71) / F-101
- 夹具：`tests/fixtures/large-source-highlight/README.md`（root：`tests/fixtures/large-source-highlight/root/`）
- 类型：test（后端/性能）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `main` @ `bf6a239`（PR #71 合并后） |
| 平台 | macOS arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `tests/fixtures/large-source-highlight/root` |
| 启动 | `target/release/mdview --root tests/fixtures/large-source-highlight/root --trust --port 8007 --port-tries 0` |

## 夹具

| 文件 | 大小 / 行数 | 用途 |
|---|---|---|
| `/big.rs` | 374,679 B / 6000 行 | 有明确语言、13 个源码块；验证首屏单块高亮与滚动逐块补齐 |
| `/oversize.rs` | 314,050 B / 550 行 | 第一个 500 行块超过 256 KB 高亮上限，验证跳过高亮不阻塞 |
| `/wide.txt` | 282,893 B / 4000 行 | 无明确语言；验证不做自动语言探测，9 个源码块保持纯文本 |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 / 集成 | `cargo test` | 96 + 134 + 27 passed |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=292 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=338 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/smoke-artifact.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 |
|---|---|---|---|---|
| F-101 | 首屏单块 | 打开 `/big.rs` | 13 个块中只有视口附近 1 个块着色；行号、滚动正常 | 通过 |
| F-101 | 滚动补齐 | 滚到中段/底部 | 空闲时逐块高亮；中段累计 3 个块、不重复处理已高亮块 | 通过 |
| F-101 | 快速滚过 | 快速滚到文件末尾 | `nearViewport` 跳过已离开视口的排队块，不整文件高亮 | 通过 |
| F-101 | 超限块 | 打开 `/oversize.rs` | 第一个块 >256KB 关闭高亮，不阻塞；页面和滚动正常 | 通过 |
| F-101 | 无语言 | 打开 `/wide.txt` | 不做自动探测，9 个块保持纯文本 | 通过 |
| F-101 | 队列清空 | 滚动后等待 | `.source-chunk[data-highlight-queued]` 最终为 0 | 通过 |

浏览器探针新增/更新断言：

- `大源码按块着色`：`/big.rs` 至少一个块 `code.hljs`；
- `大源码着色有界`：着色块 <10；
- `大源码滚动后继续着色`：滚到底部后着色块数量增加；
- `大源码高亮队列清空`：等待空闲队列排空。

## 滚动长任务对比

用 CDP `PerformanceObserver` 记录 ≥50ms 的 `longtask`，在首屏、滚到中段、滚到底部
分别采样；数值为毫秒。修改前是同步 `highlightElement` 循环，修改后每轮
`requestIdleCallback` 只处理一个可见块。

开发基准（临时生成文件）：

| 文件 | 阶段 | 修改前 | 修改后 |
|---|---|---|---|
| `big.rs`（578 KB） | 首屏 | 76 | 83 |
| | 中段 | 53 | — |
| | 底部 | 53 | — |
| `wide.rs`（963 KB） | 首屏 | 88 | 95 |
| | 中段 | 54 | — |
| | 底部 | 54 | — |
| `huge.rs`（9.9 MB） | 首屏 | — | — |
| | 中段 | 69 | — |
| | 底部 | 69 | — |

夹具复测（提交后的 `tests/fixtures/large-source-highlight/root`）：

| 文件 | 块数 / 着色块 | 首屏长任务 | 中段长任务 | 底部长任务 |
|---|---|---|---|---|
| `big.rs` | 13 / 1→3 | 无 | 无 | 无 |
| `oversize.rs` | 2 / 0 | 无 | 无 | 无 |
| `wide.txt` | 9 / 0 | 无 | 无 | 无 |

结论：首屏单块高亮仍可能有约 50–100ms 的一次性长任务（页面渲染 + 首个可见块），但
**滚动阶段不再出现 50ms+ 长任务**；不再把多个可见块叠在同一个任务里。

## 发现

- 现有优化（500 行分块、`content-visibility`、可见块懒高亮）已经存在；缺口是
  多个可见块在同一任务里同步调用 highlight.js。
- 改为 `requestIdleCallback` 单块队列 + `dataset.highlightQueued` 去重后，滚动阶段
  长任务消失；快速滚过时用 `nearViewport` 跳过不再可见的排队块。
- `/oversize.rs` 的首块超过 256KB，按设计关闭高亮；页面仍可滚动，不阻塞。
- 没有引入 Web Worker 或服务端高亮：Worker 需要额外 CSP `worker-src` 与独立
  bundle；服务端 syntect 会改变 VS Code 视觉并增加二进制/CPU，见 ADR 0005/0011。

## 覆盖缺口

- 仅 Chromium 156；Firefox/Safari 未测。
- 首屏首个块仍有单次 50–100ms 长任务，后续可评估 Worker。
- 9.9 MB 用例只在开发基准中测量，未纳入仓库夹具（避免提交超大文件）。

## 结论

- 通过。大源码滚动高亮改为单块空闲调度，滚动阶段无 50ms+ 长任务；现有懒分块、
  行锚点与无 JS 全文行为不变。
