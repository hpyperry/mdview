# 图片放大：手写遮罩，不引入 lightbox

**Status**: accepted

正文图片一律由服务端包一层**包裹链接** `<a class="zoom" href="原图">`：没有 JS 时
点它直接打开原图，有 JS 时那段内联脚本接管点击，弹出运行时创建的单例 `<dialog>`
（`showModal()`），把原图按视口缩放居中。

不引任何现成库，理由是实测下来的体积与能力都不划算：最轻的 medium-zoom 也要
**3.1 KB gzip**，而它恰好一样都不给这个项目要的东西 —— 没有 aria、没有焦点管理、
只管 Esc 的 keyup、不锁滚动；PhotoSwipe / GLightbox / lightGallery / Fancybox 则是
**15–42 KB gzip 再加一份独立 CSS**，能力（相册、滚轮缩放、双指手势）远超需要，
却全都要求图片外面**先**有一层 `<a>`。原生 `<dialog>` 免费给出 top layer、
`::backdrop`、Esc 关闭、背景 inert 与隐式 `aria-modal`，自己写的只有约 40 行 JS。

## 考虑过的替代方案

- **medium-zoom（FLIP 原位放大）**：观感最好，但要 `cloneNode` + `getBoundingClientRect`
  + 滚动偏移补偿，而且遮罩、滚动锁、焦点归还仍然得自己补 —— 背一个依赖却省不下代码。
- **纯 CSS `:target` / checkbox hack**：零 JS，但 `:target` 会污染 URL 与后退历史、
  Esc 无效、没有焦点管理，而且 Markdown 生成的 HTML 里插不进 checkbox。
- **引入 PhotoSwipe / GLightbox**：能力过剩，且与「零第三方文件、内网离线可审计」
  直接冲突 —— 与 [ADR 0001](0001-markdown-target-encoding.md) 拒绝 markdown-it 是同一条理由。
- **只包 `<a>`、不写 JS（点击＝新标签看原图）**：最省，但没有放大视图；
  同标签打开会把当前文档页替换掉，所以这只能当降级路径，不能当唯一形态。

## 影响与代价

- `href` **逐字节复用** `<img>` 已有的 `src`：那条「只解码一次、只编码一次」的管线
  不许被走第二遍，两者永远同源（`TestImageZoom.test_href_is_byte_identical_to_src`）。
- **链接里的图片（徽章图片）不包裹**：`<a>` 不能套 `<a>`，浏览器会把外层链接撕成
  两半，徽章就点不动了。服务端按「锚点深度为 0」判定，与上下文无关。
- **不做**相册、滚轮缩放、双指缩放、1:1 切换：要这些就得回到上面那些库。
- 入场动画依赖 `@starting-style` + `transition-behavior: allow-discrete`（2024 Baseline）；
  `prefers-reduced-motion: reduce` 时整段动画不生效（Chrome 实测走的是无动画分支）。
- 关闭时把焦点还给**包裹链接**而不是 `<img>`：`img` 默认不可聚焦，`img.focus()` 是空操作
  （Chrome 实测 `activeElement` 会停在 `body`）。
- 带修饰键（Cmd/Ctrl/Shift/Alt）或中键的点击**不劫持**，照旧走浏览器的
  「新标签打开 / 另存为」—— 这层链接同时是原图的入口，抢掉它就没别的出口了。
- 超过 `--max-preview` 的图片本来就由服务端改为下载（页面上是裂图），点它也就变成下载。
