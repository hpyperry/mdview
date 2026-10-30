# 浏览器兼容基线：Chromium 86

**Status**: accepted（2026-10-30）。约束 `web/src/styles/` 与 `assets/*.css` 可用的
CSS 语法；由 [`tests/check-css-baseline.mjs`](../../../tests/check-css-baseline.mjs) 执行。

在统信 UOS x86 + 360 信创版（旧 Chromium 内核）上打开 mdview，顶栏 `brand-mark`
不可见、`topbar` 没有底色和边框只在滚动内容上留一层模糊、搜索弹层的 `kbd` 没有
背景和边框；同一个 URL 在 Chrome 完全正常，服务端无报错、无 404。

根因是 `app.css` 用了三个基线外特性：`light-dark()`（12 处，需 Chromium 123+）定义
全部颜色 token，`color-mix()`（5 处，需 111+）做半透明，`inset: 0`（需 87+）定位
遮罩。旧内核把整条声明判为 *invalid at computed-value time*：背景变成
`rgba(0,0,0,0)`、边框变成 `none`、阴影变成 `none`；而 `backdrop-filter`（76+）仍然
生效，于是 `topbar` 只剩一块透明毛玻璃。CSS 的无效值静默失败，所以控制台没有任何
报错——这也是它一直没被自动化发现的原因：浏览器探针跑的是最新 headless Chrome，
永远支持这些语法。

## 决定

1. **基线定为 Chromium 86**。覆盖 360 信创版 v10 的常见内核，以及同代或更新的
   统信 UOS 内置浏览器、奇安信可信浏览器、Edge/Chrome。不承诺 Chromium 78 及更早。
2. **静态双色板**。`app.css` 的 `:root` 写浅色值；深色在
   `@media (prefers-color-scheme: dark) html:not([data-theme="light"])` 与
   `html[data-theme="dark"]` 两处各写一份。不再使用 `light-dark()`。
   `color-scheme`（81+）保留，滚动条与表单控件的系统配色照旧。
3. **半透明层次用静态 token**。新增 `--topbar-bg`、`--surface-translucent`、
   `--accent-wash` 三个每主题一份的 rgba，结果行 hover 预计算成 `--hover`；
   五处 `color-mix()` 全部消掉。`backdrop-filter` 保留，`topbar` 仍是半透明毛玻璃。
4. **`inset: 0` 展开为四边**（`.scrim`、`.nav-scrim`），86 上遮罩仍是全屏点击区。
5. **静态检查兜底**。`tests/check-css-baseline.mjs` 维护带最低版本的特性黑名单
   （`light-dark`/`color-mix`/现代颜色函数/`inset`/`:is`/`:where`/`@layer`/`@container`/
   `:has`/动态视口单位/`text-wrap`/`scrollbar-gutter`/`subgrid`/`overflow: clip`/
   `accent-color`/`text-underline-offset`/CSS 嵌套），扫 `web/src/styles/` 与
   `assets/*.css`；同时逐项比对两份深色色板，防止手写副本漂移。脚本接入
   `tests/run-all.sh`。升基线时删对应条目即可。

## 考虑过的替代方案

- **`@supports (color: light-dark(...))` 渐进增强**：现代内核源码更短，但色板实际
  存在三份（浅色回退、深色回退、`light-dark`），改一次颜色要同步三处，漂移面更大。
- **构建期用 Lightning CSS 按 browserslist 展开**：源文件最干净，但引入新构建依赖
  与一份可调基线，产物与源码不再一一对应，排查线上样式时要先想“降级器做了什么”。
- **只检测旧内核并提示升级**：内容可读但界面残缺，现场用户没有升级权限时等于不可用。
- **不写 lint，只写文档约定**：这次的根因正是“没人注意到声明被整条丢弃”，纯靠
  review 挡不住下一次随手写 `:has()`。

## 后果

- Chrome 上观感不变：`topbar` 仍是 92% 半透明 + 毛玻璃，其余颜色逐值等价。
- 深色色板在源码里写两遍，这是静态写法的固有成本；两份必须逐项一致，lint 会拦。
- 新增颜色 token 要同时改两处深色块；新增 CSS 特性要先查最低版本，必要时加进
  黑名单注释。
- 浏览器探针仍只跑最新 Chrome；旧内核的真机验收靠
  [`tests/fixtures/chromium-baseline/README.md`](../../../tests/fixtures/chromium-baseline/README.md)
  与 `probe.html` 的自检输出。

## 验证

- `node tests/check-css-baseline.mjs`：黑名单与深色色板同步。
- `bash tests/run-all.sh`：Chrome 侧全量回归。
- 旧内核真机：`probe.html` 报告 `light-dark`/`color-mix`/`inset` 不支持；mdview 页面
  上 `brand-mark`、`topbar` 底色与边框、`kbd`、目录页隔线、链接蓝、代码块底色恢复。
  功能编号见 [`F-93`](../../reference/features.md)。
