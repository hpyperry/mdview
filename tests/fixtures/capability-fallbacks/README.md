# capability-fallbacks 复测夹具

对应 2026-11-11 的三处改动：剪贴板失败回退、`<dialog>` 不可用时的图片放大兜底、
默认监听地址改为 `127.0.0.1`。README-only，复用现有文档根。

## 启动

```bash
cargo build --release
./target/release/mdview --root docs --trust --host 127.0.0.1 --port 8306 --port-tries 0
```

## 复测入口

| 场景 | 操作 | 预期 |
|---|---|---|
| 默认监听 | `./target/release/mdview --help` / 直接启动 | 默认地址是 `127.0.0.1:8000`，局域网不可访问 |
| 复制的回退 | DevTools 执行 `Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error())}})`，再点代码块“复制” | 走 `execCommand('copy')`，按钮显示“已复制” |
| 复制失败提示 | 再执行 `document.execCommand = () => false`，点主岛工具栏“复制” | 底部出现“复制失败：请允许剪贴板权限，或使用下载”的提示 |
| 图片放大兜底 | `document.querySelector('dialog.zoomdlg').showModal = undefined`，再点正文图片 | 不再拦截点击，图片按普通链接直接打开 |
| 正常放大 | 不修改 `showModal`，点图片 | 仍打开遮罩，Esc/关闭按钮/点遮罩关闭 |

自动化覆盖：`tests/browser-probe.mjs` 的 `== preview page ==` 段（复制回退、失败提示、
`showModal` 兜底）与 `src/cli.rs` 的默认值单测。

关联测试报告：
[`docs/testing/reports/browser-report-2026-11-11-capability-fallbacks.md`](../../../docs/testing/reports/browser-report-2026-11-11-capability-fallbacks.md)。

截图证据：
[`docs/testing/evidence/2026-11-11/copy-failure-toast.png`](../../../docs/testing/evidence/2026-11-11/copy-failure-toast.png)。
