# ADR 0029：固定主岛，内容在岛内滚动

- Status: accepted
- Date: 2026-11-06

## 背景

主岛铺满外壳后，页面仍使用文档滚动：顶栏 sticky，但主岛跟着页面一起向上移动。
用户看到的是一块固定顶栏和一块会滑走的内容，页面被切成两个运动层；用户希望
主岛本身也是固定容器，真正滚动的是岛里的正文。

## 决策

- **≥901px** 使用固定外壳：
  - `html, body { height: 100%; overflow: hidden; }`；
  - `.app` 为 100vh 的纵向 flex，顶栏 + 主岛填满视口；
  - `.shell` 占满剩余高度，`.main` / `.content-card` 高度 100%；
  - `.content-card` 成为滚动容器（`overflow-y: auto`，`overscroll-behavior: contain`）；
  - TOC 岛与主岛同高，目录列表在岛内独立滚动。
- **≤900px** 保留普通文档滚动，避免移动端地址栏与内滚动冲突。
- 滚动相关脚本统一感知滚动容器：
  - `totop` 优先滚动 `.content-card`；
  - TOC 跳转与 scroll-spy 使用容器 `scrollTop` 和容器顶部偏移；
  - 大源码懒高亮使用容器可视区域，并把 `IntersectionObserver` 的 `root` 指向容器；
  - 行定位继续用 `scrollIntoView`，由最近滚动容器处理。
- 打印样式恢复 `overflow: visible` 与自动高度，分页行为不变。

## 后果

- 顶栏、主岛和 TOC 岛在桌面保持静止，只有岛内内容滚动，页面不再有两层运动会；
- 浏览器 `window.scrollY` 在桌面恒为 0，测试与脚本必须读取内容卡 `scrollTop`；
- 代码块/大源码的懒加载要使用内容卡作为可视区域，不能只看 `window.innerHeight`；
- 移动端仍按普通文档滚动，行为与之前一致。
