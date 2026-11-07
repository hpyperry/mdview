# 干净顶栏与页头岛测试报告（2026-11-07）

- 关联：Issue [#67](https://github.com/hpyperry/mdview/issues/67) / PR（待建）/ F-29、F-45、F-100
- 夹具：`tests/fixtures/page-head/README.md`
- 类型：browser（浏览器/视觉）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `fix/clean-topbar-page-head`（PR 待建） |
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
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=331 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/smoke-artifact.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-100 | 干净顶栏 | 1440px 打开 `/all-levels.md` | 顶栏只有导航、搜索、主题；没有 logo/面包屑/操作 | 通过 | [F-100_clean-topbar-doc-1440.png](../evidence/2026-11-07/F-100_clean-topbar-doc-1440.png) |
| F-100 | 页头岛 | 同上 | 内容区顶部独立页头：面包屑、文件名、元信息、操作；长面包屑不越界 | 通过 | 同上 |
| F-100 | 滚动固定 | 滚动正文 | 页头岛固定在主岛顶部，正文在岛内滚动；顶栏不动 | 通过 | [F-100_clean-topbar-scrolled-1440.png](../evidence/2026-11-07/F-100_clean-topbar-scrolled-1440.png) |
| F-100 | 源码页一致 | 打开 `?raw=1` | 顶栏仍只有三控件；内容页头显示文件名/类型/大小/编码/行数/更新时间与预览 | 通过 | [F-100_clean-topbar-source-1440.png](../evidence/2026-11-07/F-100_clean-topbar-source-1440.png) |
| F-100 | 1366px | 打开 `/all-levels.md` | 页头岛与操作完整，顶栏干净 | 通过 | [F-100_clean-topbar-doc-1366.png](../evidence/2026-11-07/F-100_clean-topbar-doc-1366.png) |
| F-45 | 长面包屑 | 深层路径文件 | 面包屑在页头内换行，不覆盖文件名/元信息 | 通过 | 浏览器探针页头几何断言 |
| F-45 | 四类页头一致 | 文档/源码/目录/搜索 | 都是内容区 `PageHead`；搜索页保留表单 | 通过 | 浏览器探针 |

## 发现

- 顶栏页面上下文方案在长面包屑下会覆盖居中文件名，且无操作菜单的页面会把
  搜索/主题挤到中间；本版回退为干净顶栏。
- 页面身份与操作回到内容区 sticky 页头岛，所有页面结构一致；长面包屑在页头内
  换行，不再和文件名抢同一行。
- 顶栏从 64px 回到 56px，页面多出的空间来自取消顶栏页面上下文；页头岛仍占约 129px。
- 移除了 `actions` 岛与二级菜单，操作直接显示在页头右侧。

## 覆盖缺口

- 仅 Chromium 156；Firefox/Safari 未人工复测。
- 超长无空格路径会撑高页头，未做逐像素截图。
- 触摸屏平板横屏（>900px）未单独验证页头 sticky。

## 结论

- 通过。顶栏恢复干净三控件，页面身份/操作回到内容区页头岛；长面包屑覆盖问题
  与页面间位置不一致问题已修复，F-29/F-45/F-100 与全量本地套件通过。
