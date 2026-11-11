# performance 复测夹具

对应 2026-11-11 的资源加载与压缩优化（A 组）：按需加载 highlight.js、gzip/brotli、
vendor CSS 构建时压缩、旧外壳 CSS 清理、meta description。README-only，复用仓库根
和 `docs/` 内容。

## 启动

```bash
cargo build --release
./target/release/mdview --root . --trust --host 127.0.0.1 --port 8306 --port-tries 0
```

## 复测入口

| 场景 | 操作 | 预期 |
|---|---|---|
| 无代码文档 | 打开 `/docs/README.md` | HTML 不引用 `highlight.js`/`highlight.css`；正文可读 |
| 目录页 | 打开 `/` | 不加载 highlight.js；总传输约 40 KB |
| 含代码文档 | 打开 `/docs/manual/README.md` | 引用并把代码高亮 |
| 源码页 | 打开 `/docs/manual/README.md?raw=1` | 引用 highlight.js，行号与高亮正常 |
| HTML 压缩 | `curl -s -D - -o /dev/null -H 'Accept-Encoding: gzip' http://127.0.0.1:8306/docs/README.md` | `content-encoding: gzip`、`vary: accept-encoding` |
| CSS Brotli | `curl -s -D - -o /dev/null -H 'Accept-Encoding: br' 'http://127.0.0.1:8306/_assets/app.css?__mdview=asset'` | `content-encoding: br` |
| 二进制不压缩 | 同上，请求 `/docs/manual/images/01-directory.png` | 无 `content-encoding` |
| Lighthouse | 见测试报告命令 | 目录页性能 100；手册桌面 95、移动 76；SEO 100 |

自动化覆盖：`tests/selftest-rust.sh`（条件高亮、gzip/br、Vary、PNG 不压缩）、
`tests/browser-probe.mjs`（各页面是否加载 highlight），以及 `cargo test --lib`
（HTML 条件引用）。

关联测试报告：
[`docs/testing/reports/test-report-2026-11-11-performance.md`](../../../docs/testing/reports/test-report-2026-11-11-performance.md)。

视觉回归证据：
[`docs/testing/evidence/2026-11-11/`](../../../docs/testing/evidence/2026-11-11/)。
