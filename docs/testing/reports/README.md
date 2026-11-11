# 当前测试报告

每个 feature/fix 一份报告，按日期与主题登记在下面；浏览器/视觉用
`browser-report-<YYYY-MM-DD>-<slug>.md`，后端/其他用
`test-report-<YYYY-MM-DD>-<slug>.md`。模板见 [`TEMPLATE.md`](TEMPLATE.md)。

当前测试计数与命令见 [`../selftest.md`](../selftest.md)，测试方法见
[`../agent-guide.md`](../agent-guide.md)。历史快照见
[`../../archive/testing/README.md`](../../archive/testing/README.md)。

| 日期 | 主题 | 报告 | 证据 | 功能 |
|---|---|---|---|---|
| 2026-10-26 | 导航分层预载 | [browser-report-2026-10-26-nav-lazy.md](browser-report-2026-10-26-nav-lazy.md) | [`../evidence/2026-10-26/`](../evidence/2026-10-26/) | F-46 / F-47 / F-49 |
| 2026-10-26 | 压缩包格式扩展 | [browser-report-2026-10-26-archive-formats.md](browser-report-2026-10-26-archive-formats.md) | [`../evidence/2026-10-26/`](../evidence/2026-10-26/) | F-81 / F-92 |
| 2026-10-27 | 文件编码检测 | [browser-report-2026-10-27-encodings.md](browser-report-2026-10-27-encodings.md) | [`../evidence/2026-10-27/`](../evidence/2026-10-27/) | F-89 / F-90 |
| 2026-11-04 | 旧引擎（Chromium 88）兼容 | [legacy-chromium-88-2026-11-04.md](legacy-chromium-88-2026-11-04.md) | 无截图（CDP 断言） | F-31 / F-76 / F-93 |
| 2026-11-06 | HTML 第二 origin | [browser-report-2026-11-06-html-second-origin.md](browser-report-2026-11-06-html-second-origin.md) | [`../evidence/2026-11-06/`](../evidence/2026-11-06/) | F-75 / F-77 / F-96 |
| 2026-11-06 | 右侧 TOC 目录岛与工具栏反馈 | [browser-report-2026-11-06-toc-island.md](browser-report-2026-11-06-toc-island.md) | [`../evidence/2026-11-06/`](../evidence/2026-11-06/) | F-50 / F-51 / F-52 / F-95 |
| 2026-11-06 | 统一页头 PageHead | [browser-report-2026-11-06-page-head.md](browser-report-2026-11-06-page-head.md) | [`../evidence/2026-11-06/`](../evidence/2026-11-06/) | F-29 / F-45 |
| 2026-11-06 | 全宽内容岛与 TOC 分栏动效 | [browser-report-2026-11-06-shell-layout.md](browser-report-2026-11-06-shell-layout.md) | [`../evidence/2026-11-06/`](../evidence/2026-11-06/) | F-29 / F-35 / F-45 / F-50 / F-51 / F-52 |
| 2026-11-07 | 渐进搜索与扫描上限 | [browser-report-2026-11-07-search-progressive.md](browser-report-2026-11-07-search-progressive.md) | [`../evidence/2026-11-07/`](../evidence/2026-11-07/) | F-99 |
| 2026-11-07 | 固定页头岛（已被顶栏方案取代） | [browser-report-2026-11-07-fixed-head.md](browser-report-2026-11-07-fixed-head.md) | [`../evidence/2026-11-07/`](../evidence/2026-11-07/) | F-100 |
| 2026-11-07 | 顶栏页面上下文（已被干净顶栏取代） | [browser-report-2026-11-07-topbar-context.md](browser-report-2026-11-07-topbar-context.md) | [`../evidence/2026-11-07/`](../evidence/2026-11-07/) | F-29 / F-45 / F-100 |
| 2026-11-07 | 干净顶栏与页头岛 | [browser-report-2026-11-07-clean-topbar.md](browser-report-2026-11-07-clean-topbar.md) | [`../evidence/2026-11-07/`](../evidence/2026-11-07/) | F-29 / F-45 / F-100 |
| 2026-11-07 | 大源码高亮空闲调度 | [test-report-2026-11-07-large-source-highlight.md](test-report-2026-11-07-large-source-highlight.md) | 无截图（CDP 长任务数据） | F-101 |
| 2026-11-07 | 布局 v5（顶栏/缝隙/主岛功能区）与文件工具 | [browser-report-2026-11-07-layout-v5.md](browser-report-2026-11-07-layout-v5.md) | [`../evidence/2026-11-07/`](../evidence/2026-11-07/) | F-100 / F-22 |
| 2026-11-07 | 源码页铺满与大块高亮 Worker | [browser-report-2026-11-07-source-worker.md](browser-report-2026-11-07-source-worker.md) | [`../evidence/2026-11-07/`](../evidence/2026-11-07/) | F-101 / F-100 |
| 2026-11-11 | 宽屏外壳铺满与主岛让位 | [browser-report-2026-11-11-wide-layout.md](browser-report-2026-11-11-wide-layout.md) | [`../evidence/2026-11-11/`](../evidence/2026-11-11/) | F-50 / F-20 / F-30 / F-33 / F-52 |
| 2026-11-11 | 主岛纵向滚动回弹修复 | [browser-report-2026-11-11-overscroll.md](browser-report-2026-11-11-overscroll.md) | 无截图（计算样式 + 触控板人工确认） | F-98 |
