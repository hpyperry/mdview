# 固定页头岛测试报告（2026-11-07）

- 关联：Issue [#67](https://github.com/hpyperry/mdview/issues/67) / PR（待建）/ F-100
- 夹具：`tests/fixtures/page-head/README.md`
- 原型：`prototype/fixed-head` 分支（A 随滚动 / B 贴顶 / C 独立岛；用户选 C）
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
| F-100 | 页头独立岛 | 1440px 打开 `/all-levels.md` | 页头距主岛顶部 12px、左右内缩 14px，带圆角/边框/阴影；与正文分离 | 通过 | [F-100_fixed-head-top-1440.png](../evidence/2026-11-07/F-100_fixed-head-top-1440.png) |
| F-100 | 滚动时页头不动 | 向下滚正文 | 页头、顶栏、TOC 岛位置不变；只有正文滚动；页头操作仍可点 | 通过 | [F-100_fixed-head-scrolled-1440.png](../evidence/2026-11-07/F-100_fixed-head-scrolled-1440.png) |
| F-100 | 1366px | 打开 `/all-levels.md` | 页头岛正常，正文不被遮挡 | 通过 | [F-100_fixed-head-1366.png](../evidence/2026-11-07/F-100_fixed-head-1366.png) |
| F-100 | TOC 跳转避让 | 点击目录项 | 标题落在页头下缘 + 8–50px，不被页头遮住 | 通过 | 浏览器探针 `TOC 点击 h1/h2 跳转`、多 h1 跳转 |
| F-100 | 行定位避让 | 搜索命中跳转 / 源码 `#L` | 目标落在页头下方 | 通过 | 浏览器探针行定位与源码锚点 |
| F-100 | 移动端 | 390px | 页头不 sticky，保持普通文档流 | 通过 | 390 无横向溢出；CSS 媒体查询 |

## 发现

- 原型 A/B/C 中用户选择 C：独立页头岛。
- 页头高度约 129px（1440px）；TOC 跳转按运行时页头高度计算，长文件名换行也能避让。
- 行定位/源码锚点使用 `scroll-margin-top: 180px`，覆盖当前页头高度。
- 页头 sticky 只作用于 ≥901px；≤900px 保持普通页头。

## 覆盖缺口

- 仅 Chromium 156；Firefox/Safari 未人工复测。
- 触摸屏平板横屏（>900px）未单独验证页头 sticky 行为。
- 页头高度极端换行（超长文件名）只依赖运行时计算，未做视觉截图。

## 结论

- 通过。页头已按 C 方案固定为独立岛，正文滚动时操作始终可达；F-100 与全量本地
  套件通过，可以进入 PR 评审。
