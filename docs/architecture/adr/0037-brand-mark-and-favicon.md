# ADR 0037：品牌标记与 favicon

- Status: accepted
- Date: 2026-11-11

## 背景

页面此前没有品牌标记，浏览器默认的 `/favicon.ico` 请求也没有响应。需要一个在
16×16 下仍可辨认、与 VS Code 蓝一致、运行时无外部请求的标记。

## 决定

### 1. 标记

- 32×32 圆角方块（`#0969da`），中间是白色 Markdown “M” 折线；
- 源文件 `assets/favicon.svg`，另存 32×32 的 `assets/favicon.png` 作为不支持
  SVG favicon 的浏览器的兜底；
- 两个文件都 `include_str!`/`include_bytes!` 进二进制，并计入资产版本 hash。

### 2. 顶栏位置

- 放在顶栏最左、导航按钮之前，作为链接到 `/` 的首页入口
  （`aria-label="返回首页"`），标记 24×24；
- 文件名仍绝对居中，搜索/主题仍在右侧；≤900px 只保留标记；
- 无 JS 时标记仍在（服务端渲染），导航按钮按 no-JS 规则隐藏。

### 3. favicon 接口

- `<link rel="icon" type="image/svg+xml" href="/_assets/favicon.svg?__mdview=asset&v=…">`
- `<link rel="icon" type="image/png" sizes="32x32" href="/_assets/favicon.png?__mdview=asset&v=…">`
- 两条路由走与 `app.css`/`app.js` 相同的 `asset_or_file`：带 `__mdview=asset`
  标记时返回嵌入资产，`Cache-Control: immutable`，版本由资产 hash 决定。

### 4. 不保留 `/favicon.ico`

内部 URL 必须带 `__mdview=` 标记，且同路径真实文件优先；因此不为 `/favicon.ico`
预留路由。浏览器通过 `<link rel="icon">` 使用上面的标记资产；如果根目录里真的有
`favicon.ico`，它仍按普通文件返回。

## 备选方案

- **CSS 方块 + 字母 “m”**：与旧 `.brand-mark` 相同，辨识度低；
- **只提供 `/favicon.ico`**：与内部 URL/真实文件优先规则冲突，还要维护 ICO 编码；
- **引用 CDN 图标**：违反单文件、零外部请求约束。

## 后果

- 顶栏最左多一个 24px 首页入口，顶栏标题仍居中，不影响主岛布局；
- favicon 与 logo 共用同一份 SVG，资产版本更新后 URL 自动变化；
- 浏览器标签页使用蓝色 M 标记；不支持 SVG favicon 的浏览器回退到 PNG；
- 新增两条资产路由、对应单测与浏览器探针断言；
- 旧的 `.brand-mark` 文字样式被图片替代，相关 CSS 收窄为 24×24 的图片容器。
