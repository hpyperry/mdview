# 旧浏览器 / 旧 Chromium 内核兼容性审计

**Status**: 审计完成（2026-11-04）。只读代码，未修改产品代码。
**审计快照**: HEAD `ab4d097`（PR #42，含 `fetch_kind` 旧子资源修复）。
**范围**: HTTP 内容协商、`web/src/` 语法与 Web API、CSS/HTML 特性、测试与构建产物。
**基线**: 审计时 [ADR 0022](../architecture/adr/0022-browser-baseline-chromium-86.md) 承诺
Chromium 86+；2026-11-04 已由 [ADR 0024](../architecture/adr/0024-browser-baseline-chromium-88.md)
提升到 **Chromium 88**（PR #47）。本文保留审计时的 86 表述作为历史语境。

## TL;DR

- **原问题已确认**：旧客户端不发 `Sec-Fetch-Dest`，classic script 只发 `Accept: */*`；
  `fetch_kind` 把它当导航，`docs.js` 走 `source_page` 返回 `text/html`，再加上
  `X-Content-Type-Options: nosniff`，Chromium 直接拒绝执行。`new OpenCollection()`
  的 “not a constructor” 是脚本没执行的连带错误，不是第二个根因。
- **修复已提交（`ab4d097`）**：`fetch_kind` 增加 `Sec-Fetch-Mode` 兜底，并对
  `Accept: */*` + 子资源扩展名（`js/mjs/cjs/css/json/map/webmanifest/xml`）判为
  `Subresource`；`raw_mime` 返回真实 MIME。旧发布产物需重新构建/发版才受益。
- **无 `Sec-Fetch-Dest` 本身就是线索**：Chrome 80 起发 `Sec-Fetch-Dest`，76 起发
  `Sec-Fetch-Mode`。真 Chrome/Chromium 在 80+ 还缺这两个头，更可能是 **<80 的内核**、
  中间代理/扩展剥离了请求头，或根本不是 Chromium（套壳/IE 内核）。
- **如果内核 <80，坏的不止 MIME**：`web/build.mjs` 的 esbuild target 是 `chrome86`，
  产物保留可选链/空值合并（Chrome 80），`app.js` 在 <80 会直接 `SyntaxError`；
  所有岛（主题/导航/搜索/TOC/代码/放大/导出）都不会水合。
- **86 基线仍有一个 CSS 漏检**：`contain-intrinsic-height` 需要 Chrome 95，
  `contain-intrinsic-width: none` 需要 98；`content-visibility: auto` 从 85 开始支持。
  因此在 Chrome 86–94 上，离屏源码分块没有 intrinsic 尺寸，滚动条/锚点可能跳变。
- **`:modal` 不是产品依赖**：产品只用 `dialog.showModal()`（Chrome 37+）；`:modal`
  只出现在 `tests/browser-probe.mjs:424`，Chrome 105 才支持，旧内核上会抛
  `SyntaxError`，导致旧内核无法直接复用该探针。
- **二进制子资源基本不受 MIME 分流影响**：图片/SVG/字体/PDF 走 `Kind::Binary`，
  即使被判成 `Navigation` 也仍由 `serve_file` 返回真实 MIME；真正受影响的是
  `Kind::Text` 的 JS/JSON/CSS/XML/manifest，以及 `--max-preview` 的下载判断。

## 落地状态（2026-11-04）

