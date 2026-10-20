# 岛屿前端与内容主导的全宽外壳

**Status**: accepted（2026-10-20）；左侧当前目录侧栏与正文预留导航列由
[ADR 0013](0013-full-site-navigation-island.md) 更新；TOC 细轨改为悬停展开
文字大纲；页头改为横跨内容面，搜索结果行定位由
[ADR 0014](0014-markdown-line-target.md) 补充（决策 5）

原前端是一个 `assets/mdview.js` IIFE：所有页面加载同一份脚本，DOMContentLoaded
后执行 7 个初始化器。行为还能用，但改一个交互容易影响整页，且三列卡片把 780px
正文压得很紧。用户确认采用 island 架构，同时重做视觉层级：**使用频率决定视觉
权重，内容面最大，辅助区退后，低频能力按需展开**。

## 决定

### 1. 岛清单与边界

服务端在 `body[data-islands]` 输出页面实际需要的岛；运行时就只初始化这些岛：

- **外壳岛**：`theme`、`nav`、`search`、`totop`；
- **文档页岛**：`toc`、`linetarget`、`code`、`zoom`；
- **源码页岛**：`source`。

服务端 HTML 是权威；岛只接管自己的控制区或生成自己的 UI，不对整块正文做
hydration。无 JS 时正文、行号、搜索页仍可读，TOC/工具条/放大浮层不出现。

### 2. 水合策略

- `theme`、`nav`、`search`、`totop`、`toc`、`linetarget`：立即；
- `code`、`zoom`：空闲；
- `source`：进入视口附近后。

每个岛独立 try/catch；一个岛失败不阻断其他岛。浏览器探针通过
`window.__mdviewIslands` 检查已挂载的岛。

### 3. 工具链

- `web/` 使用 TypeScript + esbuild，单入口 `app.ts` → `app.js` + `app.css`；
- Preact 只用于有局部状态的岛：TOC、代码工具条、图片放大、全站导航；主题、搜索、
  回顶、行定位、源码分块保持原生 TS；
- `build.rs` 在编译时执行 `npm run build:web`，把产物写进 Cargo `OUT_DIR`
  并 `include_bytes!`/`include_str!` 进二进制；
- `npm ci` 是开发/CI 的一次性准备步骤，不在 build.rs 里联网安装；
- musl cross 构建先在 host 执行 `npm run build:web`，再用
  `MDVIEW_WEB_PREBUILT=web/dist` 复用产物，避免容器内没有 Node；
  `Cross.toml` 负责把这个环境变量透传进 cross 容器。

### 4. CSS 归属

应用 CSS 全部迁到 `web/src/styles/app.css`，由 esbuild 输出并作为
`/_assets/app.css` 提供；VS Code `markdown.css` 与 `highlight.css` 保持独立。
Rust 不再维护大段外壳 CSS。

### 5. 内容主导的布局

- `.app` 最大 1680px、外边距 16px；顶栏与内容面占满可用宽度；
- ≥1360px：内容面 + 24px TOC 细轨；901–1359px 与 ≤900px 单列；
- 内容面最大 1240px，阅读行最大 1000px；页头横跨内容面（左右 30px），正文
  仍保持阅读行；代码块/表格随内容面变宽；
- 全站导航是默认收起的浮层；TOC 细轨默认只显示刻度，悬停或键盘聚焦时向左
  展开带文字大纲；
- 搜索页表单放在页头右侧，窄屏自动换行；窄屏直接进入搜索页；
- TOC 细轨：刻度点击跳转；悬停/聚焦展开带文字大纲，顶部图标可固定/收起；
  展开是浮层，不改变正文宽度。

### 6. 保留项

- 16px 正文、1.7 行高；标题无 id，TOC 运行时生成；
- 主题三态、无 JS 基线、CSP nonce-only、零外部请求；
- 大源码页全文分块与 `content-visibility` 策略（ADR 0011）。

## 考虑过的替代方案

- **继续单个 IIFE，只拆函数**：改动小，但没有页面级水合边界，低频功能仍随所有
  页面加载；不满足“按需”。
- **所有岛都用 Preact**：组件一致，但主题/侧栏/源码分块没有组件状态，反而增加
  运行时与服务端 DOM 的边界处理。
- **多入口/动态 import**：每页字节更少，但需要多份资产、CSP `strict-dynamic`
  或 `'self'`，并产生请求瀑布；当前单 bundle 约 34KB，不值得。
- **保留居中窄文档**：阅读舒适，但 1440 屏幕上左右各约 128px 空白，用户明确
  认为布局没有用满。
- **继续常驻三列卡片**：辅助面板与正文抢视觉重量，正文仍被压缩。

## 后果

- 从源码构建需要 Node 22 + `npm --prefix web ci`；运行时仍只需单二进制。
- 首次页面加载多出 `app.js`（约 34KB）与 `app.css`（约 27KB），均为同源、
  可缓存资产；无 JS 时不影响内容阅读。
- 构建脚本会在每次 cargo 编译时运行 esbuild（通常几十毫秒）；CI/发布用预构建
  产物避免容器内 Node 依赖。
- 新增交互必须放进现有岛或新增岛，并更新 `data-islands` 清单；不要再写全局
  DOMContentLoaded 初始化器。
- 文档页新增 `linetarget` 岛，负责把搜索 `#L<n>` 映射到渲染块；页头统一使用
  `.head-inner` 横跨内容面，正文阅读行仍由 `.markdown-body` 限制为 1000px。
- 既有 ADR 0010 的三列/780px 数值被本 ADR 取代；搜索仍沿用 ADR 0009 的
  `form-action 'self'` 与无 JS 表单能力。
