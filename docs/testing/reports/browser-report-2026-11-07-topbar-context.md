# 顶栏页面上下文测试报告（2026-11-07）

> 后续：页面身份已回退到内容区页头岛，本报告方案由
> [browser-report-2026-11-07-clean-topbar.md](browser-report-2026-11-07-clean-topbar.md) 取代。

- 关联：Issue [#67](https://github.com/hpyperry/mdview/issues/67) / PR（待建）/ F-29、F-45、F-100
- 夹具：`tests/fixtures/page-head/README.md`
- 原型：`prototype/topbar-actions` 分支（A/B/C 与后续间距/菜单迭代；最终选 C）
- 类型：browser（浏览器/视觉）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `refactor/page-head-component`（PR 待建） |
| 平台 | macOS arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `tests/fixtures/toc-all-levels/root` |
| 启动 | `target/release/mdview --root tests/fixtures/toc-all-levels/root --trust --port 8005 --port-tries 0` |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 / 集成 | `cargo test` | 96 + 134 + 27 passed |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=292 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=331 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/smoke-artifact.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-100 | 顶栏身份 | 1440px 打开 `/all-levels.md` | 去掉 logo；导航+面包屑在左，文件名 22px 居中、元信息第二行，点状菜单/搜索/主题在右 | 通过 | [F-100_topbar-1440.png](../evidence/2026-11-07/F-100_topbar-1440.png) |
| F-100 | 顶栏固定 | 滚动正文 | 顶栏、主岛、TOC 岛位置不变；正文在岛内滚动；操作菜单始终可点 | 通过 | [F-100_topbar-scrolled-1440.png](../evidence/2026-11-07/F-100_topbar-scrolled-1440.png) |
| F-100 | 操作二级菜单 | 点「…」 | 142px 面板：源码/下载/导出图片/导出 PDF；Esc/外部点击关闭；导出时保持打开显示完成图标 | 通过 | [F-100_topbar-menu-1440.png](../evidence/2026-11-07/F-100_topbar-menu-1440.png) |
| F-100 | 窄屏降级 | 1280px 打开 | 隐藏编码/时间徽标，菜单文字保留在弹层内，顶栏仍一行 | 通过 | [F-100_topbar-1280.png](../evidence/2026-11-07/F-100_topbar-1280.png) |
| F-100 | 岛间距 | 1440px | 顶栏→主岛、主岛→TOC 岛均为 24px | 通过 | 浏览器探针几何断言 |
| F-100 | 源码/目录 | 打开 `?raw=1` 与 `/sub/` | 顶栏上下文与面包屑一致；源码菜单只有预览，目录菜单按需出现 | 通过 | 浏览器探针 |
| F-100 | 搜索页例外 | 打开搜索页 | 搜索表单仍在内容面页头；顶栏只保留导航/搜索/主题 | 通过 | 浏览器探针 |

## 发现

- 顶栏页头避免了固定页头占用的约 129px，正文直接从主岛顶部开始；
- `actions` 岛负责菜单开合；导出图片时菜单不自动关闭，确保完成绿色对勾可见；
- 面包屑去掉当前文件名和文件夹图标，避免与居中文件名重复；
- 1280px 隐藏元信息，900px 隐藏面包屑，窄屏菜单内部仍保留四项文字；
- 搜索页是唯一保留 content 页头的页面，因为表单需要独立宽度。

## 覆盖缺口

- 仅 Chromium 156；Firefox/Safari 未人工复测。
- 顶栏高度在超长文件名 + 多徽标组合下依赖 1280 的隐藏规则，未做逐像素截图。
- 触摸屏平板横屏（>900px）未单独验证菜单点击区域。

## 结论

- 通过。页面身份与操作已迁入全局顶栏，正文空间最大化，F-29/F-45/F-100 与全量
  本地套件通过，可以进入 PR 评审。
