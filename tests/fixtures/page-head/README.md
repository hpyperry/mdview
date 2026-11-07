# 干净顶栏与页头岛复测文档

- 关联：Issue [#67](https://github.com/hpyperry/mdview/issues/67) / PR（待建）/ F-29 / F-45 / F-100
- 关联测试报告：`docs/testing/reports/browser-report-2026-11-07-clean-topbar.md`
- 证据：`docs/testing/evidence/2026-11-07/F-100_clean-topbar-*.png`
- 夹具根：`tests/fixtures/page-head/`（可直接作为 `--root`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/page-head --trust --port 8004 --port-tries 0
```

- 入口：`/`
- 自动化覆盖：`src/server.rs` 的页头结构断言；`tests/browser-probe.mjs` 的顶栏
  三控件、页头岛几何、长面包屑、四类页头一致性断言。

## 复测步骤

1. 操作：打开 `/doc.md`。
   预期：顶栏只有最左导航、右侧搜索和主题，没有 logo、面包屑或页面操作；内容区
   顶部是独立页头岛：面包屑、文件名 H1、Markdown/大小/编码/更新时间徽标，右侧
   源码/下载/导出图片/导出 PDF。

2. 操作：打开深层目录里的一个文件，让面包屑变长。
   预期：面包屑在页头内换行或占满可用宽度，**不会覆盖**文件名和元信息；操作按钮
   仍在右侧，不被挤走。

3. 操作：打开 `/doc.md?raw=1`、`/sub/`、搜索页。
   预期：源码/目录/搜索都使用同一页头岛结构；源码页只保留预览，目录页显示项目数，
   搜索页保留搜索表单；顶栏始终只有导航/搜索/主题。

4. 操作：滚动 Markdown 正文。
   预期：页头岛固定在主岛顶部，正文在岛内滚动；顶栏和页头操作仍然可见；长文档
   TOC 跳转、搜索行定位、源码 `#L` 锚点落在页头下方。

5. 操作：缩窄到 1366/1280/900px。
   预期：页头岛仍在内容区，面包屑和操作按现有响应式规则换行；顶栏不增加页面信息。

## 已知限制

- 页头占据约 129px 高度，这是为了始终可达的页面操作与路径。
- 超长无空格路径会在页头内换行，可能把页头撑高。
- 顶栏不再提供页面级快捷操作；操作在页头岛内。

## 清理

- 停止临时服务，释放端口。
