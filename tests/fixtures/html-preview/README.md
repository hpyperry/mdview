# HTML 手动测试夹具

用于手动验证 ADR 0015 的 Trust 门控 HTML 行为。所有资源都在本地，不需要外网。

## 启动

在仓库根目录：

```bash
cargo build --release

# 离线 Linux 且没有 web/node_modules 时，从开发机复制 web/dist 后：
# MDVIEW_WEB_PREBUILT=web/dist cargo build --release

# 已信任根：HTML 走静态原文
./target/release/mdview --root tests/fixtures/html-preview --trust --port 8000 --port-tries 0

# 另开一个终端：未信任根：HTML 走沙箱外壳
./target/release/mdview --root tests/fixtures/html-preview --untrusted --port 8001 --port-tries 0
```

不要把两个服务都指向同一个端口；上面的命令已经分开。

## 1. Trusted 原文（`http://127.0.0.1:8000`）

打开 `http://127.0.0.1:8000/page.html`，预期：

- 页面没有 mdview 顶栏、面包屑、tabs 或 iframe；
- 相对 `style.css` 生效；
- “运行时探针”显示 `localStorage: ok`、`fetch /_nav: 200`；
- 点击 `打开 guide.md` 进入 Markdown 页面；
- 点击 `target=_top` / `target=_blank` 都按普通浏览器行为导航；
- `http://127.0.0.1:8000/report.html` 是报告本身，没有外壳；
- `http://127.0.0.1:8000/page.html?raw=1` 是源码页，顶部有 `预览 / 源码` tabs；
- `http://127.0.0.1:8000/page.html?view=1` 与默认原文一致。

## 2. 未信任沙箱（`http://127.0.0.1:8001`）

打开 `http://127.0.0.1:8001/page.html`，预期：

- 出现 mdview 外壳和沙箱 iframe；
- iframe 内探针显示 `localStorage: blocked`、`fetch /_nav: blocked`；
- 相对 CSS 仍生效；
- 顶部 `预览 / 源码` tabs 和 `沙箱预览` 标识可见；
- `?view=1` 是沙箱裸页；`?raw=1` 是源码页；
- 点击 iframe 里的 `target=_top` 不会把外层 mdview 页面导航走；
- `target=_blank` 会开新标签，但新标签继承沙箱。

## 3. 子资源 MIME

```bash
# 作为样式表取：应返回 text/css 和原始 CSS
curl -sI -H 'Sec-Fetch-Dest: style' http://127.0.0.1:8000/style.css
curl -s -H 'Sec-Fetch-Dest: style' http://127.0.0.1:8000/style.css

# 直接导航：应是源码页
curl -s http://127.0.0.1:8000/style.css | head
```

## 4. SVG

```bash
curl -sI http://127.0.0.1:8000/evil.svg
```

响应应包含：

```text
Content-Security-Policy: sandbox allow-top-navigation-by-user-activation
```

直接打开 `http://127.0.0.1:8000/evil.svg`，页面里的文字应保持 `not executed`，
标签标题不应变成 `EXECUTED`。

## 5. 搜索

打开 `http://127.0.0.1:8000/search?q=htmlneedle`，HTML 内容行应链接到
`/page.html?raw=1#L...`；文件标题链接到 `/page.html`。

## 6. Linux 的 `_nav` 500 / CSS 丢失

用 `--verbose` 启动，复现问题后看 stderr：

```bash
./target/release/mdview --root tests/fixtures/html-preview --trust --verbose --port 8000
```

- `_nav` 失败会打印 `nav: 无法读取目录 <路径>: <errno>`；
- 看浏览器是否请求了 `GET /_assets/app.css`，状态是多少；
- 另开终端：

```bash
curl -sI http://127.0.0.1:8000/_assets/app.css | grep -iE 'content-length|content-type'
```

官方包应为 `Content-Length: 32949` 左右。如果是 0，说明跑的是自编译二进制且
`app.css` 为空；重新 `npm --prefix web ci && npm --prefix web run build:web`
再编译。

## 自动化测试

```bash
bash tests/selftest-rust.sh      # 黑盒 HTTP，含 trusted/untrusted HTML
node tests/browser-probe.mjs     # 需要 Chrome/Chromium
bash tests/run-all.sh            # 全量
```

`tests/selftest-rust.sh` 和 `tests/browser-probe.mjs` 会在临时目录里自己建夹具；
这个目录只是给你手动打开页面、看探针和链接行为用的。
