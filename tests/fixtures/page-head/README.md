# 统一页头（PageHead）复测文档

- 关联：Issue [#65](https://github.com/hpyperry/mdview/issues/65) / PR（待建）/ F-29 / F-45
- 关联测试报告：`docs/testing/reports/browser-report-2026-11-06-page-head.md`
- 证据：`docs/testing/evidence/2026-11-06/F-45_page-head-*.png`
- 夹具根：`tests/fixtures/page-head/`（可直接作为 `--root`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/page-head --trust --port 8004 --port-tries 0
```

- 入口：`/`
- 自动化覆盖：`src/server.rs` 的页头结构/元信息断言；`tests/browser-probe.mjs`
  的四类页头结构、标题、徽标、操作与 800px 搜索页紧凑断言。

## 复测步骤

1. 操作：打开 `/doc.md`。
   预期：页头依次是面包屑、文件名 H1（`doc.md`）、`Markdown` / 大小 / 编码 /
   更新时间徽标；右侧为「源码 / 下载 / 导出图片 / 导出 PDF」；正文自己的 H1
   仍在页头下方，不重复显示文件名。

2. 操作：打开 `/doc.md?raw=1`。
   预期：页头结构与文档页一致，只是标题下方徽标增加行数，右侧动作只保留
   「预览」，不再有下载按钮；没有正文 H1。

3. 操作：打开 `/` 与 `/sub/`。
   预期：目录页同样使用面包屑 + 目录名 H1 + 项目数徽标；主岛铺满屏幕并与
   顶栏左右对齐；压缩包目录还会有格式 / 大小 / 条目数徽标和「下载压缩包」。

4. 操作：打开 `/search?__mdview=search&q=页头`。
   预期：搜索页使用面包屑 + 查询标题 H1 + 文件数/结果数徽标；搜索表单在页头
   右侧，宽屏与标题同一行。

5. 操作：把浏览器缩到 800px 宽再打开搜索页。
   预期：搜索表单换到标题下方，与标题/徽标保持紧凑，不被挤到页面底部。

6. 操作：在文档页点「下载」或「导出图片」。
   预期：页头操作按钮位置不变；完成反馈仍然是图标短暂换成绿色对勾。

## 已知限制

- 页头是服务端 Rust 模板，不是 Preact 岛；无 JS 时仍是权威 HTML。
- 信任页/错误页保留专用面板，不使用 PageHead。
- 旧内核只做 CSS 基线检查，视觉人工复测仍以 Chromium 为准。

## 清理

- 停止临时服务，释放端口；不需要清理解压缓存（本夹具不含压缩包）。
