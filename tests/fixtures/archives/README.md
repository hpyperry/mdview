# Archive manual fixture

用于手动验证压缩包虚拟目录。

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/archives --trust --port 8002 --port-tries 0
```

打开：

- `http://127.0.0.1:8002/sample.zip/`
- `http://127.0.0.1:8002/sample.tar.gz/`
- `http://127.0.0.1:8002/sample.7z/`

预期：

- 包根页显示包名、格式、大小、条目数和“下载压缩包”；
- `docs/` 可进入，`docs/a.md` 走 Markdown 渲染，图片链接保留为
  `/sample.zip/docs/pic.png`；
- `docs/page.html` 在 trusted 根直接原文；`--untrusted` 时走沙箱外壳；
- `?raw=1` 看源码，`?download=1` 下载条目或整包；
- `inner.zip` 是嵌套包，按普通文件下载，不递归解压；
- `--safe` 下压缩包整体 404。

自动化覆盖在 `src/server.rs` 的 archive 测试和
`tests/selftest-rust.sh` / `tests/browser-probe.mjs`。
