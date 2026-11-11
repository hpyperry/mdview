# 宽屏外壳铺满与主岛让位测试报告（2026-11-11）

- 关联：F-50；本地分支 `fix/wide-layout`（Issue / PR 待建）
- 夹具：`tests/fixtures/wide-layout/README.md`
- 类型：browser（浏览器/视觉）+ 布局回归

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 分支 / commit | `fix/wide-layout`（本地提交，未推送） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 157.0.8103.39（headless / CDP） |
| 被测根 | `tests/fixtures/wide-layout/root` |
| 端口 | 8304（截图）/ 探针随机端口 |

## 背景与目标

2.5.x 的 `.app` 上限 1680px、正文上限 1200px。2560px 视口下外壳只占 1680
（两侧各 440px 空白），主岛 1376、正文 1200，正文与 TOC 之间再空 176px，
看起来没有撑满。

目标：

1. 去掉 1680px 上限，顶栏与主岛铺满视口；
2. Markdown 页主岛左边缘保持不动，右边缘只向左让出“TOC 岛宽度 + 32px”；
3. TOC 岛保持在主岛右侧、与顶栏右边缘对齐，两块面板之间露出页面底色；
4. 正文在主岛内居中，1200px 阅读行宽不变；主岛、工具栏、面包屑和 TOC 岛不动。

中途试过“主岛拉满 + TOC 绝对定位”（TOC 画在主岛表面上）和“主岛收窄 + 整体
居中”（超宽屏两侧各留 528px）两种方案，都不符合第 2 条，已改回最终的让位方案。

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 100 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=303 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=344 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | ok |
| 文档链接 | `node tests/check-doc-links.mjs` | ok |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

浏览器探针新增/改写断言：

- 1440：主岛左侧与顶栏对齐；目录岛右侧与顶栏对齐；主岛与目录岛之间 32px；
  正文在主岛内居中（左右留白相等）；正文宽 ≥1000；
- 2560：主岛左侧与顶栏对齐、目录岛右侧与顶栏对齐、两块面板间隔 32px；正文仍为
  1200px 且在主岛内居中；无横向溢出；
- 1600：正文卡片宽度 >1240（保留原断言）；
- 1280 / 1200 / 1000：细轨、单列与窄屏行为保持原断言。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-50 | 2560 文档 | 打开 `/guide.md`，2560×1440 | 主岛 16–2272（2256）；目录岛 2304–2544（240）；间隔 32；正文 544–1744（1200，两侧各 528）；工具栏/面包屑不动 | 通过 | [`../evidence/2026-11-11/wide-layout-2560-doc.png`](../evidence/2026-11-11/wide-layout-2560-doc.png) |
| F-50 | 2560 长目录 | 打开 `/long.md` | 目录岛与主岛同高，目录在岛内滚动 | 通过 | [`../evidence/2026-11-11/wide-layout-2560-long.png`](../evidence/2026-11-11/wide-layout-2560-long.png) |
| F-50 | 2560 深色 | 切换深色 | 两块面板的底色/边框与浅色布局一致 | 通过 | [`../evidence/2026-11-11/wide-layout-2560-doc-dark.png`](../evidence/2026-11-11/wide-layout-2560-doc-dark.png) |
| F-20 | 2560 目录页 | 打开 `/` | 主岛铺满；列表仍 1100px 居中 | 通过 | [`../evidence/2026-11-11/wide-layout-2560-dir.png`](../evidence/2026-11-11/wide-layout-2560-dir.png) |
| F-33 | 2560 源码页 | 打开 `/code.rs?raw=1` | 代码背景与行号栏铺满主岛 | 通过 | [`../evidence/2026-11-11/wide-layout-2560-source.png`](../evidence/2026-11-11/wide-layout-2560-source.png) |
| F-30 | 2560 搜索页 | `/search?__mdview=search&q=正文` | 页头与结果限宽到阅读行宽 + TOC 宽度并居中 | 通过 | [`../evidence/2026-11-11/wide-layout-2560-search.png`](../evidence/2026-11-11/wide-layout-2560-search.png) |
| F-50 | 1440 | 打开 `/guide.md` | 主岛 16–1205；目录岛 1237–1424；间隔 32；正文 1145 | 通过 | [`../evidence/2026-11-11/wide-layout-1440-doc.png`](../evidence/2026-11-11/wide-layout-1440-doc.png) |
| F-50 | 1280 临界 | 打开 `/guide.md` | 仍为常驻目录岛；主岛 1050、目录岛 166 | 通过 | [`../evidence/2026-11-11/wide-layout-1280-doc.png`](../evidence/2026-11-11/wide-layout-1280-doc.png) |
| F-50 | 1200 细轨 | 打开 `/long.md` | 24px 细轨，回顶按钮右移 46px | 通过 | [`../evidence/2026-11-11/wide-layout-1200-rail.png`](../evidence/2026-11-11/wide-layout-1200-rail.png) |
| F-52 | 390 移动端 | 打开 `/guide.md` | 单列、内联目录，面板不重叠 | 通过 | [`../evidence/2026-11-11/wide-layout-390-mobile.png`](../evidence/2026-11-11/wide-layout-390-mobile.png) |

