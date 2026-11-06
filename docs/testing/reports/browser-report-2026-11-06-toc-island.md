# 右侧 TOC 目录岛浏览器验收报告（2026-11-06）

关联：[Issue #63](https://github.com/hpyperry/mdview/issues/63) ·
PR #64（待建） · [ADR 0026](../../architecture/adr/0026-toc-island-layout.md)。
功能：F-50 / F-51 / F-52；附 F-95 工具栏完成反馈。

> 后续修正：F-95 完成反馈已改为约 500ms 的完成图标 + 禁用窗口，并移除
> “图片已生成”成功文案；最新验收见
> [browser-report-2026-11-06-page-head.md](browser-report-2026-11-06-page-head.md)。
> 布局断点与宽度已由 ADR 0028 调整（≥1280px 常驻岛、全宽主岛），最新验收见
> [browser-report-2026-11-06-shell-layout.md](browser-report-2026-11-06-shell-layout.md)。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-06 |
| 分支 | `feat/toc-island-layout`（基于 `main` @ `28d24f4`） |
| 平台 | macOS 27.2 arm64 |
| Rust | 1.96.0 |
| Node | v22.22.3 |
| 浏览器 | Chrome 156.0.8078.80（headless 探针）；Chromium 152（Electron 手工） |
| 被测根 | `tests/fixtures/toc-all-levels/root` |
| 端口 | 8290（本地 `--trust`） |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元/集成 | `cargo test --lib` | **94 passed** |
| Golden | `cargo test --test golden` | **27 cases passed** |
| 渲染兼容 | `cargo test --test render_compat` | **134 passed** |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | **PASS=292 FAIL=0** |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=299 FAIL=0** |
| TTY 信任 | `bash tests/trust-tty.sh` | **PASS=9 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | **4 项预算通过** |
| artifact 冒烟 | `bash tests/smoke-artifact.sh target/release/mdview` | **PASS=7 FAIL=0** |
| 全量本地验收 | `bash tests/run-all.sh` | **ALL LOCAL CHECKS PASSED** |

关键探针断言（1440px 细轨模式）：

- 细轨可见；`totop` 的 `right` 为 `46px`，不与细轨重叠；
- 悬停刻度出现该标题浮层，移出消失；悬停细轨不会自动展开完整面板；
- 点击顶部按钮展开大纲；h1/h2 文字项点击后滚到顶栏下约 88px；
- 多 h1 文档 h1 A/B/D 均可跳转；文末 h1 D 滚到最大位置且可见。

关键探针断言（1600px 常驻岛模式）：

- `#toc-island` 显示，宽度 ≥220px（1600px 视口约 304px）；正文卡片仍为 1240px；
- 细轨按钮/刻度隐藏；全局 `totop` 隐藏，目录岛内有 `回到顶部`；
- 点击目录岛 h1 可跳转，active 跟随；
- `/long.md` 的 61 个标题在目录岛内独立滚动，当前项自动进入视野。

## 视觉与交互验收

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-50 | 1600px 常驻目录岛 | 打开 `/all-levels.md`，窗口 1600×900 | 正文 1240 固定；右侧 ≥220px 文字目录岛（随剩余宽度伸展）；间距 24；两岛外缘与顶栏同 padding；目录岛内“回到顶部”；不显示“本页目录”标题/数量徽标 | 通过 | [F-50_toc-island-1600.png](../evidence/2026-11-06/F-50_toc-island-1600.png) |
| F-50 | 1440px 细轨 | 打开 `/all-levels.md`，窗口 1440×900 | 正文 1240；右侧 24px 细轨；回顶按钮在细轨左侧，不重叠 | 通过 | [F-50_toc-rail-1440.png](../evidence/2026-11-06/F-50_toc-rail-1440.png) |
| F-51 | 常驻岛浅色选中态 | 1600px，浅色主题，打开 `/all-levels.md` | 选中项无整行底色，只用左侧强调条 + 蓝色文字；不显示“本页目录”标题/数量徽标 | 通过 | [F-51_toc-island-light-1600.png](../evidence/2026-11-06/F-51_toc-island-light-1600.png) |
| F-51 | 细轨展开大纲浅色 | 1440px，浅色主题，点击顶部按钮 | 面板不显示“本页目录”标题文字，只保留右上角关闭图标；当前项无整行底色，点击/聚焦不再出现蓝色整框，改为浅灰底 + 左侧强调条 | 通过 | [F-51_toc-popover-light-1440.png](../evidence/2026-11-06/F-51_toc-popover-light-1440.png) |
| F-51 | 细轨悬停单条标题 | 悬停 h1 刻度 | 只出现该标题浮层；横向排版，不展开完整面板 | 通过 | 浏览器探针断言（瞬时状态） |
| F-51 | 细轨完整大纲 | 点击顶部按钮 | 展开 7 条文字大纲；点外部/Esc 收起；固定后移出不收起 | 通过 | 浏览器探针断言 |
| F-50 | 多 h1 跳转 | 1600px，从顶部点 h1 B/D，从底部点 h1 A | h1 B 到 88px；h1 D 到页面最大值且可见；h1 A 回 88px | 通过 | 浏览器探针断言；夹具 `multi-h1.md` |
| F-50 | 长文档目录岛 | 1600px，打开 `/long.md`，滚到底 | 目录岛列表独立滚动，当前项进入岛内 | 通过 | 浏览器探针断言 |
| F-95 | 下载/导出完成反馈 | 点击文档页「下载」 | 原图标立即换成绿色对勾，1 秒后恢复；文字保持「下载」 | 通过 | [F-95_toolbar-download-done.png](../evidence/2026-11-06/F-95_toolbar-download-done.png) |
| F-95 | 导出图片完成反馈 | 点击「导出图片」 | PNG 生成完成后原图标换成绿色对勾，1 秒后恢复 | 通过 | 浏览器探针断言（MutationObserver） |

## 发现

- 旧鱼骨的三个问题都已消除：刻度悬停能读出具体标题；细轨悬停不再等于导航
  按钮；返回顶部不再覆盖目录。
- h1 跳转在 Chrome 156 与 Chromium 152（Electron）下都正常。实现改为
  “顶栏高度 + 32px” 的即时 `window.scrollTo`，不再依赖 smooth scroll。
- 多 h1 文档按 DOM 顺序生成多个 h1 条目，ID 唯一，跳转正常。
- 1600px 下正文卡片实测 1240px，没有因目录岛出现而缩窄。
- 下载/导出图片完成后只替换图标，不改按钮文案；1 秒后恢复原图标。

## 覆盖缺口

- 没有在 Chromium 88 上复跑新的常驻目录岛；CSS 已通过 Chromium 88 lint，
  但旧内核的实际 sticky/滚动表现仍需人工确认。
- 没有测 1560px 临界点的 1px 抖动；当前以 1560 为断点，滚动条宽度已留余量。
- 悬停浮层是瞬时状态，截图为静态页面；只保留了探针断言，没有单独截图。
- 没有测触屏/窄屏的常驻岛（<1360px 走内联目录）。
- 反向代理/缩放下 `.app` 实际宽度可能变化；断点按 CSS 像素计算。

## 结论

通过。宽屏下正文与目录是两个独立岛，正文宽度不变；中等宽度保留细轨，但悬停
能读出具体标题；返回顶部在常驻岛内或与细轨错开。可以进入合并/发布流程。
