# Markdown 扩展名口径：`.md`/`.markdown` 渲染，`.mdx` 源码

**Status**: accepted（2026-10-21）

旧 Python 实现只把 `.md` 当 Markdown（`MD_EXT = ".md"`，注释写明“只有 .md 被
特殊处理”）；Rust 实现的导航和语言标签却把 `.md`/`.markdown`/`.mdx` 都标成
文档/Markdown，而渲染与正文搜索只认 `.md`。需要明确“什么算 Markdown 文档”。

## 决定

1. **Markdown 文档**是扩展名 `.md` 或 `.markdown`（大小写不敏感）的文件。二者
   渲染为文档页，并进入搜索结果的内容扫描（`Doc` 分组）。
2. **`.mdx` 不是 Markdown 文档**：它含 JSX/导入语义，不按 comrak 渲染；保持
   源码查看页，正文搜索仍按文本扫描（`Text` 分组）。
3. 导航、图标、语言标签与搜索分组按以上口径统一：
   - `.md`/`.markdown` → 文档/Markdown；
   - `.mdx` → 源码/MDX（高亮可继续用 markdown 语法，但标签不能写“文档”）。
4. `.md?raw=1` 与 `.markdown?raw=1` 都是源码页；`.mdx` 默认就是源码页。
5. 扩展名大小写不敏感（`.MD`、`.Markdown` 同）。

## 考虑过的替代方案

- **三种都渲染**：实现最简单，但 MDX 的 JSX 会被当作裸 HTML 透传或显示为空，
  语义不完整；否决。
- **只渲染 `.md`**：维持旧 Python 契约，但 `.markdown` 是标准 Markdown 扩展名，
  用户会认为它是文档，导航也已经把它标成文档；否决。
- **只改标签、不渲染 `.markdown`**：内部一致但违背用户预期；否决。

## 后果

- `.markdown` 从源码页变为渲染页；搜索从“只匹配文件名”变为 Doc 内容搜索。
- `.mdx` 的导航/标签从文档/Markdown 改为源码/MDX；高亮实现可继续复用
  Markdown 语法。
- 功能矩阵与测试需要新增 `.markdown` 渲染、`.mdx` 源码断言。
