# 静态服务器兼容手动夹具

用于手动验证内部 URL 查询参数消歧、文件尾斜杠、Markdown 扩展名与目录 index 非目标。

## 启动

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/static-parity --trust --port 8004 --port-tries 0
```

打开 `http://127.0.0.1:8004/`。

## 入口与预期

| 入口 | 预期 |
|---|---|
| `/search` | 打开真实的 `search` 文件源码页，不是搜索页 |
| `/search?__mdview=search&q=hello` | 搜索页；同名文件不影响内部搜索 |
| `/_nav` | 打开真实的 `_nav` 文件源码页 |
| `/_nav?__mdview=nav` | 返回导航 JSON |
| `/_assets/app.css` | 打开真实的 `_assets/app.css` 源码页 |
| `/_assets/app.css?__mdview=asset` | 返回内嵌 CSS（`text/css`） |
| `/b.txt/`、`/b.txt%2f` | 404 |
| `/b.txt` | 源码页 200 |
| `/a.markdown` | Markdown 渲染页，页头显示编码 |
| `/a.mdx` | 源码页，类型标签为 MDX |
| `/sub/` | 目录列表；列出 `index.html`，但不自动作为首页 |

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8004/b.txt/
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8004/search
curl -s http://127.0.0.1:8004/search | head
curl -s http://127.0.0.1:8004/_nav?__mdview=nav | head -c 200
```

## 自动化

`tests/selftest-rust.sh` 从本目录复制这些文件；内部 URL/尾斜杠/Markdown 扩展名
断言在 `src/server.rs` 与黑盒测试里。
