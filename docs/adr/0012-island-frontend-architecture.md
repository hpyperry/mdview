# 岛屿前端与内容主导的全宽外壳

**Status**: accepted（2026-10-20）

原前端是一个 `assets/mdview.js` IIFE：所有页面加载同一份脚本，DOMContentLoaded
后执行 7 个初始化器。行为还能用，但改一个交互容易影响整页，且三列卡片把 780px
正文压得很紧。用户确认采用 island 架构，同时重做视觉层级：**使用频率决定视觉
权重，内容面最大，辅助区退后，低频能力按需展开**。

## 决定

### 1. 岛清单与边界

服务端在 `body[data-islands]` 输出页面实际需要的岛；运行时就只初始化这些岛：

- **外壳岛**：`theme`、`sidebar`、`search`、`totop`；
- **文档页岛**：`toc`、`code`、`zoom`；
- **源码页岛**：`source`。

服务端 HTML 是权威；岛只接管自己的控制区或生成自己的 UI，不对整块正文做
hydration。无 JS 时正文、行号、搜索页仍可读，TOC/工具条/放大浮层不出现。

### 2. 水合策略

- `theme`、`sidebar`、`search`、`totop`、`toc`：立即；
- `code`、`zoom`：空闲；
- `source`：进入视口附近后。

每个岛独立 try/catch；一个岛失败不阻断其他岛。浏览器探针通过
`window.__mdviewIslands` 检查已挂载的岛。

### 3. 工具链

- `web/` 使用 TypeScript + esbuild，单入口 `app.ts` → `app.js` + `app.css`；
- Preact 只用于有局部状态的岛：TOC、代码工具条、图片放大；主题、侧栏、搜索、
  回顶、源码分块保持原生 TS；
- `build.rs` 在编译时执行 `npm run build:web`，把产物写进 Cargo `OUT_DIR`
  并 `include_bytes!`/`include_str!` 进二进制；
- `npm ci` 是开发/CI 的一次性准备步骤，不在 build.rs 里联网安装；
- musl cross 构建先在 host 执行 `npm run build:web`，再用
  `MDVIEW_WEB_PREBUILT=web/dist` 复用产物，避免容器内没有 Node。

### 4. CSS 归属

应用 CSS 全部迁到 `web/src/styles/app.css`，由 esbuild 输出并作为
`/_assets/app.css` 提供；VS Code `markdown.css` 与 `highlight.css` 保持独立。
Rust 不再维护大段外壳 CSS。

### 5. 内容主导的布局

- `.app` 最大 1680px、外边距 16px；顶栏与三列占满可用宽度；
- ≥1360px：232px 平面目录栏 + 内容面 + 24px TOC 细轨；901–1359px 两列；
  ≤900px 单列，目录栏变抽屉；
- 内容面最大 1240px，阅读行最大 1000px；代码块/表格随内容面变宽；
- 目录栏是平面导航，不再使用卡片背景/阴影；TOC 细轨只在需要时展开浮层；
- 顶栏只保留产品名、搜索图标、主题与侧栏开关；页面路径移入文档头部；
- 搜索变成图标 + 弹层，提交进入搜索页；窄屏直接进入搜索页；
- TOC 细轨：刻度点击跳转，点空白/顶部图标展开浮层；不改变正文宽度。

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
- 既有 ADR 0010 的三列/780px 数值被本 ADR 取代；搜索仍沿用 ADR 0009 的
  `form-action 'self'` 与无 JS 表单能力。
