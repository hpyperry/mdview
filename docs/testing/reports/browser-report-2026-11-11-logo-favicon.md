# 品牌标记与 favicon 测试报告（2026-11-11）

- 关联：F-100 / ADR 0037；本地分支 `fix/wide-layout`（Issue / PR 待建）
- 夹具：`tests/fixtures/logo-favicon/README.md`
- 类型：browser（顶栏/视觉）+ 资产接口

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 分支 / commit | `fix/wide-layout`（本地提交，未推送） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 157.0.8103.39（headless / CDP） |
| 被测根 | `docs/`（截图）/ 探针夹具 |
| 端口 | 8321（截图）/ 探针随机端口 |

## 改动

- 新标记：32×32 蓝色（`#0969da`）圆角方块 + 白色 Markdown “M” 折线；
- 顶栏最左、导航按钮之前放 24×24 的标记，链接到 `/`，`aria-label="返回首页"`；
- `<head>` 加 `image/svg+xml` 与 32×32 `image/png` 两条 favicon 链接；
- 新增 `/_assets/favicon.svg`、`/_assets/favicon.png` 资产路由，带
  `__mdview=asset` 标记时返回嵌入字节，版本 hash 包含两个文件；
- 不预留 `/favicon.ico`，保持“内部 URL 必须带标记、真实文件优先”的规则。

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 101 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=303 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=361 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | ok |
| 文档链接 | `node tests/check-doc-links.mjs` | ok |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

新增断言：

- 顶栏 logo 在导航按钮左侧、链接到 `/`、`src` 带 `__mdview=asset`；
- 页面有 SVG 与 PNG 两条 `rel="icon"`；
- 两个 favicon 资产返回 200 且 MIME 分别为 `image/svg+xml` / `image/png`；
- 无 JS 时 logo 仍在；
- 服务端单测覆盖两条资产路由与 HTML 链接。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-100 | 顶栏 logo | 1440×900 打开手册 | 最左 logo、导航次之、标题居中 | 通过 | [`../evidence/2026-11-11/logo-topbar-crop.png`](../evidence/2026-11-11/logo-topbar-crop.png) |
| F-100 | 整页 | 同上 | 顶栏、主岛、TOC 布局不受影响 | 通过 | [`../evidence/2026-11-11/logo-topbar.png`](../evidence/2026-11-11/logo-topbar.png) |
| 标记 | 256×256 预览 | 渲染 `assets/favicon.svg` | 蓝色圆角方块 + 白色 M | 通过 | [`../evidence/2026-11-11/logo-mark.png`](../evidence/2026-11-11/logo-mark.png) |
| 接口 | curl 两条资产 URL | 带 `__mdview=asset` | 200 + 正确 MIME + immutable | 通过 | 报告内断言 |
| 无 JS | 禁用页面脚本 | 文档页 | logo 仍在，导航隐藏 | 通过 | 探针 |

## 发现

- 浏览器标签页图标无法在 headless 的页面截图里看到，只能断言 `<link>` 与资产响应；
- 旧的 `.brand-mark` 是 CSS 字母方块，现改为 24×24 图片容器，样式收窄；
- 不支持 SVG favicon 的浏览器回退到 32×32 PNG；
- 不访问 `/favicon.ico`；如果根目录真有该文件，仍按普通文件路径返回。

## 覆盖缺口

- 未在 Safari/Firefox 实机看标签页图标；只验证了 Chrome 与 PNG 兜底资源。
- 未测 16×16 下的视觉清晰度（PNG 为 32×32，浏览器会缩小）；标记的折线在 32px
  内已按 3px 描边设计。
- favicon 的 `v=` 版本只通过 HTML 与资产断言覆盖，未做缓存过期测试。

## 结论

通过。顶栏左侧有可点击的首页 logo，文件名仍居中；favicon 通过带标记的嵌入资产
提供 SVG 与 PNG 两种格式，运行时仍无外部请求。ADR 0037、F-100、AGENTS 与夹具
已同步。
