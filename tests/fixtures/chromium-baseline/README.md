# Chromium 86 基线 CSS 回退 复测文档

- 关联：Issue [#26](https://github.com/hpyperry/mdview/issues/26) /
  PR [#27](https://github.com/hpyperry/mdview/pull/27) / F-93
- 夹具根：`tests/fixtures/chromium-baseline/`（README-only + `probe.html`，不新增内容夹具）
- 启动（用仓库根作为 root，页面入口都在仓库内）：

```bash
cargo build --release
./target/release/mdview --root . --trust --port 8003 --port-tries 0
```

- 入口：
  - `/tests/fixtures/chromium-baseline/probe.html` —— 旧内核自检页
  - `/` —— 首页，看 `brand-mark` 与 `topbar`
  - `/docs/` —— 目录页，看隔线与链接色
  - `/docs/reference/features.md` —— Markdown 页，看代码块与表格

## 复测步骤

1. 在目标浏览器（360 信创版 / UOS 内置浏览器等旧内核）打开
   `/tests/fixtures/chromium-baseline/probe.html`。
   预期：特性表如实显示 `light-dark()` / `color-mix()` / `inset` 是否支持；三条演示
   规则判定 **PASS**，计算值为 `markBackground: rgb(9, 105, 218)`、
   `barBackground: rgba(255, 255, 255, 0.92)`、`barBorder: solid 1px`、
   `kbdBackground: rgb(255, 255, 255)`、`kbdBottomBorder: 2px`。
2. 打开 `/`。
   预期：顶栏左侧出现蓝底圆角方块 `m`（`brand-mark`）；`topbar` 有底色、1px 边框和
   圆角，滚动时呈现毛玻璃而不是只剩一层模糊；点搜索按钮，弹层里的 `Enter` / `Esc`
   有底色与边框（底部 2px）。
3. 打开 `/docs/`。
   预期：目录行之间有分隔线；文件名/链接是蓝色（`--accent`），不是纯黑；悬停有淡底。
4. 打开 `/docs/reference/features.md`。
   预期：代码块有底色、表格有边框、`mark` 高亮有底色；正文在浅/深色下都可读。
5. 点主题按钮切换「浅色 / 深色 / 跟随系统」。
   预期：深色下页面底色、卡片、边框、`topbar` 半透明底一起变化；切换后按钮标题
   与状态提示正确。
6. 把窗口缩到 ≤900px，打开导航抽屉。
   预期：抽屉外的遮罩覆盖全屏且可点击关闭（`inset` 展开后的回归点）。

Chrome 对照：同一批 URL 在 Chrome 上改动前后观感应一致；`topbar` 仍是 92% 半透明
加 `backdrop-filter` 毛玻璃。

## 自动化覆盖

- `node tests/check-css-baseline.mjs`：黑名单（基线外语法）+ 两份深色色板逐项比对；
  已接入 `bash tests/run-all.sh`。
- `bash tests/run-all.sh`：Chrome 侧全量回归（含 238 项浏览器探针）。
- 旧内核本身**没有**自动化：浏览器探针跑最新 headless Chrome，不支持回退模拟。

## 验证记录

- 2026-10-30，Ubuntu 26.04 arm64（UTM，Apple Virtualization 后端 + Rosetta）+
  Chromium 92.0.4515.107（Linux x64，Rosetta 转译）：
  - **旧版**（2026-10-21 的 aarch64 构建）复现：`brand-mark` 不可见、`topbar`
    无底色无边框、`kbd` 无键帽、目录行无隔线、链接偏黑、代码块无底色。
  - **新版**（PR #27 的 aarch64 musl 构建）在同一个内核下以上全部恢复，浅色/深色
    主题与搜索弹层正常。
- 尚未在统信 UOS + 360 信创版真机上复测。Chromium 92 与 360 的差异主要是版本号，
  本次问题的失效机制相同（缺少 `light-dark()` / `color-mix()`）。

## 已知限制

- macOS arm64 上没有 Chromium 86 构建、也没有 Rosetta，本机无法自动化复现旧内核；
  真机复测只能在 UOS + 360 或同类旧内核环境完成。
- 360 信创版不同版本内核可能是 Chromium 78 / 86 / 95；本基线只承诺 **86+**，
  78 上的 flex `gap`（84+）等额外差异不在范围内。
- `probe.html` 验证的是“静态声明是否生效”，不覆盖 mdview 页面的完整交互；交互仍看
  Chrome 探针。
- 两份深色色板是手写副本，lint 只能保证逐项一致，不能保证语义正确。

## 清理

停止临时服务，释放端口；无需删除缓存或临时文件（本目录不生成产物）。
