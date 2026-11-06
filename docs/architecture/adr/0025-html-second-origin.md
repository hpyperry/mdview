# 未信任 HTML：第二 origin 静态镜像

**Status**: accepted（2026-11-06）。取代 [ADR 0015](0015-html-file-preview-and-sandbox.md)
里“未信任根 = mdview 外壳 + sandbox iframe”的默认路径；trusted 根的原文直出与
`--safe` 规则不变。裸 HTML 的 Trust/CSP 仍由
[ADR 0006](0006-html-trust-and-csp.md) 约束。

## 背景

ADR 0015 把未信任根的独立 `.html` 放进 `sandbox="allow-scripts …"` 的 iframe，
没有 `allow-same-origin`。这个选择把文档变成 opaque origin，于是：

- `localStorage` / `sessionStorage` 读取直接抛 `SecurityError`；
- `navigator.serviceWorker` 被禁用；
- `<script type="module">`、`fetch()` 与相对 JS/CSS 走 CORS，mdview 不返回
  `Access-Control-Allow-Origin`，模块脚本被拦；
- 外壳的“新标签页”指向 `?view=1`，仍然是同一个 sandbox，无法逃逸。

2026-11 的兼容性修复（PR #42）只改了子资源 MIME，没有引入沙箱；沙箱来自
ADR 0015，首次发布在 2.0.1。实际应用型 HTML（模块脚本、PWA、存储、同源 fetch）
在 sandbox 里无法运行，这不是兼容性补丁能解决的。

## 决定

### 1. 第二监听端口 = 独立 origin

- 主 origin 只负责 Markdown、源码页、搜索、导航与 Trust 拦截。
- 未信任根的 `/x.html` 返回 **302**，`Location` 指向
  `http://<当前请求 Host>:<HTML 端口>/x.html`。
- 第二 origin 是**只读静态镜像**：整个服务根按真实 MIME 返回，GET/HEAD；
  不挂 mdview 外壳、导航、搜索、`__mdview` 内部路由与内嵌资产。
- HTML 在第二 origin 以原文顶层运行；不同端口是不同 origin，因此
  `localStorage` / `sessionStorage` / Service Worker / module / 同源 fetch 都按正常
  站点工作，但读不到主 origin 的存储与接口。
- trusted 根不变：仍在主 origin 直接返回原文。`--safe` 只给源码，不启动第二
  origin。

### 2. 端口与失败行为

- 默认起点是**实际主端口 + 1**；冲突时顺延，最多 10 个候选端口（不受 `--port-tries`
  影响，那个选项只描述主监听）。
- `--html-port <PORT>` 覆盖起点；`0` 表示让操作系统分配。
- 第二 origin 全部端口都不可用时，未信任 HTML 回退到**源码页**并显示提示，
  不静默退回沙箱。
- 启动横幅打印 `html: http://<host>:<port>`，便于脚本与人工确认。

### 3. URL 与旧参数

- `?raw=1`：主 origin 源码页；“预览”tab 指向第二 origin（untrusted）或主
  origin 原文（trusted）。
- `?download=1`：主 origin 原字节下载。
- `?view=1`：不再有裸沙箱页语义，按普通 HTML 请求处理（302 到第二 origin），
  旧链接不会 404。
- 沙箱外壳页、iframe、`HTML_PREVIEW_CSP`、`?view=1` 裸页与相关 CSS 全部移除。

### 4. 压缩包

压缩包内 HTML 也走第二 origin：主 origin 302，第二 origin 复用同一份解压缓存
按虚拟路径返回原字节。压缩包根目录浏览仍只在主 origin 提供。

### 5. 安全边界

- 第二 origin 只读、只 GET/HEAD；路径仍走 `resolve_path` 的 canonicalize +
  `starts_with(root)`，损坏/越界路径返回纯文本 4xx。
- 目录请求返回 404，不提供第二套目录 UI；`/_nav`、`/search`、`/_assets/*`
  没有内部路由，只有真实同名文件才会命中。
- 不返回 mdview 的 nonce/CSP；只在 SVG 上保留
  `CSP: sandbox allow-top-navigation-by-user-activation`。
- 端口隔离不等于内容隔离：第二 origin 能读**整个服务根**（包括隐藏文件与
  `.git`），和普通静态服务器一致。不要在含机密的根里运行未信任 HTML，或使用
  `--safe`。
- 端口隔离不等于 cookie 隔离：cookie 按 domain 共享，第二 origin 的页面仍能
  带上主 origin 的 cookie。mdview 自身不设 cookie。
- 反向代理只转发了主端口时，第二端口不可达；需要单独暴露，或只在本地使用。
  HTTPS 终止在主 origin、第二 origin 仍是 HTTP 时，顶层跳转可用，但跨 origin
  的 fetch/module 可能受混合内容限制。

## 考虑过的替代方案

- **保留沙箱，只修新标签页**：storage/SW/module 仍然坏，等于没解决。
- **未信任根也在主 origin 直出原文**：最简单，但未信任 HTML 能读主 origin 的
  存储与接口，等于取消 Trust 门控。
- **默认只给源码，要运行必须 `--trust`**：安全，但应用型 HTML 仍然点开不能跑。
- **原生打开 `file://`**：Web 页面不能直接跳 `file://`；需要 mdview 调系统命令，
  只对运行 mdview 的机器有效，手机/局域网无效。
- **第二 origin（采用）**：同时得到可运行的静态站点与 origin 级隔离；代价是第二个
  端口、反向代理配置和按端口变化的存储。

## 后果

- 未信任根的 HTML 恢复静态服务器体验；模块、PWA、存储、同源 fetch、下载与顶层
  链接都能工作。
- 需要多一个监听端口；端口变化会让第二 origin 的 `localStorage` 重新开始。
- 反向代理/HTTPS 部署需要额外暴露第二端口，或接受只在本地使用。
- trusted 根的行为与 2.3.0 完全一致；Markdown、搜索、导航与编码规则不变。

## 验证

- Rust 单测：302 Location、Host 端口剥离、静态 MIME、目录 404、内部路由不可用、
  SVG CSP、压缩包条目、端口不可用回退源码页。
- `tests/selftest-rust.sh`：untrusted 302、第二 origin 原文/MIME/无 CSP、源码页
  预览链接、压缩包 HTML、`--html-port`、端口冲突回退。
- `tests/browser-probe.mjs`：module + sessionStorage + service worker + fetch +
  相对 CSS 在第二 origin 全部可用；主 origin 无 iframe/外壳。
- 人工复测：`tests/fixtures/html-second-origin/README.md`。
