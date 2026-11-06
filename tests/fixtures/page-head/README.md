# 顶栏页面上下文复测文档

- 关联：Issue [#65](https://github.com/hpyperry/mdview/issues/65) / [#67](https://github.com/hpyperry/mdview/issues/67) / PR（待建）/ F-29 / F-45 / F-100
- 关联测试报告：`docs/testing/reports/browser-report-2026-11-07-topbar-context.md`
- 证据：`docs/testing/evidence/2026-11-07/F-100_*.png`
- 夹具根：`tests/fixtures/page-head/`（可直接作为 `--root`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/page-head --trust --port 8004 --port-tries 0
```

- 入口：`/`
- 自动化覆盖：`src/server.rs` 的顶栏结构/岛清单断言；`tests/browser-probe.mjs`
  的顶栏路径/文件名/元信息、点状菜单开合、窄屏与全宽布局断言。

## 复测步骤

1. 操作：打开 `/doc.md`。
   预期：顶栏从左到右是导航按钮、`root ›` 面包屑、居中的文件名 `doc.md`
   （22px）、文件名下的 `Markdown`/大小/编码/更新时间徽标；右侧是点状操作菜单、
   搜索和主题。产品 logo 不再显示。

2. 操作：点击点状菜单。
   预期：展开 142px 二级菜单，依次是源码/下载/导出图片/导出 PDF；Esc 或点击外部
   关闭；下载/导出完成后菜单里的图标短暂变成绿色对勾。

3. 操作：打开 `/doc.md?raw=1`。
   预期：顶栏结构与文档页一致，操作菜单只有「预览」；没有下载按钮；正文直接开始。

4. 操作：打开 `/` 与 `/sub/`。
   预期：目录页同样在顶栏显示面包屑、目录名和项目数；压缩包目录的操作菜单里有
   「下载压缩包」。

5. 操作：打开搜索页。
   预期：搜索页是例外，仍在内容面顶部显示搜索页头和表单；顶栏只保留导航、搜索、
   主题。

6. 操作：在 `/doc.md` 向下滚动正文，再缩窄窗口。
   预期：顶栏固定在顶部、正文在岛内滚动；缩到 1280px 以下时隐藏编码/时间徽标，
   缩到 900px 以下时隐藏面包屑，只保留文件名和菜单。

## 已知限制

- 搜索页仍保留内容面页头，因为搜索表单不适合放进顶栏。
- 顶栏文件名过长时会省略；完整路径在面包屑中。
- 顶栏菜单使用原生 `title` 提示，不使用自定义浮层。

## 清理

- 停止临时服务，释放端口。
