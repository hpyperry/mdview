# 旧引擎实测记录：Chromium 88（2026-11-04）

**目的**：在非最新 Chromium 上验证旧客户端 MIME 兜底（#42）与 86 基线回退（#44），
覆盖大源码分块、导出 PNG、主题/导航/TOC/放大/搜索。
**结论**：**PASS=25 FAIL=0**。
**注意**：本次实际引擎是 **Chromium 88.0.4287.0**，不是精确的 86；原因见“已知限制”。

## 环境

| 项 | 值 |
|---|---|
| 引擎 | HeadlessChrome/88.0.4287.0（Chromium snapshot revision 815036） |
| 容器 | Ubuntu 24.04 **amd64**（Docker Desktop on Apple Silicon，qemu 模拟） |
| 服务端 | `target/release/mdview`，`--host 0.0.0.0 --trust`，端口 7415 |
| 驱动 | 宿主机 Node 22 + 原生 WebSocket/CDP，连接容器 9222 |
| 页面 | `legacy.html` + `docs.js`、`big.txt`（15000 行）、`doc.md` + `pic.png` |

Chromium 88 与 86–94 同档：`content-visibility` 已支持（85+），
`contain-intrinsic-width: none` 未支持（95/98），正好覆盖 #44 的回退分支。

## 启动方式（可复现）

```bash
# 1. Chromium snapshot（Linux x64；86 的精确 revision 在快照桶里 404，
#    这里用 815036 = 88.0.4287.0）
curl -L -o /tmp/chrome86/chrome-linux.zip \
  https://commondatastorage.googleapis.com/chromium-browser-snapshots/Linux_x64/815036/chrome-linux.zip
unzip -q /tmp/chrome86/chrome-linux.zip -d /tmp/chrome86

# 2. Ubuntu amd64 容器（qemu 模拟）
docker run -d --name chrome86deps --platform linux/amd64 -p 9222:9222 ubuntu:24.04 sleep infinity
docker exec chrome86deps apt-get update
docker exec chrome86deps apt-get install -y --no-install-recommends \
  libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
  libasound2t64 libpango-1.0-0 libcairo2 libxshmfence1 libglib2.0-0 libx11-6 \
  libxext6 libxi6 libxtst6 libxss1 libfontconfig1 libexpat1 libgtk-3-0t64 \
  libxcb1 libx11-xcb1
docker cp /tmp/chrome86/chrome-linux chrome86deps:/opt/chrome86

# 3. headless 启动（qemu 下必须 --no-zygote --single-process，否则 zygote 崩）
docker exec -d chrome86deps sh -c '/opt/chrome86/chrome --headless --no-sandbox \
  --no-zygote --single-process --disable-gpu --disable-dev-shm-usage \
  --remote-debugging-address=0.0.0.0 --remote-debugging-port=9222 about:blank'

# 4. 宿主机起 mdview，构造夹具（docs.js / big.txt / doc.md / pic.png / style.css）
target/release/mdview --root /tmp/legacy-root --host 0.0.0.0 --trust --port 7415
```

检查脚本为临时 CDP harness（不在仓库内）：连接 `http://127.0.0.1:9222/json/version`，
用 `Fetch.enable` 拦截 `*docs.js*`，删除 `Sec-Fetch-*` 并强制 `Accept: */*`；
其余页面直接在 `http://host.docker.internal:7415` 上验证。

## 结果

| # | 检查 | 结果 |
|---|---|---|
| 1 | 剥掉 `Sec-Fetch-*` + `Accept: */*` 后 `docs.js` 仍执行 | ok |
| 2 | `window.OpenCollection` 已定义 | ok |
| 3 | 无 MIME 控制台错误 | ok |
| 4 | 源码岛已水合 | ok |
| 5 | 分块数量 31 | ok |
| 6 | 引擎不支持 `contain-intrinsic-width/height` | ok |
| 7 | `content-visibility` 回退为 `visible` | ok |
| 8 | 分块有实际高度、文档高度正常 | ok |
| 9 | 首行锚点 `#L1` 存在 | ok |
| 10 | 末行锚点 `#L15001` 可达 | ok |
| 11 | 导出岛已水合 | ok |
| 12 | PNG 导出成功 | ok |
| 13 | PNG 签名正确 | ok |
| 14 | 导出白底 | ok |
| 15 | 导出尺寸合理 | ok |
| 16 | 标题渲染 | ok |
| 17 | 代码高亮 | ok |
| 18 | 导出 PDF 按钮存在 | ok |
| 19 | TOC 生成 | ok |
| 20 | 主题切换 | ok |
| 21 | 全站导航打开 | ok |
| 22 | 图片放大（`showModal`） | ok |
| 23 | 搜索弹层 | ok |
| 24 | `:modal` 未知伪类按预期不可用 | ok |
| 25 | 页面无未捕获异常 | ok |

## 解释

- **MIME 修复在旧引擎上成立**：即使把 `Sec-Fetch-*` 全部剥掉、把 `Accept` 改成
  `*/*`，`docs.js` 仍按 `text/javascript` 返回并执行，`OpenCollection` 正常定义。
- **`@supports` 门禁成立**：Chromium 88 判断
  `CSS.supports('contain-intrinsic-width', 'none') === false`，`content-visibility`
  没有生效（计算值 `visible`），31 个分块全部有高度，`#L1` / `#L15001` 正常。
- **导出在旧引擎可用**：SVG `foreignObject` + Canvas + `document.fonts.ready` +
  `canvas.toBlob` 在 88 上成功生成白底 PNG。
- **基础岛可用**：主题、导航、TOC、放大、搜索都能在 88 上挂载和交互。

## 已知限制

- **不是精确的 Chromium 86**：快照桶里 M86 的 revision（如 800218）返回 404，
  本次用 88.0.4287.0。86–94 在 `content-visibility`/`contain-intrinsic-*` 上行为一致，
  但 `replaceChildren`（86 起）等精确边界没有在 86 上逐个复核。
- **<86 不在支持范围**：`app.js` 的语法下限仍是 Chrome 80；更老内核会解析失败。
- **qemu 单进程**：容器使用 `--single-process` 才稳定，真实 86 桌面/信创浏览器行为
  可能不同（尤其滚动、字体、Canvas）。
- **没有截图证据**：本轮是 CDP DOM/几何断言，不是视觉验收；字体/布局像素未比对。
- **未接入 CI**：harness 是临时的，旧引擎任务没有进 GitHub Actions。

## 后续

- 若要精确 86：需要找到存在构建产物的 M86 revision，或使用带 Chrome 86 的
  Playwright/browserless 镜像；网络受限时成本较高。
- 是否把临时 harness 固化为 `tests/legacy-probe.mjs`，等决定是否维护旧引擎自动化。
