# 资源按需加载与压缩测试报告（2026-11-11）

- 关联：F-102；本地分支 `fix/wide-layout`（Issue / PR 待建）
- 夹具：`tests/fixtures/performance/README.md`（README-only，复用仓库根与 `docs/`）
- 类型：test（性能/后端/构建）+ 浏览器回归

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 分支 / commit | `fix/wide-layout`（本地提交，未推送） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 157.0.8103.39（headless） |
| Lighthouse | 13.6.0（npx，移动默认模拟节流 / `--preset=desktop`） |
| 被测根 | 仓库根（`/docs/README.md`、`/docs/manual/README.md`、`/`） |
| 端口 | 8321 |

## 改动

1. **按需加载 highlight.js**：源码页始终加载；Markdown 页只在服务端渲染结果含
   `<pre>` 时加载 `highlight.js` 与 `highlight.css`。目录/搜索/信任/无代码文档
   不再下载 1 MB 高亮包。
2. **gzip / brotli**：新增 `tower-http` 压缩层（gzip + br），只压缩文本响应；
   二进制图片/压缩包保持原样，响应带 `Vary: accept-encoding`。
3. **vendor CSS 构建时压缩**：`web/build.mjs` 用 esbuild 把 `assets/markdown.css`
   与 `assets/highlight.css` minify 到 `OUT_DIR`，服务端仍分文件提供。源文件与
   ADR 0012 的“保持独立”不变。
4. **清理旧外壳 CSS**：删除已不再输出的侧栏/三列/旧搜索框/toc-col 等规则，
   `app.css` 行数从 1591 降到约 1498。
5. **SEO**：补 `<meta name="description">`。

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 101 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=309 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=367 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | ok |
| 文档链接 | `node tests/check-doc-links.mjs` | ok |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

新增断言：

- 无代码文档/目录/搜索页不引用 `highlight.js`/`highlight.css`；源码页与含代码
  文档仍引用并高亮；
- `Accept-Encoding: gzip` 的 HTML 返回 `content-encoding: gzip` 与 `Vary`；
  CSS 请求 br 返回 `content-encoding: br`；
- PNG 不压缩；
- HTML 含 `meta description`。

## Lighthouse 前后对比

命令（每个页面）：

```bash
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  npx --yes lighthouse "<url>" --chrome-flags="--headless=new --no-sandbox --disable-gpu" \
  --output=json --output=html --output-path=/tmp/lh-<name> \
  --only-categories=performance,accessibility,best-practices,seo --quiet
```

| 页面 | 指标 | 改动前 | 改动后 |
|---|---|---|---|
| 手册页 移动 | 性能 / a11y / BP / SEO | 75 / 100 / 100 / 91 | **76 / 100 / 100 / 100** |
| 手册页 移动 | FCP / LCP / TBT / TTI | 1.5s / 13.2s / 61ms / 13.4s | **0.9s / 8.5s / 57ms / 8.7s** |
| 手册页 移动 | 总传输 | 2,563 KiB | **1,677 KiB** |
| 手册页 桌面 | 性能 / SEO | 89 / 91 | **95 / 100** |
| 手册页 桌面 | LCP / TTI | 2.3s / 2.3s | **1.53s / 1.57s** |
| 目录页 移动 | 性能 / SEO | 99 / 91 | **100 / 100** |
| 目录页 移动 | 总传输 / TTI | 1,233 KiB / 7.5s | **41 KiB / 0.9s** |
| 目录页 移动 | render-blocking / unused CSS / unused JS | 710ms / 49 KiB / 38 KiB | **270ms / 达标 / 达标** |

补充：

- `document-latency-insight` 从“节省 16–18 KiB”变为通过（gzip/br）。
- 手册页的 `unused-css` / `unused-javascript` 从 35 / 29 KiB 的提示变为达标
  （压缩后的传输量低于 Lighthouse 阈值；不是靠删代码达到的）。
- 手册页的 `image-delivery-insight` 仍提示 1.17 MB（17 张 PNG 截图），属于文档
  内容，不是应用 UI；目录页/短文档已经是满分。
- 手册页的 `bf-cache` 仍因 `Cache-Control: no-store` 失败，属于 B 组取舍，未在
  本轮修改。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-102 | 目录页不加载高亮 | 打开 `/` | 无 highlight.js；总传输约 40 KB | 通过 | [`../evidence/2026-11-11/performance-dir.png`](../evidence/2026-11-11/performance-dir.png) |
| F-102 | 无代码文档 | 打开 `/docs/README.md` | 无 highlight；正文正常 | 通过 | Lighthouse + 探针 |
| F-102 | 含代码文档 | 打开 `/docs/manual/README.md` | 高亮、TOC、布局不变 | 通过 | [`../evidence/2026-11-11/performance-doc.png`](../evidence/2026-11-11/performance-doc.png) |
| F-102 | 源码页 | 打开 `/docs/manual/README.md?raw=1` | 高亮与行号正常 | 通过 | [`../evidence/2026-11-11/performance-source.png`](../evidence/2026-11-11/performance-source.png) |
| F-102 | 搜索页 | `/search?__mdview=search&q=mdview` | 不加载 highlight；样式正常 | 通过 | [`../evidence/2026-11-11/performance-search.png`](../evidence/2026-11-11/performance-search.png) |
| F-102 | 移动端 | 390×844 手册页 | 单列、TOC 内联、logo 正常 | 通过 | [`../evidence/2026-11-11/performance-mobile.png`](../evidence/2026-11-11/performance-mobile.png) |
| F-102 | gzip/br | curl 见夹具 | 文本压缩、PNG 不压缩 | 通过 | 黑盒 PASS=309 |

## 发现

- 最大收益来自“目录页不再加载 1 MB highlight.js”：1,233 KiB → 41 KiB，性能 99 → 100。
- gzip/br 把手册页总传输从 2.5 MB 降到 1.7 MB（剩余的 1.2 MB 是 17 张截图），
  并把 `document-latency` 审计清零。
- 手册页移动端 LCP 13.2s → 8.5s：高亮包压缩后，首个代码块的重新着色提前；
  但移动性能仍受截图体积限制，所以分数只从 75 到 76。
- 桌面手册页 89 → 95；SEO 91 → 100。
- `valid-source-maps` 仍在含 highlight.js 的页面失败（未计分）；内嵌单文件工具
  不补 source map。
- 三个 CSS 请求仍在（app.css / markdown.css / highlight.css，后两个条件加载），
  这是 ADR 0012 “vendor CSS 保持独立”的取舍；压缩后 render-blocking 从 680ms
  降到 220ms。

## 覆盖缺口

- Lighthouse 是模拟 4G/CPU 节流；本地回环的实际数字更好，不能直接当真实网络 SLA。
- 未在真实 2G/4G、低端 Android 或 Safari 上复测。
- 没有直接删除或压缩手册的 17 张 PNG（B 组图片项）；该页仍是性能最低的页面。
- 仅验证了 gzip/br 的响应头与浏览器可正常加载，未做代理/CDN 缓存行为测试。

## 结论

通过。按需加载 highlight.js、gzip/br、vendor CSS 压缩与旧 CSS 清理均为行为不变
的优化：目录页从 1.2 MB 降到 41 KB、性能 100；手册桌面 95、SEO 100；高亮、TOC、
源码行号、移动端布局与所有 367 项浏览器断言保持一致。图片体积与 bfcache 留待
B 组取舍。
