# ADR 0038：资源按需加载与文本压缩

- Status: accepted
- Date: 2026-11-11

## 背景

Lighthouse（手册页/目录页）暴露了三个资源问题：

- 1.09 MB 的 highlight.js 在所有页面加载，目录页和无代码文档也下载；
- HTML/CSS/JS 没有压缩，手册页总传输 2.5 MB；
- `app.css` 里仍有旧侧栏/三列外壳的死规则，vendor CSS 未 minify。

这些问题不影响功能，但让目录页在模拟移动网络下 TTI 到 7.5s、手册移动性能只有 75。

## 决定

### 1. highlight.js 按需加载

- 源码页（`PageKind::Source`）始终加载 `highlight.js` 与 `highlight.css`；
- Markdown 页只在服务端渲染结果含 `<pre>` 时加载；
- 目录、搜索、信任/错误页、无代码文档不加载；
- 判断基于渲染后的 body（同时覆盖 fenced code 与裸 HTML `<pre>`），不依赖文件扩展名。

### 2. gzip / brotli

- 引入 `tower-http` 的 `CompressionLayer`（gzip + br），对主 origin 与 HTML 第二
  origin 的文本响应生效；
- 二进制图片/压缩包不压缩；响应带 `Vary: accept-encoding`；
- 保持 `Content-Disposition` 下载内容可被浏览器正确解码。

### 3. vendor CSS 构建时 minify

- `web/build.mjs` 用 esbuild 把 `assets/markdown.css`、`assets/highlight.css`
  minify 到 `OUT_DIR`；
- 服务端仍以独立文件与独立路由提供，保持 ADR 0012 的边界；
- `MDVIEW_WEB_PREBUILT` 分支同步复制这两个产物。

### 4. 清理旧外壳 CSS

- 删除不再输出的 `.sidebar`/`.side-*`/`.scrim`/`.toc-col`/旧 `.searchbox` 等规则；
- 保留仍在使用的 `.shell`/`.main`/`.content-card` 基础与页面样式；
- 浏览器探针与截图回归覆盖目录、文档、搜索、源码、移动端。

### 5. meta description

- 页面补一条通用描述，满足 SEO 审计；不改变页面内容。

## 备选方案

- **服务端高亮**：违反“服务端不生成高亮 HTML”的既有约束（ADR 0005/0012）。
- **把三个 CSS 合并成一个**：与 ADR 0012“vendor CSS 保持独立”冲突，且会失去按页
  条件加载 highlight.css 的能力；本轮不做。
- **预压缩静态资产**：能进一步省 CPU，但动态 HTML 仍需运行时压缩；先用
  `tower-http` 统一处理，后续可再评估。
- **关闭高亮**：会改变阅读体验，不做。

## 后果

- 目录页总传输 1,233 KiB → 41 KiB，移动性能 99 → 100；
- 手册页移动 LCP 13.2s → 8.5s，桌面 89 → 95，SEO 91 → 100；
- 无代码文档不再下载 1 MB 高亮包；
- 文本响应压缩、二进制不压缩，`Vary` 正确；
- 三个 CSS 请求仍保留（其中 highlight.css 条件加载），render-blocking 由 680ms
  降到 220ms；
- 图片（17 张截图）与 bfcache（`no-store`）仍是 B 组取舍，不在本决策内；
- 新增黑盒/浏览器/单元断言，Lighthouse 前后数据记入
  `docs/testing/reports/test-report-2026-11-11-performance.md`。
