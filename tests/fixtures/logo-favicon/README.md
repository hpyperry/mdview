# logo-favicon 复测夹具

对应 2026-11-11 的品牌标记与 favicon（ADR 0037）。README-only，复用现有文档根。

## 启动

```bash
cargo build --release
target/release/mdview --root docs --trust --host 127.0.0.1 --port 8306 --port-tries 0
```

## 复测入口

| 场景 | 操作 | 预期 |
|---|---|---|
| 顶栏 logo | 打开 `/manual/README.md` | 最左是 24×24 蓝色 M 标记，点击回到 `/`；导航按钮在它右侧；标题仍居中 |
| 标签页图标 | 看浏览器标签 | 显示蓝色 M；支持 SVG 的浏览器用 `favicon.svg`，否则用 32×32 PNG |
| SVG 接口 | `curl -I '/_assets/favicon.svg?__mdview=asset'` | 200，`image/svg+xml`，`immutable` |
| PNG 接口 | `curl -I '/_assets/favicon.png?__mdview=asset'` | 200，`image/png`，`immutable` |
| 不带标记 | `curl -I '/_assets/favicon.svg'` | 走普通文件路径；根目录没有该文件时 404 |
| 无 JS | 禁用 JS 打开文档 | logo 仍在，导航按钮隐藏 |
| 移动端 | 390×844 | 只保留 24px 标记，标题不与其重叠 |

自动化覆盖：`tests/browser-probe.mjs` 的 `== preview page ==` 与
`== no-JS baseline ==` 段；服务端单测覆盖 favicon 资产路由与 HTML 链接。

关联测试报告：
[`docs/testing/reports/browser-report-2026-11-11-logo-favicon.md`](../../../docs/testing/reports/browser-report-2026-11-11-logo-favicon.md)。

截图证据：
[`docs/testing/evidence/2026-11-11/`](../../../docs/testing/evidence/2026-11-11/)。
