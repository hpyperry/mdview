# 大源码高亮空闲调度复测文档

- 关联：Issue [#70](https://github.com/hpyperry/mdview/issues/70) / PR [#71](https://github.com/hpyperry/mdview/pull/71) / F-101
- 关联测试报告：`docs/testing/reports/test-report-2026-11-07-large-source-highlight.md`
- 夹具根：`tests/fixtures/large-source-highlight/root/`（可直接作为 `--root`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/large-source-highlight/root --trust --port 8007 --port-tries 0
```

- 入口：`/big.rs`
- 自动化覆盖：`tests/browser-probe.mjs` 的 `大源码按块着色`、`大源码着色有界`、
  `大源码滚动后继续着色`、`大源码高亮队列清空`；本夹具用于人工复测与长任务对比。

## 夹具

| 文件 | 大小 / 行数 | 用途 |
|---|---|---|
| `/big.rs` | 约 366 KB / 6000 行 | 有明确语言、需要分块；验证首屏单块高亮与滚动逐块补齐 |
| `/oversize.rs` | 约 307 KB / 550 行 | 第一个 500 行块超过 256 KB 高亮上限，验证跳过高亮不阻塞 |
| `/wide.txt` | 约 276 KB / 4000 行 | 无明确语言；验证不做自动语言探测，保持纯文本 |

## 复测步骤

1. 操作：打开 `/big.rs`，看首屏。
   预期：只有视口附近的一个源码块被 highlight.js 着色；行号、滚动条正常。

2. 操作：滚动到文件中段和底部。
   预期：每次空闲只高亮一个进入视口附近的块；滚动不掉帧，已高亮块不重复处理；
   未浏览到的块保持纯文本。

3. 操作：快速滚过整个文件再停下。
   预期：离开视口的排队块会被跳过，不会把整份文件全部高亮；停在当前区域后继续
   补齐当前可见块。

4. 操作：打开 `/oversize.rs`。
   预期：第一个块超过 256 KB，关闭该块高亮但不阻塞；页面仍可滚动，行号正常。

5. 操作：打开 `/wide.txt`。
   预期：不做自动语言探测，保持纯文本；分块、行号与滚动正常。

6. 操作：用 CDP `PerformanceObserver` 记录 `longtask`，依次采样首屏、中段、底部。
   参考命令与数据见测试报告；预期滚动阶段不再出现 50ms+ 长任务。

## 已知限制

- 单块超过 256KB 时仍会关闭该块高亮；服务端 syntect 会改变 VS Code 视觉与二进制
  体积，不作为默认方案。
- 首屏首次高亮仍可能产生约 50–100ms 的单个长任务；滚动阶段不再叠加多个块。
- 旧内核没有 `requestIdleCallback` 时回退到 `setTimeout(16)`。

## 清理

- 停止临时服务，释放端口。
