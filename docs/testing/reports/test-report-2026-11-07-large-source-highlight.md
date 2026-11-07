# 大源码高亮空闲调度测试报告（2026-11-07）

- 关联：Issue [#70](https://github.com/hpyperry/mdview/issues/70) / PR（待建）/ F-101
- 夹具：`tests/fixtures/large-source-highlight/README.md`（README-only，复用浏览器探针的 `big.rs`）
- 类型：test（后端/性能）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `perf/large-source-highlight`（PR 待建） |
| 平台 | macOS arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `/tmp/bigroot`（`big.rs` 578 KB / `wide.rs` 963 KB / `huge.rs` 9.9 MB） |
| 启动 | `target/release/mdview --root /tmp/bigroot --trust --port 8290 --port-tries 0` |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 / 集成 | `cargo test` | 96 + 134 + 27 passed |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=292 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=338 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/smoke-artifact.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 滚动长任务对比

用 CDP `PerformanceObserver` 记录 ≥50ms 的 `longtask`，在首屏、滚到中段、滚到底部
分别采样；数值为毫秒。修改前是 synchronized `highlightElement` 循环，修改后每轮
`requestIdleCallback` 只处理一个可见块。

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

结论：首屏单块高亮仍有约 50–100ms 的一次性长任务（页面渲染 + 首个可见块），但
**滚动阶段不再出现 50ms+ 长任务**；不再把多个可见块叠在同一个任务里。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 |
|---|---|---|---|---|
| F-101 | 首屏单块 | 打开 `/big.rs` | 只高亮视口附近一个块；行号、滚动正常 | 通过 |
| F-101 | 滚动补齐 | 滚到中段/底部 | 空闲时逐块高亮；不重复处理已高亮块 | 通过 |
| F-101 | 快速滚过 | 快速滚到文件末尾 | 离开视口的排队块被跳过，不整文件高亮 | 通过 |
| F-101 | 无语言 | 打开 `wide.txt` | 不做自动探测，保持纯文本 | 通过 |
| F-101 | 大于 256KB 块 | 超长行/超大块 | 该块关闭高亮，不阻塞 | 通过 |

## 发现

- 现有优化（500 行分块、`content-visibility`、可见块懒高亮）已经存在；缺口是
  多个可见块在同一任务里同步调用 highlight.js。
- 改为 `requestIdleCallback` 单块队列 + `dataset.highlightQueued` 去重后，滚动阶段
  长任务消失；快速滚过时用 `nearViewport` 跳过不再可见的排队块。
- 没有引入 Web Worker 或服务端高亮：Worker 需要额外 CSP `worker-src` 与独立
  bundle；服务端 syntect 会改变 VS Code 视觉并增加二进制/CPU，见 ADR 0005/0011。

## 覆盖缺口

- 仅 Chromium 156；Firefox/Safari 未测。
- 首屏首个块仍有单次 50–100ms 长任务，后续可评估 Worker。
- 9.9 MB 用例没有显式语言时不做自动探测，本报告不覆盖自动探测优化。

## 结论

- 通过。大源码滚动高亮改为单块空闲调度，滚动阶段无 50ms+ 长任务；现有懒分块、
  行锚点与无 JS 全文行为不变。
