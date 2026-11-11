# 主岛纵向滚动回弹修复测试报告（2026-11-11）

- 关联：F-98；本地分支 `fix/wide-layout`（Issue / PR 待建）
- 夹具：`tests/fixtures/overscroll/README.md`（README-only，复用 `tests/fixtures/wide-layout/root`）
- 类型：browser（滚动行为）+ 样式回归

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 分支 / commit | `fix/wide-layout`（本地提交，未推送） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 157.0.8103.39（headless / CDP） |
| 被测根 | `tests/fixtures/wide-layout/root`，入口 `/long.md` |
| 端口 | 8304 |

## 问题与修改

桌面端 `.content-card` 是唯一滚动容器。原来：

```css
overscroll-behavior-x: auto;
overscroll-behavior-y: contain;
```

按 CSS Overscroll Behavior 规范，`contain` 只阻止滚动链，“bounce” 仍会发生，
因此滚到顶部后继续滑动会出现 macOS 的弹性回弹。改为：

```css
overscroll-behavior-x: auto;   /* 保留触控板左右滑的浏览器后退/前进手势 */
overscroll-behavior-y: none;   /* 关闭纵向回弹，同时仍不向 body 传播 */
```

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 100 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=303 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=345 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | ok |
| 文档链接 | `node tests/check-doc-links.mjs` | ok |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

浏览器探针新增“主岛关闭纵向回弹”（`overscrollBehaviorY === 'none'`），并把原来的
横向检查拆成“主岛放行横向回退手势”（`overscrollBehaviorX === 'auto'`）。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-98 | 顶部回弹 | `/long.md`，触控板滚到顶部后继续上滑 | 内容不再被拉出，页面停住 | 待人工确认 | 见覆盖缺口 |
| F-98 | 底部回弹 | 滚到底部后继续下滑 | 同上 | 待人工确认 | 见覆盖缺口 |
| F-98 | 横向后退手势 | 双指从左向右滑 | 浏览器后退手势仍可用 | 通过 | 探针 `overscrollBehaviorX === 'auto'` |
| F-98 | 计算样式 | DevTools 选中 `.content-card` | y 为 `none`，x 为 `auto` | 通过 | 探针输出 |

## 覆盖缺口

- 回弹是 macOS/触控板的平台视觉效果，headless Chrome 无法复现或断言；本报告只
  验证计算样式与横向手势属性，物理回弹需在真实触控板上人工确认。
- 未在 Windows/Linux 上复核（这两个平台没有同款弹性回弹）。

## 结论

属性和规范一致：`overscroll-behavior-y: none` 会同时关闭纵向回弹与滚动链；
横向保持 `auto`，不影响浏览器的左右滑后退/前进。自动化全部通过，物理回弹等待
触控板人工确认。
