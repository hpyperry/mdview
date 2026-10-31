# 开发构建体积与清理 复测文档

- 关联：Issue #29 / PR #N / 无 F-xx（工程卫生修复，不是用户可见功能）
- 夹具根：`tests/fixtures/dev-build-size/`（README-only，没有可服务的夹具文件）
- 启动：不启动服务；用下面的 cargo 命令复测
- 自动化覆盖：`cargo test`、`bash tests/run-all.sh` 覆盖回归；本文的数字与
  debug 信息检查为手工复测

## 背景

`[profile.dev]` 从 Cargo 默认的 `debug = 2` 改为 `debug = 1`，并新增
[构建产物与磁盘占用](../../../docs/guides/build-hygiene.md) 与
[ADR 0023](../../../docs/architecture/adr/0023-dev-build-artifact-size.md)。
这个目录没有夹具，只记录怎么确认改动生效、以及数字对不对。

## 复测步骤

1. 操作：`cargo build --locked`
   预期：构建成功；`du -sh target` 落在 **560–620 MB**（macOS arm64 参考值 588 MB）。

2. 操作：`cargo test --locked --no-run`
   预期：构建成功；`du -sh target` 落在 **690–730 MB**（参考值 708 MB）。

3. 操作：确认行号表还在
   ```bash
   # macOS
   otool -l target/debug/deps/mdview-*.o | grep -c __debug_line
   # Linux
   readelf -S target/debug/deps/mdview-*.o | grep -c .debug_line
   ```
   预期：输出 ≥ 1。若把 `debug` 改成 `0` 再构建同样命令，应为 0——这说明检查本身
   有区分力，不是恒真。

4. 操作：`cargo test --locked`
   预期：88 单元 + 134 渲染兼容 + 27 golden 全绿。`debug = 1` 不改变任何断言。

5. 操作：`node tests/check-doc-links.mjs`
   预期：通过；新文档的交叉链接都能解析。

6. 操作：`du -sh target` 反复构建几次后观察
   预期：同一份依赖图下的重复构建不再显著增长；换依赖或改 profile 才会新增指纹，
   这时按 docs 页的阈值清理。

## 已知限制

- 数字来自 macOS arm64、8 核、rustc 1.96.0、2026-10-31；换平台、换工具链或依赖
  版本都会变。把它当量级参考，不要当 CI 门槛。
- 用 `CARGO_PROFILE_DEV_DEBUG=2` 或不同 `CARGO_TARGET_DIR` 会生成额外指纹，
  体积会与本文数字不同。
- Windows 上没有 `otool`/`readelf`，第 3 步可跳过，或用 `dumpbin /headers` 查
  调试节；该步骤不是发布前的必过项。
- 本文不覆盖 `target/release` 的体积；发布物由 release profile 决定。

## 清理

- `cargo clean` 或 `rm -rf target/debug`；两者都不影响
  `target/release/mdview`（后者只删 debug）。
- 若复测时用了独立的 `CARGO_TARGET_DIR`，用完删除该目录。
