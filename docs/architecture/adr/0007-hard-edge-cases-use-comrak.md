# 硬边角采用 comrak 行为：Linkify、引用定义、front matter、长尾

**Status**: accepted（2026-10-19）
**Partially supersedes**: [ADR 0005](0005-vscode-1.142-as-oracle.md) 的
linkify / reference definition / front matter / URL normalization / image alt 条目

P0 差分发现 28 条 comrak 与 markdown-it/VS Code 的不一致。其中 23 条集中在四类
“实现成本明显高于收益”的硬边角：

1. **Linkify**：comrak autolink 与 markdown-it/linkify-it 的 `www.`、实体分号、
   尾部冒号、邮箱边界不同（6 条）。
2. **Reference definition**：comrak 不校验目标；被拒协议的引用定义会被移除，
   尖括号目标（`[r]: <a b.md>`）在 EOF 无换行时解析失败（6 条中的 2 条）。
3. **Front matter**：comrak 的 front matter 扩展会消费/省略该块；VS Code 渲染表格，
   且空 `---\n---` 也会被消费（10 条）。
4. **长尾**：URL normalization、图像 alt、被拒目标的 sourcepos 回退（1 条 alt +
   未充分覆盖的 URL/alt/sourcepos 风险）。

另有 2 条 `vscode:` 链接服务器偏差与 3 条表格对齐待修。

用户决定：**这四类直接采用 comrak 行为**，不再写逐字节对齐 VS Code 的自定义层。

## 决定

1. **Linkify 用 comrak autolink**：开 `extension.autolink`，不写独立 linkify pass。
   已知差异：`www.example.com` 会被链接；`&copy;`、尾部 `:`、病态邮箱边界的文本
   范围与 markdown-it 不同。裸邮箱仍会链成 `mailto:`。
2. **Reference definition 用 comrak 解析**：不做预扫描。
   - 被拒协议的整条定义会被移除，引用退化成字面文本；
   - 尖括号目标 `[r]: <a b.md>` 在**文件末尾没有换行**时解析失败（comrak EOF quirk），
     定义行可能以字面/畸形 raw HTML 留下；正常以换行结尾的文档会解析，与 markdown-it 一致；
   - 重复定义、title、多行定义的边角全部跟随 comrak。
3. **Front matter 用 comrak 扩展**：`front_matter_delimiter = Some("---")`。
   合法块被消费/省略，不渲染 VS Code 的 `table.frontmatter`；空 `---\n---`
   按 comrak 行为不消费（会输出两个 `<hr>`）。
4. **长尾用 comrak 默认**：
   - URL 输出用 `escape_href`，不实现 mdurl 的逐字节 normalization；
   - 图像 alt 用 comrak 的 Plain 渲染（实体保持解码后的字符）；
   - 被拒目标不做 markdown-it 的 sourcepos/raw-tail 回退；简化为渲染标签文本，
     不生成锚点/图片。差异记录在案。

## 不交出去的安全边界

“采用 comrak 行为”**不包括**协议安全。以下仍是自定义层：

- 行内链接/图片继续过 `validateLink`：拒绝 `javascript:`、`vbscript:`、`file:`、
  非法 `data:`；**任意 `data:image/*;…`**（链接与图片位置）是唯一放行的例外；
  `vscode:`/`vscode-insiders:` 链接拒绝（服务器偏差，见 ADR 0005）。
- 不能用 comrak 的 `render.unsafe = true` 直接放行危险 URL；`unsafe` 只用于
  裸 HTML 透传。
- 裸 HTML 仍由 [ADR 0006](0006-html-trust-and-csp.md) 的 Trust/CSP 约束。
- 被拒目标即使回退简化，也绝不能产出可执行的 `href`/`src`。

## 后果

- 项目的承诺从“严格 VS Code 语义”改为 **“VS Code 核心语义与视觉 + comrak 硬边角”**；
  README/GLOSSARY/设计文档必须写清楚这 23 条 comrak accepted deviations，
  以及 2 条 `vscode:` 链接服务器偏差。
- P2 去掉 linkify pass、reference 预扫描、front matter 表格、alt 提取；
  保留：协议校验、URL 重写、表格对齐 `style="text-align:…"`、`<s>`、代码块 class、
  raw HTML、任务列表/标题 id 关闭。P2 由 8–12 天下调到 **4–6 天**。
- 整体执行计划由 5–7 周下调到 **4–5 周**。
- P4 移植旧测试时，这 25 条 accepted 差异的期望改为 comrak/服务器行为；
  golden 把它们标为 accepted，不再追求 markdown-it 逐字节一致。
- P0 报告保留为历史证据；其“必须补”的 25 条改为 accepted（23 comrak +
  2 vscode），剩下 3 条表格对齐仍需自定义。

## 考虑过的替代方案

- **继续逐条对齐 markdown-it**：linkify 2–3 天、reference 1–1.5 天、front matter
  YAML 长尾、alt/URL 长尾；收益是逐字节一致，成本高且不确定。
- **换 markdown-it-rs / 内嵌 markdown-it**：解析器级一致，但引入不成熟 crate 或
  JS 引擎，违背单二进制目标；不采纳。
- **只对 linkify/reference 放弃、其余继续对齐**：front matter YAML 与 URL/alt
  长尾仍然不划算；统一按本 ADR 处理，边界更清楚。