| 审计项 | 状态 |
|---|---|
| 旧客户端 JS/JSON MIME | 已修复：[PR #42](https://github.com/hpyperry/mdview/pull/42)（`ab4d097`） |
| `content-visibility` 的 intrinsic-size 门禁 | 已修复：[PR #44](https://github.com/hpyperry/mdview/pull/44) |
| `replaceChildren` 回退 | 已修复：[PR #44](https://github.com/hpyperry/mdview/pull/44) |
| `:modal` 探针兼容 | 已修复：[PR #44](https://github.com/hpyperry/mdview/pull/44) |
| `highlight.min.js` 构建 target | 已修复：[PR #47](https://github.com/hpyperry/mdview/pull/47)（`chrome88`） |
| 基线提升到 Chromium 88 | 已合并：[PR #47](https://github.com/hpyperry/mdview/pull/47) / ADR 0024 |
| 旧内核 `--headless` 探测 | 未做 |
| 旧引擎实测（Chromium 88） | 2026-11-04 通过 25/25，见[报告](../testing/reports/legacy-chromium-88-2026-11-04.md) |
| <86 视觉/API、`app.js` 语法、`.md` fetch 契约 | 未做，见 §7 / §9 |

## 分级汇总表

| 级别 | 问题 | 位置 | 最低 Chrome | 影响 | 严重度 | 现有测试 |
|---|---|---|---|---:|---|---|
| P0 | 旧客户端 JS/JSON MIME 误判（旧行为） | `src/server.rs:951`、`:3060`、`:698` | 80（无 Sec-Fetch 时） | 脚本被 `text/html` + nosniff 拒绝，页面初始化失败 | 致命 | `ab4d097` 新增单测/黑盒；旧版本无 |
| P0 | `Accept: */*` 直开 CSS/JS 不再是源码页 | `src/server.rs:996` | 任意 | 源码页契约改为依赖 `Accept: text/html` 或 `?raw=1` | 高（契约） | `selftest-rust.sh:287` 已改 |
| P1 | `Element.replaceChildren` 不存在 | `web/src/islands/source.ts:55` | 86 | 大源码分块不生成行锚点，`#L12000` 无法定位 | 中高 | 仅新 Chrome |
| P1 | `contain-intrinsic-*` 被整条丢弃 | `web/src/styles/app.css:408-410` | 95 / 98 | 86–94 上离屏分块按 0 尺寸布局，滚动/锚点跳变 | 中高 | 无 |
| P1 | `app.js` 语法下限 | `web/build.mjs:14`、`web/tsconfig.json:3` | 80 | <80 直接 `SyntaxError`，全部岛不工作 | 致命（<80） | 无 |
| P2 | `:modal` 测试断言 | `tests/browser-probe.mjs:424` | 105 | 旧内核探针抛异常；产品不受影响 | 中（测试） | 新 Chrome |
| P2 | flex `gap` 不支持 | `web/src/styles/app.css:111` 等 | 84 | 78–83 上间距塌成 0，布局拥挤 | 中（视觉） | 无 |
| P2 | `:focus-visible` 不支持 | `web/src/styles/app.css:121` 等 | 86 | <86 键盘焦点环缺失 | 中（无障碍） | 无 |
| P2 | `scrollIntoView/scrollTo` options | `toc.tsx:47`、`totop.ts:12`、`source.ts:112` | 约 61 | 旧内核平滑/选项降级，滚动可能不生效 | 低中 | 无 |
| P3 | `color-scheme` / `backdrop-filter` | `app.css:9/70/564` | 81 / 76 | 深色表单控件、毛玻璃降级 | 低（视觉） | 无 |
| P3 | 导出 PNG 的字体/foreignObject | `web/src/islands/export.ts:85/141` | 35/50 起，效果未核实 | 旧内核可能导出失败或丢字体/图片 | 低中 | 仅新 Chrome |
| P3 | 无 Sec-Fetch 时 `.md/.txt/.html` fetch 仍走导航；大二进制子资源可能被 `--max-preview` 判下载 | `src/server.rs:932-1006`、`:716-722` | — | 旧客户端拿不到原字节；图片/字体/PDF 带 `Content-Disposition` | 低中 | 无 |

## 1. HTTP 内容协商

### 1.1 原故障链路（`ab4d097` 前）

`handle_file` 先算 `fetch_kind(headers)`（`src/server.rs:698`、`:951`）。原实现顺序是：

1. 有 `Sec-Fetch-Dest`：`document` → 导航，`iframe/frame/object/embed` → 帧导航，
   其余 → 子资源；
2. 没有 `Sec-Fetch-Dest` 时看 `Accept`：含 `text/html`/`application/xhtml+xml` →
   导航；含 `text/css`/`text/javascript`/`application/javascript`/`application/json`
   → 子资源；
3. 其余一律 `Navigation`。

旧 Chrome 的 classic `<script src="docs.js">` 发 `Accept: */*`，没有
`Sec-Fetch-*`，于是命中第 3 条。`classify` 把 `.js` 归为 `Kind::Text`
（`src/server.rs:2871`，`TEXT_EXT` 含 `js`），`handle_file` 走 `source_page`，
返回外壳 HTML，`Content-Type: text/html; charset=utf-8`，且 `stream_file` 带
`X-Content-Type-Options: nosniff`（`src/server.rs:2558`）。Chromium 的 MIME 检查
因此拒绝执行；`nosniff` 不是 bug，移除它只会把“拒绝”变成“按 HTML 解析”，仍然错。

### 1.2 修复后的判定

`ab4d097` 新增（`src/server.rs:932-1006`）：

- 有 `Sec-Fetch-Dest`：语义不变；
- 否则有 `Sec-Fetch-Mode`：`navigate` → 导航，其余 → 子资源；
- 否则看 `Accept`：含 `text/html`/`xhtml` → 导航；含 CSS/JS/JSON → 子资源；
- 否则若 `Accept` 是 `*/*` 或空，且扩展名在
  `LEGACY_SUBRESOURCE_EXTENSIONS = js/mjs/cjs/css/json/map/webmanifest/xml` 中 →
  子资源；
- 其余 → 导航（`.md`/`.txt`/`.html` 故意不纳入）。

`raw_mime`（`src/server.rs:3060`）对上述扩展返回：
`text/javascript; charset=utf-8`、`text/css; charset=utf-8`、
`application/json; charset=utf-8`、`application/manifest+json; charset=utf-8`、
`application/xml; charset=utf-8`。`apply_charset` 会保留检测到的非 UTF-8 charset。

### 1.3 请求形态矩阵

| 请求 | 旧内核请求头（无 Sec-Fetch） | 旧行为 | 修复后结果 | 说明 |
|---|---|---|---|---|
| 顶层导航 `/a.md` | `Accept: text/html,...` | 导航 | 导航 | 正确 |
| `<script src=docs.js>` | `Accept: */*` | 导航 → `text/html` | 子资源 → `text/javascript` | 本次故障 |
| `<link rel=stylesheet>` | `Accept: text/css,*/*;q=0.1` | 子资源 | 子资源 | 原实现已覆盖 |
| `fetch('data.json')` | `Accept: */*` | 导航 → 源码页 | 子资源 → `application/json` | 同故障 |
| `<link rel=manifest>` | `Accept: */*` | 导航 → 源码页 | 子资源 → `application/manifest+json` | 同故障 |
| `<img src=pic.png>` | `Accept: image/...` | 导航，但 `Kind::Binary` | 导航，但 `Kind::Binary` | 仍返回 `image/png` |
| `@font-face` woff2 | `Accept: */*` | 导航，但 `Kind::Binary` | 同左 | 仍返回字体 MIME |
| `<iframe src=page.html>`（未信任） | `Accept: text/html,...` | 导航 → 外壳 | 导航 → 外壳 | `?view=1` 才是沙箱裸页 |
| `<object data=page.html>`（未信任） | `Accept` 含 `text/html` 或 `*/*` | 导航 → 外壳 | 导航 → 外壳 | `.html` 不在扩展名白名单 |
| `fetch('README.md')` | `Accept: */*` | 导航 → 源码页 | 导航 → 源码页 | 旧客户端拿不到 raw Markdown |
| `fetch('notes.txt')` | `Accept: */*` | 导航 → 源码页 | 导航 → 源码页 | 同上 |
| `fetch('x.html')`（未信任） | `Accept: */*` | 导航 → 外壳 | 导航 → 外壳 | 不是 raw HTML |
| `.wasm` / `.pdf` fetch | `Accept: */*` | 导航，但 `Kind::Binary` | 同左 | 真实 MIME 仍返回 |
| 压缩包内 `docs.js` | 同普通文件 | 旧行为 | 修复生效 | `handle_archive` 复用 `handle_file` |
| `?download=1` | 任意 | 下载优先 | 下载优先 | `handle_file:710-718` 先判 explicit download |
| 超过 `--max-preview` 的图片/字体 | 无 Sec-Fetch | 导航 → 可能 `Content-Disposition` | 同左 | 大二进制子资源仍可能被当文档下载 |

### 1.4 取舍与剩余风险

- **源码页契约变了**：`curl` 默认发 `Accept: */*`，现在直接访问 `.css`/`.js`/`.json`
  会拿到 raw 字节，而不是 `<h1>style.css</h1>` 源码页。普通浏览器地址栏/链接导航发
  `text/html`，所以用户正常点击不受影响；脚本/API 客户端需要显式
  `Accept: text/html` 或访问 `?raw=1`。`tests/selftest-rust.sh:287` 和
  `:448-449` 已为此改成 `Accept: text/html`。
- **`.md`/`.txt` 被排除是刻意取舍**：它们在浏览器里是文档，不能因为 `Accept: */*`
  就把源码页变成 raw。代价是旧客户端的 `fetch('README.md')` 拿不到原始 Markdown；
  这需要产品明确契约，或引入 `Referer`/`Sec-Fetch-Site` 等更强信号。
- **大二进制子资源**仍会被 `--max-preview` 判为下载（`src/server.rs:716-722`），
  因为 `fetch_kind` 对图片/字体返回导航。Chromium 通常忽略子资源响应上的
  `Content-Disposition`，但旧内核/嵌入浏览器是否如此需要实测。
- **`Sec-Fetch-Mode` 无 Dest 的 76–79**：`iframe/object` 也发 `navigate`，会被判成
  导航而不是 `Iframe`。未信任 HTML 的 `<object>` 因此可能拿到外壳页而不是沙箱裸页；
  外壳页仍带自己的 CSP，未发现直接逃逸，但语义不再精确。
- **`Referer` 没有参与判定**：如果有 `Referer` 且同源，可以更可靠地区分“页面内
  子资源”和“直接导航”。当前实现没有用，属于可改进项，不是缺陷。

## 2. 前端语法与 API

`web/build.mjs:14` 的 `target: ['chrome86']` 只保证“语法”按 Chrome 86 降级，
**不降 API**。`web/tsconfig.json:3` 的 `target: ES2020` 只影响类型检查，不产出代码。

### 2.1 语法下限

- 产物保留可选链 `?.` 和空值合并 `??`（Chrome 80 支持，esbuild 不会降到 80 以下）。
  审计时本机构建产物 `web/dist/app.js` 可见 24 个 `?.`、5 个 `??`。
- 因此 **Chrome <80 会在解析 `app.js` 时直接失败**，不是“某个功能不可用”，而是
  所有 island 都不水合。页面仍有服务端 HTML，但主题/导航/搜索/TOC/代码条/放大/导出
  全部失效。
- 未使用：逻辑赋值、类字段/私有字段、顶层 await、`Array.at`、`Object.hasOwn`、
  `structuredClone`、`replaceAll`、`Promise.any/allSettled`、`queueMicrotask`、
  `AbortSignal.timeout`、`crypto.randomUUID`、`WeakRef`、`Intl.*`、`ResizeObserver`、
  `history.replaceState`。esbuild 也覆盖不到 vendored 资产（见 5.2）。Preact 10.29.8
  未发现这些运行时 API，但它依赖 `Map`/`Set`/`Symbol`/`Promise`（Chrome 38+）。

### 2.2 API 清单

| API | 最低 Chrome | 使用位置 | 无此 API 时的表现 |
|---|---:|---|---|
| `Element.closest` | 41 | 多个 island | 点击/导航直接抛错 |
| `fetch` | 42 | `nav.tsx:260/306` | 导航加载失败 |
| `URLSearchParams` | 49 | `nav.tsx:260/306`、`search.ts:71` | 导航/搜索参数构造失败 |
| `IntersectionObserver` | 51 | `app.ts:34/38`、`code.tsx:69` | **有回退**：直接 run / 高亮 |
| `requestIdleCallback` | 47 | `app.ts:47`、`nav.tsx:332` | **有回退**：`setTimeout` |
| `CSS.escape` | 46 | `toc.tsx:192/205` | TOC 查询选择器抛错；当前 id 是 `toc-N`，暂不触发 |
| `document.fonts.ready` | 35 | `export.ts:85` | 未 guard；导出 PNG 失败 |
| `canvas.toBlob` | 50 | `export.ts:141` | 未 guard；导出 PNG 失败 |
| `URL.createObjectURL` | 19 | `export.ts:74` | 导出失败 |
| `a.download` | 14 | `export.ts:77` | 导出可能变成导航 |
| `navigator.clipboard` | 66 | `utils.ts:18` | **有回退**：`execCommand('copy')` |
| `HTMLDialogElement.showModal` | 37 | `zoom.tsx:51` | 无回退；放大功能失效 |
| `Element.replaceChildren` | 86 | `source.ts:55` | **无回退**；大源码行锚点不生成 |
| `scrollIntoView({behavior,block})` | 约 61 | `toc.tsx:47`、`source.ts:112`、`linetarget.ts:64` | 旧内核可能忽略平滑/选项 |
| `window.scrollTo({top,behavior})` | 约 61 | `totop.ts:12` | 旧内核可能不滚动 |
| `MediaQueryList.addEventListener` | 39 | `toc.tsx:214` | <39 无 change 监听；实际下限已被 80 覆盖 |
| `localStorage` / `matchMedia` | 4 / 9 | `utils.ts`、`nav.tsx` | 已 try/catch；极老内核才会缺 |
| `PointerEvent`/`pointerenter` | 55 | `nav.tsx` 悬停预热 | 只是少了预热 |

结论：**Chrome 80–84 语法能过，但 flex `gap`（84）、`content-visibility`（85）、
`replaceChildren`/`:focus-visible`（86）会依次缺失；Chrome 95 才补上源码分块的
intrinsic 尺寸。**

## 3. CSS / HTML

`tests/check-css-baseline.mjs:21-45` 的黑名单覆盖了 `light-dark()`、`color-mix()`、
`inset`、`:is/:where/:has`、`@container`、`dvh`、`text-wrap`、`scrollbar-gutter`、
`subgrid`、`overflow: clip`、`accent-color`、`text-underline-offset`、CSS 嵌套。
它**没有覆盖**下面这些实际在用的特性：

| 特性 | 最低 Chrome | 位置 | 低于最低版本的表现 | lint 覆盖 |
|---|---:|---|---|---|
| `content-visibility: auto` | 85 | `app.css:408` | 整条忽略，所有分块完整渲染（性能降级，内容仍可读） | 否 |
| `contain-intrinsic-width: none` | 98 | `app.css:409` | 声明丢弃，离屏分块宽度回退不确定 | 否 |
| `contain-intrinsic-height` | 95 | `app.css:410` | 声明丢弃，离屏分块按 0 高度布局 | 否 |
| flex `gap` | 84 | `app.css:111` 等大量 | 间距变 0，顶栏/导航/按钮挤在一起 | 否 |
| `:focus-visible` | 86 | `app.css:121` 等 | 键盘焦点环不出现 | 否 |
| `color-scheme` | 81 | `app.css:9/70/89` | 深色下表单控件/滚动条仍是浅色 | 否 |
| `backdrop-filter` | 76 | `app.css:564` | 顶栏只剩半透明背景，没有毛玻璃 | 否 |
| `overflow-wrap: anywhere` | 80 | `app.css:232/387/455` | 超长路径可能撑破列 | 否 |
| `min()` | 79 | `assets/markdown.css:206` | 工具提示 `max-height` 失效 | 否 |
| `dialog` / `::backdrop` | 37 | `zoom.tsx:63`、`app.css:497` | 元素按普通块显示，`showModal`/遮罩不生效 | 否 |

**最重要的漏检是 `contain-intrinsic-*`**：`content-visibility: auto` 本身在 86 上可用，
但离屏元素会启用 size containment；没有 intrinsic fallback 时，浏览器把跳过内容的
尺寸当作 0。大源码页（>256 KB）在 Chrome 86–94 上可能出现滚动条长度变化、滚动位置
跳变、`#L12000` 定位偏移。`content-visibility` 在打印媒体查询里被改回 `visible`
（`app.css:999`），所以打印不受影响；屏幕上的阅读体验需要真机确认。

HTML 侧没有发现旧内核专属的标签问题：`<dialog>` 37+、`<iframe sandbox>` 很早、
`referrerpolicy` 21+、`target=_blank rel=noopener` 都是旧内核可解析的。真正的问题是
上面这些 CSS 声明被静默丢弃——与 ADR 0022 记录的 `light-dark()` 事故同一类。

## 4. 已确认会坏 / 可能坏 / 需实测

**已确认会坏：**

1. **旧客户端 JS/JSON MIME（旧行为）**：已用 curl 复现，根因和链路见 1.1。
   `ab4d097` 修复后该路径恢复；旧发布产物仍坏，需要重新构建/发版。
2. **`Element.replaceChildren`（<86）**：`source.ts:55` 无特性检测。`mountSource`
   在初始化时对可见分块调用 `ensureGutter`，直接抛 `TypeError`，island 被标记失败；
   后续滚动也不会补行号。服务端仍输出完整源码，但 `#L<n>` 行锚点消失。
3. **`:modal` 测试（<105）**：`browser-probe.mjs:424` 对 `dialog` 调
   `matches(':modal')`。Chrome 105 才支持该伪类，旧内核会抛 `SyntaxError`（未知
   伪类），不是返回 `false`。产品没有使用 `:modal`，所以这是测试兼容问题，不是产品
   功能问题；但“旧内核跑同一套探针”会被这一条直接打断。
4. **`app.js` 语法（<80）**：见 2.1。若现场内核是 Chromium 78/79，控制台会先出现
   `SyntaxError`，MIME 错误只是用户最先注意到的那个。
5. **`contain-intrinsic-*`（86–94）**：声明确定被丢弃；滚动行为的严重程度需要真机，
   但“86 基线完全安全”这个结论不成立。

**可能坏 / 需实测：**

- **视觉/无障碍降级**：flex `gap`（<84）间距归零；`:focus-visible`（<86）无焦点环；
  `color-scheme`（<81）/`backdrop-filter`（<76）深色控件与毛玻璃降级。都不影响阅读。
- **`scrollIntoView/scrollTo` options（约 <61）**：TOC、回顶、源码行定位可能只做
  默认对齐或不滚动；锚点链接本身仍可用。需要旧内核实测。
- **导出 PNG（旧内核）**：`document.fonts.ready`、`canvas.toBlob`、SVG
  `foreignObject` + `drawImage` 的组合在旧 Chromium 上没有一手兼容表。可能在
  `foreignObject` 渲染、字体、跨源图片污染画布或大画布尺寸上失败；当前只有新 Chrome
  探针覆盖。
- **其余契约/边界项**：大二进制子资源 + `--max-preview`、`.md/.txt/.html` 的旧客户端
  fetch、`Sec-Fetch-Mode` 无 Dest 的帧语义，详见 1.4；均需真实请求样本或浏览器实测。
- **CSP 指令降级**：`script-src 'nonce-...'` 需要 Chrome 40+，`sandbox` 需要 25+，
  `frame-ancestors`/`form-action` 更晚；低于 80 时已被语法下限覆盖，但不要为了兼容
  旧内核放宽 nonce 或加 `'self'`/`'unsafe-inline'`。

## 5. 测试与构建的盲区

### 5.1 现有测试永远抓不到什么

| 测试 | 跑什么 | 抓不到 |
|---|---|---|
| `tests/browser-probe.mjs` | 本机最新 headless Chrome | 旧引擎的 CSS 静默丢弃、缺失 API、旧请求头；`:modal`/`contentVisibility` 断言还会反过来卡住旧内核 |
| `tests/check-css-baseline.mjs` | 只扫 CSS 文本 | JS API、`contain-intrinsic-*`、flex `gap`、`content-visibility` 配对、vendored JS 语法 |
| `tests/selftest-rust.sh` | curl 重放请求头 | 浏览器是否执行脚本、`nosniff` 的实际拦截、DOM/API 行为 |
| `cargo test` | `tower::oneshot`，默认无请求头 | 只覆盖新增的 `fetch_kind` 单测；旧请求形态的黑盒在 shell 套件里 |
| `tests/perf-source.mjs` | 最新 Chrome | 旧内核 `content-visibility` 无 intrinsic 时的滚动/性能 |
| `tests/smoke-artifact.sh` | 二进制/路由冒烟 | 任何浏览器行为 |

具体盲点：

- `browser-probe.mjs:146` 硬编码 `--headless=new`。Chromium 86/92 早于该模式，
  需要改成 `--headless`（或版本探测）才能启动；否则“指定 `CHROME=` 跑旧内核”
  第一步就失败。
- `browser-probe.mjs:424` 的 `:modal` 和 `:796` 的
  `getComputedStyle(...).contentVisibility === 'auto'` 都是 105/85+ 断言，旧内核
  必然失败；旧内核套件需要按 `CSS.supports`/`typeof` 特性检测跳过或替换。
- `check-css-baseline.mjs` 只维护“禁止列表”，发现不了“当前用了 95+ 的特性但基线
  是 86”这种漏项；`contain-intrinsic-*` 就是例子。
- **`assets/highlight.min.js` 没有 target**：`tools/build-assets/package.json:6` 的
  esbuild 命令没有 `--target=chrome86`。当前 bundle 已含 `?.`/`??`（最低约 Chrome
  80），未来重建可能引入更新的语法/API；它不是 `web/build.mjs` 的产物，target 管不到。
- `Emulation.setUserAgentOverride` 只改 `navigator.userAgent`，**不改变引擎**；
  旧内核也没有自动化；`tests/fixtures/chromium-baseline/README.md` 明确写了
  “浏览器探针跑最新 headless Chrome，不支持回退模拟”。

### 5.2 构建与产物

- `Cargo.toml` 没有浏览器版本约束；`build.rs` 只要求 Node/npm 和 `web/node_modules`，
  把 `app.js`/`app.css` 嵌入二进制。
- `web/package.json` 固定 esbuild `0.25.12`、Preact `10.29.8`；没有 browserslist。
  唯一约束是 `web/build.mjs:14` 的 `chrome86`；`tsconfig` 的 `target/lib` 只服务
  `tsc --noEmit`，不是运行时下限。
- `tests/run-all.sh:20-35` 依次跑 `cargo test`、CSS lint、黑盒、浏览器探针、性能；
  没有旧引擎任务。单文件产物本身没有随浏览器变化的逻辑。

## 6. 如何验证旧内核

### 6.1 请求头重放（最快，验证服务端）

```bash
cargo build --release
./target/release/mdview \
  --root tests/fixtures/legacy-subresource-mime \
  --trust --port 8003 --port-tries 0
```

另开终端：

```bash
# 旧客户端 classic script：应返回 text/javascript + 原始 JS
curl -sS -D - -o /dev/null -H 'Accept: */*' http://127.0.0.1:8003/docs.js
curl -sS -H 'Accept: */*' http://127.0.0.1:8003/docs.js | head -c 80

# JSON / CSS / 直接导航 / 现代浏览器形态
curl -sS -D - -o /dev/null -H 'Accept: */*' http://127.0.0.1:8003/data.json
curl -sS -D - -o /dev/null -H 'Accept: */*' http://127.0.0.1:8003/style.css
curl -sS -H 'Accept: text/html,application/xhtml+xml' http://127.0.0.1:8003/docs.js | head -c 120
curl -sS -D - -o /dev/null -H 'Sec-Fetch-Dest: script' http://127.0.0.1:8003/docs.js
```

注意：`curl` 默认就发 `Accept: */*`，所以“直接访问 `.css` 是源码页”现在必须显式加
`Accept: text/html`；`?raw=1` 仍可用。旧客户端的 `Referer` 不影响判定。

### 6.2 旧 Chromium 真机/快照

- **首选**：在目标环境（统信 UOS + 360 信创版/UOS 内置浏览器）打开
  `tests/fixtures/chromium-baseline/probe.html` 与
  `tests/fixtures/legacy-subresource-mime/legacy.html`，用 `chrome://version` 看
  实际内核版本（不要只看 UA）。
- **Chromium 快照**：官方 bucket 提供按 revision 的 Mac/Linux 构建，例如
  `https://commondatastorage.googleapis.com/chromium-browser-snapshots/Mac/` 与
  `.../Linux_x64/` 的目录列表；进入某个 revision 后取 `chrome-mac.zip` /
  `chrome-linux.zip`。具体 revision 请从目录或 Chromium Dash 选取，本文不编造
  固定 revision。macOS arm64 上旧 x64 构建通常走 Rosetta。
- **Playwright**：在仓库外临时目录安装 Playwright 后，用 `executablePath` 指向
  已下载的旧 Chromium；不要用 `channel` 或 UA 覆盖代替引擎：

  ```js
  const browser = await chromium.launch({
    executablePath: process.env.OLD_CHROME,
    headless: true,
    args: ['--no-sandbox'],
  });
  ```

- **复用现有探针**：`CHROME=/path/to/old/Chromium node tests/browser-probe.mjs`。
  但因为 `--headless=new`、`:modal`、`contentVisibility` 三处会挡住旧内核，建议在
  临时副本里改成 `--headless` 并加特性检测，不要直接改仓库测试。
- **API 自检**：在旧内核 DevTools Console 里执行：

  ```js
  typeof Element.prototype.replaceChildren
  typeof HTMLDialogElement.prototype.showModal
  CSS.supports('content-visibility', 'auto')
  CSS.supports('contain-intrinsic-height', '100px')
  CSS.supports('gap', '1px')
  document.querySelector('dialog')?.matches(':modal') // <105 可能抛异常
  ```

- **CDP 限制**：`Emulation.setUserAgentOverride` 只改 UA；要模拟旧请求头，用
  `Fetch.enable` + `Fetch.continueRequest` 改/删 `Sec-Fetch-*`，或直接用 curl。
  `Network.setExtraHTTPHeaders` 只能加头，不能删浏览器自动发的头。

## 7. 修复优先级

| 优先级 | 动作 | 理由 |
|---|---|---|
| P0 | 重新构建/发版已提交的 `fetch_kind` 修复，并保留 `fetch_kind_*` 单测与 `selftest-rust.sh` 旧请求头断言 | 旧产物仍会让 trusted HTML 的 JS/JSON 不可用 |
| P0 | 确认 `*/*` 直开源码页契约：文档/测试统一用 `Accept: text/html` 或 `?raw=1` | `ab4d097` 已改测试与 AGENTS；不要留下“curl 直开 CSS 是源码页”的旧承诺 |
| P1 | 给 `source.ts` 的 `replaceChildren` 加回退（`textContent=''` + `appendChild`），并验证 <86 的行锚点 | 大源码页在 78–85 上丢行号 |
| P1 | 处理 `contain-intrinsic-*`：用 `@supports` 门禁回退（已完成 #44），在 88/92 上验滚动 | 88–97 仍需要回退，基线提升到 88 不等于可用 |
| P2 | 给 `:modal`/`contentVisibility` 探针加特性检测，参数化 `--headless` | 让旧内核可以真正跑回归 |
| P2 | 给 `tools/build-assets` 加 `--target=chrome86`，并加一个 vendored JS 语法检查 | 防止 highlight.js 重建后把语法下限抬高 |
| P3 | flex `gap`、`:focus-visible`、`color-scheme`、`backdrop-filter` 逐项评估 | 主要是视觉/无障碍降级，可排期 |
| P3 | 给 `scrollIntoView/scrollTo` 加旧内核回退；给导出 PNG 的 `document.fonts`/`toBlob` 加 guard | 低风险、低成本 |
| P3 | 明确 `.md/.txt/.html` 的旧客户端 fetch 契约；评估 `Referer`/`Sec-Fetch-Site`；评估大二进制子资源的 `--max-preview` 行为 | 避免隐性差异；图片/字体大概率被忽略 `Content-Disposition`，但要实测 |

## 8. 建议的回归测试

| 测试 | 断言 |
|---|---|
| `cargo test fetch_kind_*` | 覆盖 `Accept: */*`、无 `Accept`、`Sec-Fetch-Mode`、`Sec-Fetch-Dest`、`.md/.txt` 不误判、大小写扩展名 |
| `tests/selftest-rust.sh` | 旧请求头下 `docs.js`/`data.json` 的 MIME 与原始字节；`Accept: text/html` 直开仍是源码页；压缩包内同名条目 |
| `tests/browser-probe.mjs` | 新 Chrome 保持现有 261 项；新增 `fetch_kind` 的端到端 HTML 夹具（现代头） |
| 旧内核套件（人工/可选） | `probe.html` + `legacy.html` + 大源码 `#L12000` + TOC/回顶 + 放大 + 导出；对 `:modal`/`content-visibility` 做特性检测 |
| CSS lint | 给 `contain-intrinsic-*` 加最低版本条目；对 `content-visibility` 要求配套 fallback |
| JS 资产 lint | 对 `assets/highlight.min.js` 和 `app.js` 做语法检查（esbuild `--target` 解析或 `es-check`） |
| 请求头重放脚本 | 固定一组 header 组合，比较 `Content-Type`/`Content-Disposition`/body 前 80 字节 |

## 9. 未验证 / 开放问题

- **旧引擎实测覆盖**：2026-11-04 已在 Chromium 88（snapshot 815036，Docker/qemu）上跑通
  25 项 CDP 断言，覆盖旧请求头 MIME、`content-visibility` 回退、导出 PNG、主题/导航/
  TOC/放大/搜索；详见[报告](../testing/reports/legacy-chromium-88-2026-11-04.md)。
  **精确 86 仍未验证**（M86 快照 revision 取不到），<86 不在支持范围。
- **用户实际浏览器版本未知**：`Sec-Fetch-Dest` 缺失可能是 <80 内核、代理/扩展剥离、
  或非 Chromium 套壳。需要 `chrome://version` 或现场抓包确认。
- **`:modal` 在目标内核是否真的会抛**：按规范/BCD 是 <105 抛未知伪类；当前产品没有
  使用它，只有测试使用。若目标内核是 86/92，`browser-probe` 会因此失败；已在探针里
  加 try/catch 跳过（#44）。
- **`contain-intrinsic-*` 在 Chrome 86/92 的滚动表现**：声明确定被丢弃，实际跳变
  幅度、是否影响 `#L<n>` 定位未在真机验证。
- **flex `gap` 在 78/86 的布局差异**：ADR 0022 当时明确 86+，现基线为 88（ADR 0024）；78 不在承诺范围，但仍
  可能出现在现场。
- **导出 PNG 的旧内核行为**：`foreignObject`、字体、图片内联、Canvas 尺寸/污染
  在旧 Chromium 上的表现未验证；当前只有新 Chrome 探针。
- **大二进制子资源的 `Content-Disposition`**：旧内核是否忽略、是否触发下载未验证。
- **`Sec-Fetch-Mode` 无 Dest 的 76–79 请求样本**：没有真实抓包；当前只有单测。
- **CSP 在 <80 的降级与 360/UOS 的 IE 兼容模式**：nonce/sandbox 旧语义未逐项验证；
  若是 IE 内核，问题不再是 Chromium 版本，需要现场确认。不要因此放宽 CSP。

## 10. 参考来源

- [ADR 0024：浏览器兼容基线 Chromium 88](../architecture/adr/0024-browser-baseline-chromium-88.md)
- [ADR 0022：浏览器兼容基线 Chromium 86（历史）](../architecture/adr/0022-browser-baseline-chromium-86.md)
- [Chromium 基线复测文档](../../tests/fixtures/chromium-baseline/README.md)
- [MDN：`Sec-Fetch-Dest`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest)
- [MDN：`:modal`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:modal)
- [MDN：`HTMLDialogElement.showModal()`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/showModal)
- [MDN：`Element.replaceChildren()`](https://developer.mozilla.org/en-US/docs/Web/API/Element/replaceChildren)
- [MDN：`contain-intrinsic-height`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/contain-intrinsic-height)
- [MDN：`content-visibility`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/content-visibility)
- [MDN：`gap`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/gap)
- [MDN：`:focus-visible`](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/:focus-visible)
- [MDN：`scrollIntoView()`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView)
