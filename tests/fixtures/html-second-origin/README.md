# HTML 第二 origin 复测夹具

关联：[Issue #52](https://github.com/hpyperry/mdview/issues/52) · PR #53

这个夹具是一个最小应用型 HTML：ES module、`sessionStorage`、Service Worker、
相对 `fetch()`、CSS 与 JSON。它用来验证未信任根不再进入 sandbox iframe，而是
302 到第二 origin 的只读静态镜像。

## 启动

在仓库根目录：

```bash
cargo build --release

# 未信任根：主 origin 8010，第二 origin 8011
./target/release/mdview \
  --root tests/fixtures/html-second-origin \
  --untrusted --host 127.0.0.1 \
  --port 8010 --port-tries 0 --html-port 8011

# 对照：trusted 根（HTML 在主 origin 原文）
./target/release/mdview \
  --root tests/fixtures/html-second-origin \
  --trust --host 127.0.0.1 --port 8020 --port-tries 0

# 对照：--safe（只给源码，不启动第二 origin）
./target/release/mdview \
  --root tests/fixtures/html-second-origin \
  --safe --host 127.0.0.1 --port 8030 --port-tries 0
```

启动横幅应出现 `html: http://127.0.0.1:8011`；trusted 与 safe 不应出现这一行。

## 复测步骤

### 1. 主 origin 302

```bash
curl -sI http://127.0.0.1:8010/index.html
```

预期：

```text
HTTP/1.1 302 Found
location: http://127.0.0.1:8011/index.html
cache-control: no-store
x-content-type-options: nosniff
```

浏览器打开 `http://127.0.0.1:8010/index.html`，地址栏应变成
`http://127.0.0.1:8011/index.html`，页面显示：

```text
HTML second origin ok
module: ok
storage: ok
fetch: ok
sw: registered
mime: ok
```

页面没有 mdview 顶栏、面包屑、`html-toolbar` 或 iframe。DevTools Console 应为空；
不应出现 `sessionStorage ... sandboxed`、`ServiceWorker ... sandboxed` 或
module CORS 错误。

### 2. 第二 origin 是静态镜像

```bash
curl -sI http://127.0.0.1:8011/app.js
curl -sI http://127.0.0.1:8011/app.css
curl -sI http://127.0.0.1:8011/data.json
curl -sI http://127.0.0.1:8011/_nav?__mdview=nav
curl -sI http://127.0.0.1:8011/_assets/app.js
```

预期：

- `app.js` → `text/javascript; charset=utf-8`
- `app.css` → `text/css; charset=utf-8`
- `data.json` → `application/json; charset=utf-8`
- `/_nav?__mdview=nav` 与 `/_assets/app.js` → `404` 纯文本，没有 mdview JSON/资产
- `/` 与任何目录 → `404`，没有第二套目录 UI

### 3. 源码页与预览 tab

打开 `http://127.0.0.1:8010/index.html?raw=1`：

- 仍是主 origin 的 mdview 源码页；
- 顶部 `预览 / 源码` 两个 tab；
- “预览”链接是 `http://127.0.0.1:8011/index.html`；
- 页面里没有 iframe。

### 4. `--trust` 与 `--safe`

- trusted（8020）：`/index.html` 直接 200 原文，地址栏不变，脚本/存储/SW 正常；
  没有 `html:` 启动行。
- `--safe`（8030）：`/index.html` 是源码页，没有预览 tab，没有第二 origin；
  `/app.js` 等非放行文件 404。

### 5. 端口占用与回退

```bash
# 占用 8011 后，主 origin 仍应能启动，第二 origin 顺延到 8012
./target/release/mdview --root tests/fixtures/html-second-origin \
  --untrusted --host 127.0.0.1 --port 8010 --port-tries 0 --html-port 8011
```

如果 8011 已被占用，横幅打印实际端口（如 8012），302 也指向该端口。

全部候选端口被占用时（可用占位监听模拟），横幅打印
`html: (未启动，未信任 HTML 回退源码页)`；打开 `/index.html` 应得到源码页和提示
“HTML 第二 origin 未启动”，而不是沙箱外壳。

## 自动化覆盖

- `cargo test --lib`：302 Location、Host 端口剥离、第二 origin MIME、目录 404、
  内部路由不可用、SVG CSP、压缩包条目、端口不可用回退。
- `bash tests/selftest-rust.sh`：主 origin 302、第二 origin 原文/MIME/无 CSP、
  源码页预览链接、包内 HTML、`--html-port`。
- `node tests/browser-probe.mjs`：module、sessionStorage、Service Worker、fetch、
  相对 CSS 全部可用；主 origin 无 iframe/外壳。

## 已知限制

- 端口是 origin 边界，不是 cookie 边界；cookie 按 domain 共享。
- 反向代理只转发主端口时，第二端口不可达。
- 端口变化会让第二 origin 的存储与 Service Worker 重新开始。
- 第二 origin 是只读静态镜像：不提供 Markdown 渲染、源码页、目录列表或搜索；
  这些仍在主 origin。
