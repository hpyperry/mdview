# Rust 原生重写：单文件可执行、成熟 crate、全平台

**Status**: accepted（2026-10-19）

旧实现是 `mdview.py`：3394 行、只用 Python 标准库、零第三方依赖。新的硬目标是
**编译后的单文件可执行程序**，并且运行时仍然完全离线。Python 可以被 PyInstaller /
Nuitka 打包，但产物仍是解释器加归档、启动慢、跨平台构建麻烦，不符合“编译后”的
第一目标。因此改为 Rust 原生实现。

## 决定

1. **语言与形态**：Rust，单 crate，产物是单个二进制；源码可以分模块。
   版本从 `1.0.0` 升到 `2.0.0`，二进制名 `mdview`。
2. **依赖边界**：允许成熟 crate，不再坚持“零第三方”。首批核心依赖：
   `axum` + `tokio` + `tower-http`（HTTP）、`comrak`（Markdown）、`clap`（CLI）、
   `serde`/TOML（配置）、`walkdir`（搜索）、`directories`（配置目录）。
   `Cargo.lock` 入库，CI 用 `--locked`；运行时不需要网络。
3. **前端资产**：VS Code 的 `markdown.css` / `highlight.css`、完整 highlight.js
   bundle、自有 `mdview.js` 全部用 `include_bytes!` / `include_str!` 嵌进二进制，
   通过 `/_assets/<hash>/…` 提供。运行时没有外部资源文件。
4. **平台**：macOS arm64、Linux x86_64/arm64（musl 静态）、Windows x86_64
   （MSVC + static CRT）。用 CI matrix 构建；不在开发机上硬编码交叉工具链。
5. **服务器契约**：保留旧版 URL 与 CLI（`?download=1`、`?raw=1`、`/search`、
   `--safe`、`--max-preview`、`--port-tries` 等），新增 Trust 与安全级别参数。
6. **旧实现**：本分支用 Rust 实现替换 Python；`mdview.py`、`dist/`、`tools/minify.py`
   与 Python 测试在新实现验收后删除，git 历史保留。

## 考虑过的替代方案

- **PyInstaller / Nuitka 打包现有 Python**：改动最小、旧测试全复用；但产物 10–20 MB、
  启动慢、不是原生二进制，且三大平台分别构建仍然麻烦。与“编译后单文件可执行”的
  目标不符。
- **Go 重写**：交叉编译与静态单文件最省心；但本机没有 Go 工具链，且 Rust 的
  Markdown 生态（comrak）更符合本次“VS Code 语义 + golden 差分”的路线。
- **Zig / C 重写**：体积最小，但 Markdown 解析、HTTP、跨平台字符串处理全要手写，
  开发与维护成本最高。
- **Rust 但零第三方**：保留旧项目的审计身份；代价是把 3.4k 行解析器重写一遍，
  且很难达到 markdown-it 的覆盖度。用户明确选择“优先成熟 crate”。
- **保留 Python 作为对照实现**：过渡期可对拍，但仓库会出现两套代码与两套测试；
  git 历史已经保留旧实现，不需要在分支里双轨。

## 后果

- 二进制显著变大：Rust 运行时 + comrak + 完整 highlight.js + VS Code CSS。
- 构建依赖 crates.io；运行时仍然零网络请求。内网离线审计从“零依赖源码”变成
  “锁定的依赖清单 + 许可证清单 + 单一二进制”。
- ADR 0001 的“零第三方依赖”前提不再成立；其 URL 语义也被 ADR 0005 的严格
  VS Code 语义取代。
- 旧 Python 的 `--max-preview`、MIME 三层判定、端口回退等行为作为产品契约保留，
  实现重新写。

## 验证

- 跨平台 CI 至少构建并跑测试：macOS arm64、Linux x86_64/arm64、Windows x86_64。
- `cargo test --locked` + `bash tests/selftest-rust.sh` 全绿。
- 发布包附 `THIRD-PARTY-NOTICES`（VS Code CSS、highlight.js、Rust crates）。
