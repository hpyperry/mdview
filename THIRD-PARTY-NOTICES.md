# Third-party notices

mdview 的源码是自有代码；交付二进制嵌入了以下第三方资产/库。

## 前端资产

- **highlight.js 11.11.1** — BSD-3-Clause
  - 文件：`assets/highlight.min.js`（完整语言集，经 esbuild 打包压缩）
  - 上游：https://github.com/highlightjs/highlight.js
- **Preact 10.29.8** — MIT
  - 文件：`web/src/islands/*` 经 esbuild 打包进 `app.js`
  - 上游：https://github.com/preactjs/preact
- 构建期依赖：esbuild 0.25 — MIT；TypeScript 5.9 — Apache-2.0（均不嵌入产物）
- **VS Code 1.142.0 `markdown-language-features/media/highlight.css`** — MIT
  - 文件：`assets/highlight.css`
  - 其中 vs / vs2015 配色来自 highlight.js（BSD-3-Clause）
- **VS Code 1.142.0 `markdown-language-features/media/markdown.css`** — MIT
  - 文件：`assets/markdown.css`
  - 上游：https://github.com/microsoft/vscode

## Rust crates

运行时直接依赖（完整传递依赖与版本见 `Cargo.lock`）：

| crate | 许可证 |
|-------|--------|
| `anyhow` | MIT OR Apache-2.0 |
| `axum` | MIT |
| `chardetng` | Apache-2.0 OR MIT |
| `clap` | MIT OR Apache-2.0 |
| `comrak` | BSD-2-Clause |
| `directories` | MIT OR Apache-2.0 |
| `encoding_rs` | MIT OR Apache-2.0 |
| `filetime` | MIT OR Apache-2.0 |
| `flate2` | MIT OR Apache-2.0 |
| `mime_guess` | MIT |
| `percent-encoding` | MIT OR Apache-2.0 |
| `rand` | MIT OR Apache-2.0 |
| `serde` | MIT OR Apache-2.0 |
| `sevenz-rust2` | Apache-2.0 |
| `tar` | MIT OR Apache-2.0 |
| `tempfile` | MIT OR Apache-2.0 |
| `time` | MIT OR Apache-2.0 |
| `tokio` | MIT |
| `tokio-util` | MIT |
| `toml` | MIT OR Apache-2.0 |
| `walkdir` | MIT OR Unlicense |
| `zip` | MIT |

开发依赖：`tower`（MIT，仅测试）。压缩包传递依赖包含 `bzip2-1.0.6`
（bzip2/libbzip2 License）与 `ppmd-rust`（CC0-1.0 OR MIT-0）等宽松许可证。

## 许可证状态

本仓库自身采用 **MIT**（见 `LICENSE`，Copyright © 2026 hpy）。
发布前用 `cargo deny` / `cargo license` 复核传递依赖的许可证；
`tools/spike/` 里的 markdown-it / parse5 等 Node 依赖只用于开发探针，
不进入交付二进制。
