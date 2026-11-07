# ADR 索引

按编号顺序列出全部决策记录；状态以各文件顶部的 `Status` 为准。

| 编号 | 决策 | 状态 |
|---|---|---|
| [0001](0001-markdown-target-encoding.md) | markdown 目标路径的编码语义：以 VS Code 预览为准 | superseded by [0005](0005-vscode-1.142-as-oracle.md) |
| [0002](0002-image-zoom.md) | 图片放大：手写遮罩，不引入 lightbox | accepted |
| [0003](0003-data-uri-images.md) | data URI 图片：只对图片 src 放行 base64 | superseded by [0005](0005-vscode-1.142-as-oracle.md) |
| [0004](0004-rust-rewrite-and-dependencies.md) | Rust 原生重写：单文件可执行、成熟 crate、全平台 | accepted |
| [0005](0005-vscode-1.142-as-oracle.md) | VS Code 1.142 作为 Markdown 语义与视觉基准 | accepted |
| [0006](0006-html-trust-and-csp.md) | 裸 HTML、Trust 与 CSP | accepted |
| [0007](0007-hard-edge-cases-use-comrak.md) | 硬边角采用 comrak 行为 | accepted |
| [0008](0008-docs-shell-and-reading-typography.md) | 文档站外壳与阅读排版优先 | accepted |
| [0009](0009-search-scope-and-form-csp.md) | 搜索：同源表单、文本文件、文档优先 | accepted |
| [0010](0010-three-column-layout-and-sticky-shell.md) | 宽屏三列布局与 sticky 外壳 | superseded by [0012](0012-island-frontend-architecture.md) |
| [0011](0011-chunked-source-viewer.md) | 大文本源码页：全文分块 + content-visibility | accepted |
| [0012](0012-island-frontend-architecture.md) | 岛屿前端与内容主导的全宽外壳 | accepted |
| [0013](0013-full-site-navigation-island.md) | 全站导航浮岛：默认收起、空闲预取、只导航文件 | accepted |
| [0014](0014-markdown-line-target.md) | Markdown 搜索命中定位到渲染块 | accepted |
| [0015](0015-html-file-preview-and-sandbox.md) | HTML 文件：Trust 门控的静态原文与未信任沙箱 | superseded（未信任部分）by [0025](0025-html-second-origin.md) |
| [0016](0016-archive-virtual-paths.md) | 压缩包预览：虚拟包路径 + 临时解压缓存 | accepted；格式由 [0021](0021-archive-format-expansion.md) 扩展 |
| [0017](0017-internal-url-query-disambiguation.md) | 内部 URL 用查询参数消歧，真实文件优先 | accepted |
| [0018](0018-markdown-extension-scope.md) | Markdown 扩展名口径：`.md`/`.markdown` 渲染，`.mdx` 源码 | accepted |
| [0019](0019-file-encoding-detection.md) | 文件编码检测与 UTF-8 预览 | accepted |
| [0020](0020-nav-layered-preload.md) | 全站导航分层预载与按需展开 | accepted |
| [0021](0021-archive-format-expansion.md) | 压缩包格式扩展：tar 家族与 ZIP 容器 | accepted |
| [0022](0022-browser-baseline-chromium-86.md) | 浏览器兼容基线：Chromium 86 与静态色板 | superseded by [0024](0024-browser-baseline-chromium-88.md) |
| [0023](0023-dev-build-artifact-size.md) | 开发构建体积：`debug = 1` 与清理纪律 | accepted |
| [0024](0024-browser-baseline-chromium-88.md) | 浏览器兼容基线：Chromium 88 | accepted |
| [0025](0025-html-second-origin.md) | 未信任 HTML：第二 origin 静态镜像 | accepted |
| [0026](0026-toc-island-layout.md) | 右侧 TOC：常驻目录岛 + 折叠细轨 | accepted |
| [0027](0027-page-head-component.md) | 四类页面共用服务端 PageHead 构建器 | accepted |
| [0028](0028-full-width-shell-and-toc-split.md) | 内容岛铺满外壳；Markdown 分栏只收右边缘 | accepted |
| [0029](0029-fixed-island-inner-scroll.md) | 固定主岛：内容在岛内滚动 | accepted |
| [0030](0030-progressive-search-batches.md) | 搜索分批扫描与渐进追加 | accepted |
| [0031](0031-fixed-page-head-island.md) | 文档页头固定为独立页头岛 | superseded by [0032](0032-topbar-page-context.md) |
| [0032](0032-topbar-page-context.md) | 页面身份与操作迁入全局顶栏 | superseded by [0033](0033-clean-topbar-page-head.md) |
| [0033](0033-clean-topbar-page-head.md) | 顶栏只保留外壳控制，页面身份回到底部页头岛 | superseded（布局）by [0034](0034-topbar-title-gap-crumb-island-head.md) |
| [0034](0034-topbar-title-gap-crumb-island-head.md) | 顶栏文件名、缝隙面包屑与主岛功能区 | accepted |
