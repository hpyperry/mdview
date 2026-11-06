# ADR 0027：四类页面共用服务端 PageHead 构建器

- Status: accepted
- Date: 2026-11-06

## 背景

Markdown、源码、目录、搜索四类页面的页头原先各写一套 Rust `format!` 模板：

- Markdown：`doc-head` + `article-toolbar`，元信息是一行纯文本，没有文件名标题；
- 源码：`page-head` + `h1` 文件名 + `source-tags` 徽标；
- 目录：`dir-head` + `h1` + 项目数；
- 搜索：`search-head` + `h1` + 结果数 + 表单。

同一类信息（类型、大小、编码、行数、更新时间、操作）在不同页面的位置、标签和
CSS 都不同。每次调整“上面那一块”都要改多处模板与样式，容易再次漂移。

## 决策

在 `src/server.rs` 中提供共享的 `PageHead` 构建器，以及 `PageMeta`、`PageAction`
两个小类型：

```html
<header class="page-head doc-head">
  <div class="head-inner page-head-inner">
    <div class="grow">
      <nav class="crumbs">…</nav>
      <h1>文件名 / 页面标题</h1>
      <div class="page-meta"><span class="badge">…</span></div>
    </div>
    <div class="page-actions">源码 / 下载 / 导出 / 预览</div>
  </div>
</header>
```

- 四类页面都调用 `PageHead::new(...)`，只通过 modifier 类保留
  `doc-head` / `source-head` / `dir-head` / `search-head`；
- 搜索表单走 `aside` 槽位，其余页面用 `page-actions`；
- CSS 只保留一套 `.page-head` / `.page-head-inner` / `.page-meta` /
  `.page-actions` 规则，modifier 类不再复制布局；
- Markdown 页头也显示文件名 H1；正文自己的 H1 仍是文档标题，不使用 `sr-only`
  副本；
- 信任页与错误页保留专用面板，不纳入 PageHead。

## 为什么不做成 Preact 组件

页头必须在无 JS 时仍然完整可读，而且 Markdown 正文、源码行号、搜索结果是服务端
权威 HTML。把页头搬进岛屿会让无 JS 页面丢掉标题、元信息与下载入口，也扩大首屏
水合的职责。PageHead 是**服务端模板构建器**，不是客户端组件；岛屿只接管页头里的
交互（导出、下载完成反馈）。

## 后果

- 改页头只改 `PageHead` 与一套 CSS；
- Markdown 页头新增文件名标题与徽标，和源码页视觉对齐；
- 打印样式统一隐藏 `.page-head`；
- 页头结构、徽标与操作由 Rust 单测和浏览器探针共同钉住；
- 新增页面类型若需要页头，优先复用 PageHead，再考虑 modifier 类。
