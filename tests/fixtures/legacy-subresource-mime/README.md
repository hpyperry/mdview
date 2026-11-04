# 旧浏览器子资源 MIME 复测文档

- 关联：Issue [#41](https://github.com/hpyperry/mdview/issues/41) / PR [#42](https://github.com/hpyperry/mdview/pull/42) / F-76
- 夹具根：`tests/fixtures/legacy-subresource-mime/`（可直接作为 `--root`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/legacy-subresource-mime --trust --port 8003 --port-tries 0
```

- 入口：`/legacy.html`
- 自动化覆盖：`src/server.rs` 的 `fetch_kind` 单元测试；`tests/selftest-rust.sh` 的旧请求头黑盒断言；本页为人工复测

## 背景

HTML 子资源（脚本、样式、JSON、字体）必须拿到真实 MIME；直接导航到文本文件仍应显示
源码页。mdview 用 `Sec-Fetch-Dest` 判断请求上下文，没有时退化看 `Accept`。

Chrome 76 之前的版本不发 `Sec-Fetch-*`，classic script 与 `fetch()` 只发
`Accept: */*`，旧逻辑会把它当成导航，返回 `text/html` 源码页。浏览器的严格 MIME
检查随后拒绝执行脚本：

```
Refused to execute script from '.../docs.js' because its MIME type ('text/html') is not executable
Uncaught TypeError: window.OpenCollection is not a constructor
```

第二条是脚本没执行导致的连带错误。

## 复测步骤

1. 操作：用普通现代浏览器打开 `/legacy.html`。
   预期：页面显示 `ok`，脚本与样式正常加载。

2. 操作：用旧 Chrome（或重放旧请求头）打开 `/legacy.html`。
   预期：仍然显示 `ok`，控制台没有 MIME 拒绝。

3. 操作：重放旧客户端脚本请求：

   ```bash
   curl -s -o /dev/null -w '%{content_type}\n' \
     -H 'Accept: */*' -H 'Referer: http://127.0.0.1:8003/legacy.html' \
     http://127.0.0.1:8003/docs.js
   ```

   预期：`text/javascript; charset=utf-8`，响应体是 `window.OpenCollection` 开头的原始 JS。

4. 操作：重放旧客户端 JSON 请求：

   ```bash
   curl -s -o /dev/null -w '%{content_type}\n' \
     -H 'Accept: */*' http://127.0.0.1:8003/data.json
   ```

   预期：`application/json; charset=utf-8`。

5. 操作：模拟浏览器导航：

   ```bash
   curl -s -H 'Accept: text/html,application/xhtml+xml' \
     http://127.0.0.1:8003/docs.js | head -c 120
   ```

   预期：返回 mdview 源码页（HTML，含 `<h1>docs.js</h1>`），不是原始 JS。

6. 操作：直接访问 `/legacy.html` 的源码页与目录页。
   预期：HTML 仍按 trusted 原文返回；目录里 `docs.js` 仍可点开源码页。

## 自动化覆盖

- `cargo test`：`fetch_kind_handles_legacy_wildcard_accept`、`fetch_kind_prefers_fetch_metadata`
  覆盖 wildcard Accept、`Sec-Fetch-Mode`、`text/html` 导航与 `.md`/`.txt` 不误判。
- `bash tests/selftest-rust.sh`：旧请求头下 `docs.js` 的 MIME 与原始字节、`legacy.json`
  的 MIME、以及 `docs.js` 的 `text/html` 导航仍为源码页。
- 现有浏览器探针使用新 Chrome，天然带 `Sec-Fetch-Dest`，覆盖不到这条分支。

## 已知限制

- 真实浏览器版本未知；本修复按“无 `Sec-Fetch-*` + `Accept: */*`”的旧请求形态模拟。
- 只对文本子资源扩展名兜底；`.md`/`.txt` 的 `fetch()` 仍按导航处理，避免破坏源码页行为。
- 如果旧客户端连 `Accept` 都不发，仍按导航处理（保持源码页行为）；只有明确的
  `Accept: */*` 才走扩展名兜底。
- 二进制资源（图片、字体、PDF）本来就走 `Kind::Binary` 原文，不经过这条分支。

## 清理

- 停止临时服务并释放端口（8003）。
- 夹具目录没有生成物；如需清理构建产物，按
  [构建卫生](../../../docs/guides/build-hygiene.md) 处理 `target/`。
