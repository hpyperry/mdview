# 大源码高亮空闲调度复测文档

- 关联：Issue [#70](https://github.com/hpyperry/mdview/issues/70) / PR（待建）/ F-101
- 关联测试报告：`docs/testing/reports/test-report-2026-11-07-large-source-highlight.md`
- 夹具：复用 `tests/browser-probe.mjs` 生成的 `big.rs`（12000 行 Rust）与 `wide.txt`；
  本目录为 README-only。
- 启动：

```bash
cargo build --release
./target/release/mdview --root <含 big.rs 的目录> --trust --port 8007 --port-tries 0
```

- 入口：`/big.rs`
- 自动化覆盖：`tests/browser-probe.mjs` 的 `大源码按块着色`、`大源码着色有界`、
  `大源码滚动后继续着色`、`大源码高亮队列清空`。

## 复测步骤

1. 操作：打开 `/big.rs`，看首屏。
   预期：只有视口附近的一个源码块被 highlight.js 着色；行号与滚动条正常。

2. 操作：滚动到文件中段和底部。
   预期：每次空闲只高亮一个进入视口附近的块；滚动不掉帧，已高亮块不重复处理；
   未浏览到的块保持纯文本。

3. 操作：快速滚过整个文件再停下。
   预期：离开视口的排队块会被跳过，不会把整份文件全部高亮；停在当前区域后继续
   补齐当前可见块。

4. 操作：打开无明确语言的 `wide.txt`。
   预期：不做自动语言探测，保持纯文本；分块、行号与滚动正常。

## 已知限制

- 单块超过 256KB 时仍会关闭该块高亮；服务端 syntect 会改变 VS Code 视觉与二进制
  体积，不作为默认方案。
- 首屏首次高亮仍可能产生约 50–100ms 的单个长任务；滚动阶段不再叠加多个块。
- 旧内核没有 `requestIdleCallback` 时回退到 `setTimeout(16)`。

## 清理

- 停止临时服务；临时 `big.rs`/`wide.txt` 可删除。
