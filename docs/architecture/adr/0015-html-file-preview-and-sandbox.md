# HTML 文件：Trust 门控的静态原文与未信任沙箱

**Status**: accepted（2026-10-21）。取代本 ADR 先前“默认沙箱外壳”的草案；
Markdown 裸 HTML 的 Trust/CSP 规则仍由 [ADR 0006](0006-html-trust-and-csp.md) 决定。

## 背景

Python 版把独立 `.html` 当静态文件：`text/html` 顶层返回，无 mdview 外壳、无 CSP、
无 Trust；脚本同源运行，链接、`localStorage`、下载都像普通网页。Rust 2.0 改成
源码页，后续草案又默认套沙箱外壳，偏离了“简单静态服务器 + Markdown/文本预览”的
定位。用户选择 Trust 门控：**已信任根恢复静态原文，未信任根保留沙箱作为安全兜底**。

## 决定

### 1. URL 与 Trust

| 场景 | URL | 行为 |
|---|---|---|
| trusted | `/x.html` | 原字节 `text/html` 顶层返回；无外壳、无 sandbox、无 CSP |
| trusted | `/x.html?view=1` | 同上，兼容旧链接 |
| trusted | `/x.html?raw=1` | mdview 源码页；tabs 可切回原文 |
| trusted | `/x.html?download=1` | 原字节下载 |
| untrusted | `/x.html` | mdview 外壳 + 沙箱 iframe；`预览 / 源码` tabs |
| untrusted | `/x.html?view=1` | 沙箱裸页 |
| untrusted | `/x.html?raw=1` | 源码页 |
| 任意 | `--safe` | 只给源码；不 raw、不 sandbox |

- 目录/导航点击 HTML：trusted 直接原文；untrusted 进外壳。
- 目录行给 HTML 一个源码图标（`?raw=1`）；搜索正文行到
  `?raw=1#L<n>`，文件标题到 `/x.html`。
- 源码页的“预览”tab：trusted 指回 `/x.html`（原文），untrusted 指回外壳。
- 编码不强制：原文按字节返回 `text/html`，由文档自己的 BOM/`meta charset` 决定；
  Python 的强制 UTF-8 不再沿用。

### 2. Trusted raw 的安全含义

- 顶层同源文档：脚本可 `fetch('/_nav')`、读搜索页与其他文件，`localStorage`、
  cookie、下载、链接顶层导航都正常。这就是 Python 版的行为，也是它接近 `file://`
  的原因。
- 只在根目录已信任时启用。未信任根**不提供 raw**，即使有 Markdown 的一次性令牌；
  令牌不扩展到 HTML raw。
- `--safe` 优先于 Trust：safe 下 HTML 始终只给源码。

### 3. Untrusted 沙箱（安全兜底）

`?view=1` 响应：

```text
Content-Type: text/html
Content-Security-Policy: sandbox allow-scripts allow-forms allow-modals allow-popups; frame-ancestors 'self'; object-src 'none'
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
Cache-Control: no-store
```

iframe 同时带 `sandbox="allow-scripts allow-forms allow-modals allow-popups"`，
没有 `allow-same-origin`，所以文档是 opaque origin：脚本可运行，但读不到 `/_nav`、
搜索、同源文件、localStorage 与父页面。`object-src 'none'` 阻止
`<object>`/`<embed>`；这两类请求也按 frame 导航处理，不能退化成无 CSP 原始字节。
外壳页只在 `PageKind::Html` 把 `frame-src` 放宽为 `'self'`。

未信任预览的已知限制：`target="_top"`/`_parent` 被拦，`target="_blank"` 的新标签
继承沙箱，下载默认被拦。它是安全兜底，不是可信文档的默认体验。

### 4. 子资源 MIME

HTML 预览要能加载相对 `style.css`/`app.js`。服务端按 `Sec-Fetch-Dest`
（退化时看 `Accept`）区分“导航”与“子资源”：

- `document`：保持现有源码页/外壳页；
- `style`/`script`/`empty`：按扩展名返回原始字节与真实 MIME；
- `iframe`/`frame`/`object`/`embed`：HTML 文件按 frame 导航处理（trusted 原文，
  untrusted 沙箱裸页）。

直接打开 `.css` 仍是源码页，只有被 HTML 预览当样式表取时才按 CSS 返回。
`--max-preview` 只限制文档，不限制子资源。

### 5. SVG

`image/svg+xml` 始终加
`Content-Security-Policy: sandbox allow-top-navigation-by-user-activation`，
与 Trust 无关。`<img>` 内嵌不受影响；直接打开 SVG 时脚本不执行。这是对 Python
行为的刻意安全偏差。

## 考虑过的替代方案

- **始终 raw（完全 Python）**：未信任根也执行同源脚本；否决。
- **始终沙箱外壳**：偏离“简单静态服务器”的定位；用户否决。
- **Trust 门控 raw**：采用。
- **独立 origin（第二监听端口）**：能同时获得 file-like 的 storage/下载与隔离；
  工程量与部署复杂度高，暂不做。
- **交给 `file://`**：http 页面不能可靠跳 `file://`；否决。

## 后果

- 可信文档恢复 Python/file-like 体验：脚本、localStorage、同源 fetch、下载、
  顶层链接都正常；没有 mdview 外壳。
- 未信任文档得到受限但可读的沙箱预览；源码始终可用。
- Trust 因此有真实含义：可信根的 HTML 能读整个站点的同源数据；只服务可信文档。
- 主题切换、iframe 固定高度等限制只影响未信任沙箱外壳，不影响 trusted 原文。
