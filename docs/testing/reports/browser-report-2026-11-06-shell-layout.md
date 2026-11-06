# 全宽内容岛与 Markdown 分栏动效测试报告（2026-11-06）

- 关联：Issue [#65](https://github.com/hpyperry/mdview/issues/65) / PR（待建）/ F-29、F-35、F-45、F-50、F-51、F-52、F-98
- 夹具：`tests/fixtures/toc-all-levels/README.md`（TOC 断点与分栏）、`tests/fixtures/page-head/README.md`（页头与全宽）
- 类型：browser（浏览器/视觉）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-06 |
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
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=329 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/artifact-smoke.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-45 | 目录页全宽 | 1440px 打开 `/` | 主岛铺满 `.app`，左右边缘与顶栏一致；不再居中 1240px | 通过 | [F-45_dir-full-width-1440.png](../evidence/2026-11-06/F-45_dir-full-width-1440.png) |
| F-29 | 源码页全宽且无下载 | 1440px 打开 `/all-levels.md?raw=1` | 主岛与顶栏对齐；页头右侧只有「预览」，没有下载按钮 | 通过 | [F-29_source-no-download-1440.png](../evidence/2026-11-06/F-29_source-no-download-1440.png) |
| F-45 | 搜索页全宽 | 1440px 打开搜索页 | 主岛铺满并与顶栏对齐；表单仍在页头右侧 | 通过 | [F-45_search-full-width-1440.png](../evidence/2026-11-06/F-45_search-full-width-1440.png) |
| F-50 | 1440px 分栏 | 打开 `/all-levels.md` | 主岛从整宽收右边缘，右侧出现约 187px TOC 岛；正文行宽不变，两岛外缘与顶栏对齐 | 通过 | [F-50_shell-split-1440.png](../evidence/2026-11-06/F-50_shell-split-1440.png) |
| F-50 | 1366px 分栏 | 打开 `/all-levels.md` | 同上；TOC 岛约 178px，正文约 1080px，不再因 1240px 居中而浪费两侧 | 通过 | [F-50_shell-split-1366.png](../evidence/2026-11-06/F-50_shell-split-1366.png) |
| F-50 | 1600px 分栏 | 打开 `/all-levels.md` | 主岛更宽；TOC 岛约 208px；正文上限 1200px | 通过 | [F-50_shell-split-1600.png](../evidence/2026-11-06/F-50_shell-split-1600.png) |
| F-50 | 分栏动效 | 进入 Markdown 页 | `body[data-has-toc="1"]` 时播放 `shell-split` + `toc-island-in`（240ms）；主岛右缘收起，正文不重新居中 | 通过 | 浏览器探针断言 `animationName`/`animation-duration`；截图见上 |
| F-50 | 1200px 细轨 | 1200px 打开 `/all-levels.md` | 24px 细轨；悬停只显示单条标题，点击按钮展开大纲；回顶按钮右移 46px | 通过 | 浏览器探针 `== three columns ==` |
| F-52 | 1000px 内联 | 1000px 打开 `/all-levels.md` | 单列，目录回到正文顶部可折叠块 | 通过 | 浏览器探针 `1000 单列/内联目录` |
| F-35 | 源码无下载 | 打开任意 `.txt?raw=1` | 页头没有 `.page-actions a[href*="?download=1"]`；仍可直接请求 `?download=1` 下载 | 通过 | 浏览器探针、黑盒 `源码页无下载入口` |
| F-98 | 目录岛回顶 | 打开短文档 | 「回到顶部」固定在 TOC 岛底部，不紧跟标题列表悬在岛中间 | 通过 | [F-50_shell-split-1440.png](../evidence/2026-11-06/F-50_shell-split-1440.png) |
| F-98 | 固定主岛 | 1440px 打开 `/all-levels.md`，滚动正文 | 主岛、顶栏、TOC 岛位置不变；只有 `.content-card` 的 `scrollTop` 变化，`window.scrollY` 恒为 0 | 通过 | [F-98_fixed-island-top-1440.png](../evidence/2026-11-06/F-98_fixed-island-top-1440.png) · [滚动后](../evidence/2026-11-06/F-98_fixed-island-scrolled-1440.png) |
| F-98 | 岛内滚动 | 滚动目录页、源码页、搜索结果 | 内容在岛内滚动，主岛高度固定为视口剩余高度 | 通过 | 浏览器探针 `主岛固定只滚动内容` / `主岛高度适配视口` |

## 动效验证

在 1440px 下移除再重新挂载 `body[data-has-toc]`，采样 `#shell` 的
`gridTemplateColumns`：

```text
before: 1408px
at0:    1408px 0px
at70:   1323.53px 77.8281px
at170:  1232.02px 162.141px
after:  1204.81px 187.188px
animationName: shell-split
animationDuration: 0.24s
```

说明主岛从整宽连续收窄到 `1fr + 216px`，不是瞬间跳变；正文行宽由
`--read-width` 固定，采样期间内容没有重新居中。

## 发现

- 主岛原先 `max-width: 1240px` 居中，与顶栏不对齐；现在所有内容页铺满 `.app`。
- Markdown 分栏动画通过 `body[data-has-toc]` 在 TOC 挂载完成后触发；没有 JS 时主岛
  保持整宽，不会出现空白分栏。
- 正文使用 `--read-width` 固定上限并左对齐，分栏时只收主岛右边缘，文字不移动、
  不回流。
- 源码页下载按钮已移除，但 `?download=1` 接口保留；目录行与文档页下载不受影响。
- 浏览探针新增了主岛/顶栏边缘、1440 分栏、动画名、源码无下载、固定主岛与岛内滚动等断言。
- 桌面端 body 不再滚动；`window.scrollY` 恒为 0，回顶、TOC 跳转、scroll-spy 与大源码
  懒加载都改为读取 `.content-card`。移动端 ≤900px 仍使用文档滚动。

## 覆盖缺口

- 仅验证 Chromium 156；Firefox/Safari 未人工复测。
- Chromium 88 没有 grid 过渡时会直接落到最终分栏，只做了 CSS 基线 lint，未在真机
  录制动画。
- 分栏动画只验证了计算样式与终点布局，没有逐帧截图。
- 固定主岛只在 Chromium 桌面尺寸验证；移动端仍走文档滚动，未单独验证平板横屏。
- 超宽屏（≥1920px）未单独截图；正文上限 1200px 的留白属于设计取舍。

## 结论

- 通过。内容岛已铺满并对齐顶栏，Markdown 在 1280px 以上平滑分出 TOC 岛，正文行宽
  不变；源码页下载入口已移除。全量本地套件通过，可以进入 PR 评审。
