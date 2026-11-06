# HTML 手动测试夹具

用于手动验证 [ADR 0015](../../../docs/architecture/adr/0015-html-file-preview-and-sandbox.md)
的 trusted 原文，以及 [ADR 0025](../../../docs/architecture/adr/0025-html-second-origin.md)
的未信任 HTML 第二 origin。所有资源都在本地，不需要外网。

## 启动

在仓库根目录：

```bash
cargo build --release

# 已信任根：HTML 在主 origin 走静态原文
./target/release/mdview --root tests/fixtures/html-preview --trust --port 8000 --port-tries 0

# 另开一个终端：未信任根：HTML 302 到第二 origin
./target/release/mdview --root tests/fixtures/html-preview --untrusted \
  --port 8001 --port-tries 0 --html-port 8002
```

第二 origin 的端口会打印在启动横幅的 `html:` 行；不传 `--html-port` 时默认是
主端口 + 1，冲突顺延。

## 1. Trusted 原文（`http://127.0.0.1:8000`）

打开 `http://127.0.0.1:8000/page.html`，预期：

- 页面没有 mdview 顶栏、面包屑、tabs 或 iframe；
- 相对 `style.css` 生效；
- “运行时探针”显示 `localStorage: ok`、`fetch /_nav?__mdview=nav: 200`；
- 点击 `打开 guide.md` 进入 Markdown 页面；
- 点击 `target=_top` / `target=_blank` 都按普通浏览器行为导航；
- `http://127.0.0.1:8000/report.html` 是报告本身，没有外壳；
- `http://127.0.0.1:8000/page.html?raw=1` 是源码页，顶部有 `预览 / 源码` tabs，
  “预览”指回主 origin 原文；
- `http://127.0.0.1:8000/page.html?view=1` 仍是原文（参数被忽略）；
- 不出现 `html:` 启动行，也不会占用第二端口。

## 2. 未信任第二 origin（`http://127.0.0.1:8001`）

打开 `http://127.0.0.1:8001/page.html`，浏览器应 **302** 到
`http://127.0.0.1:8002/page.html`，预期：

- 地址栏是第二 origin，页面没有 mdview 顶栏、面包屑、tabs 或 iframe；
- 相对 `style.css` 生效；
- “运行时探针”显示 `localStorage: ok`、`fetch /_nav?__mdview=nav: 404`；
- `http://127.0.0.1:8002/_nav?__mdview=nav` 返回 404（纯文本），没有导航 JSON；
- `http://127.0.0.1:8002/_assets/app.js` 返回 404；
- `http://127.0.0.1:8002/page.html?raw=1` 是原文（第二 origin 不渲染源码页）；
- 主 origin 的 `http://127.0.0.1:8001/page.html?raw=1` 是源码页，
  “预览”tab 指向 `http://127.0.0.1:8002/page.html`；
- 主 origin 的 `?view=1` 同样 302，不再有沙箱裸页；
- 主 origin 的目录行仍有 `查看 page.html 源码` 入口；
- 压缩包内 HTML 也按同一规则 302 到第二 origin。

## 3. 子资源 MIME

```bash
# trusted 主 origin：作为样式表取，返回 text/css 和原始 CSS
curl -sI -H 'Sec-Fetch-Dest: style' http://127.0.0.1:8000/style.css
curl -s -H 'Sec-Fetch-Dest: style' http://127.0.0.1:8000/style.css

# trusted 主 origin：直接导航仍是源码页
curl -s http://127.0.0.1:8000/style.css | head

# 第二 origin：静态镜像，直接按扩展名返回
curl -sI http://127.0.0.1:8002/style.css
```

## 4. SVG

```bash
curl -sI http://127.0.0.1:8000/evil.svg
curl -sI http://127.0.0.1:8002/evil.svg
```

两个响应都应包含：

```text
Content-Security-Policy: sandbox allow-top-navigation-by-user-activation
```

直接打开任意一个，页面里的文字应保持 `not executed`，标签标题不应变成
`EXECUTED`。

## 5. 搜索

打开 `http://127.0.0.1:8000/search?__mdview=search&q=htmlneedle`（trusted）或
`http://127.0.0.1:8001/search?__mdview=search&q=htmlneedle`（untrusted 主 origin），
HTML 内容行应链接到 `/page.html?raw=1#L...`；文件标题链接到 `/page.html`
（未信任时再 302 到第二 origin）。

## 6. 已知限制

- 端口是 origin 边界，不是 cookie 边界：cookie 按 domain 共享。
- 反向代理只转发主端口时，第二端口不可达；需要单独暴露，或只在本地使用。
- 端口变化会让第二 origin 的 `localStorage` / Service Worker 重新开始。

## 自动化测试

- `bash tests/selftest-rust.sh`：302 Location、第二 origin 原文/MIME/无内部路由、
  源码页预览链接、压缩包 HTML。
- `node tests/browser-probe.mjs`：module、sessionStorage、Service Worker、同源
  fetch、相对 CSS 在第二 origin 全部可用，主 origin 无 iframe/外壳。
