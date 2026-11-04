# 引用块留白 复测文档

- 关联：Issue [#37](https://github.com/hpyperry/mdview/issues/37) / PR #N / F-94
- 夹具根：`tests/fixtures/blockquote-spacing/`（可直接作为 `--root`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/blockquote-spacing --trust --port 8003 --port-tries 0
```

- 入口：`/quote.md`
- 自动化覆盖：`tests/browser-probe.mjs` 的 `== blockquote spacing ==` 段（4 项几何断言）、`tests/check-css-baseline.mjs`；本页为人工视觉复测

## 背景

引用块有底色与左右内边距，块内最后一个子块（通常是段落）自带的 `margin-bottom: 16px`
不会穿出块外，只能留在底色里。改前实测色块上留白 2px、下留白 18px，文字看起来
贴顶；红框位置就是那截空带。

修复在 `web/src/styles/app.css`：引用块上下内边距改为对称的 8px，并清掉
`:first-child` / `:last-child` 在块内的上下外边距。`assets/markdown.css` 的
VS Code 语义基准不动（[ADR 0008](../../../docs/architecture/adr/0008-docs-shell-and-reading-typography.md)）。

## 复测步骤

1. 操作：按上面的命令启动，打开 `/quote.md`。
   预期：单段、两段、嵌套、含列表四种引用块，文字在色块内**上下留白相同**，
   不再有底部空带。

2. 操作：用开发者工具选中引用块，检查计算样式。
   预期：`padding-top` 与 `padding-bottom` 都是 `8px`；块内最后一个子元素的
   `margin-bottom` 为 `0px`。

3. 操作：对照引用块前后相邻的普通段落。
   预期：引用块与后一段之间仍是 `16px`；两段引用内部两段之间仍是 `16px`。

4. 操作：切到深色主题（右上角主题按钮）再看一遍。
   预期：留白对称不变；底色切换后文字仍垂直居中。

5. 操作：窄屏（≤900px）再看一遍。
   预期：留白不变，没有横向溢出。

## 自动化覆盖

- `node tests/browser-probe.mjs`：`== blockquote spacing ==` 段断言 5 个引用块
  的首/末子元素到色块边缘的留白等于上下内边距且互相对称、块后间距 16px、
  两段引用内部的段间距 16px。
- `node tests/check-css-baseline.mjs`：`> :first-child` / `> :last-child` 不触碰
  Chromium 86 基线外语法。

## 已知限制

- 这是视觉留白修复，没有改动 Markdown 语义或 HTML 结构；golden / render_compat
  断言不变。
- 断言读取的是计算后的几何值，字体加载完成前后 1px 内的取整差异按 `Math.round`
  归一；不覆盖旧内核的亚像素渲染差异。

## 清理

- 停止临时服务并释放端口（8003）。
- 夹具目录没有生成物；如需清理构建产物，按
  [构建卫生](../../../docs/guides/build-hygiene.md) 处理 `target/`。