改动前后的实测对照（headless Chrome）：

| 视口 | 项目 | 改动前（2.5.2） | 改动后 |
|---|---|---|---|
| 2560×1440 | `.app` / 顶栏 | 1680（两侧各 440） | 2560 / 顶栏 2528 |
| 2560×1440 | 主岛 | 1376（距外壳左侧 120） | 2256（左边缘 16，右边缘 2272） |
| 2560×1440 | 正文 | 1200 | 1200（544–1744，主岛内居中） |
| 2560×1440 | 目录岛 | 240，贴主岛右侧 | 240，2304–2544，贴主岛右侧 |
| 2560×1440 | 主岛/目录岛间隔 | 32 | 32（页面底色） |
| 1920×1080 | 主岛 | 1376 | 1616 |
| 1440×900 | 主岛 | 1189 | 1189（正文 38–1183，两侧各 22） |

## 发现

- 前两版布局都不符合“主岛左边缘不动、右边缘让位”的目标：绝对定位会让 TOC 画在
  主岛表面，整体居中会让超宽屏两侧各留 528px。最终直接沿用 2.5.x 的两列网格，
  只去掉 `.app` 的 1680px 上限。
- 两列轨道从首帧就存在，TOC 挂载只做淡入，不会出现宽度跳变；无标题文档
  （`.no-toc`）恢复单列，主岛重新铺满。
- 超宽屏上主岛右侧的空白是文档画布的一部分（正文仍保持 1200px），不是外壳之外
  的灰边；如果以后要增大正文行宽，应单独调整 `--read-width`，不要把“正文 + TOC”整组居中。
- 搜索页仍限宽到“阅读行宽 + TOC 宽度”并居中，避免结果行横贯整屏；目录页列表、
  信任/错误面板的宽度上限保持不变。

## 覆盖缺口

- 只在 headless Chrome 157 模拟 2560×1440、1920×1080、1440、1280、1200、
  1000、390；未在真实 2K/4K/超宽屏或浏览器 80%/125% 缩放下人工复核。
- Chromium 88 旧内核未实机验证两列网格与 `clamp()` 宽度；`check-css-baseline.mjs`
  只拦语法，不验证布局结果。
- 1100–1279 细轨与 <1100 内联目录只跑既有探针与 1200/390 截图，未补每个宽度的
  视觉对照。
- 无 JS 基线只在探针中断言控件隐藏与单列，未在 2560 下单独截图。

## 结论

通过。顶栏与主岛在超宽屏铺满视口；进入 Markdown 页时主岛左边缘不动，右边缘只
向左让出 272px（TOC 240 + 间距 32），目录岛落在主岛右侧并与顶栏右边缘对齐；
正文在主岛内居中（2K 下两侧各 528px），主岛、工具栏、面包屑和目录岛位置不变；
正文位置与 1200px 阅读行宽不变；1440/1280/1200/1000 与移动端行为未变。F-50
验收口径、浏览器探针与 ADR 0036 已同步。
