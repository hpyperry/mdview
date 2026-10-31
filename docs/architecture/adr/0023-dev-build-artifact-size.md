# 开发构建体积：debug = 1 与清理纪律

**Status**: accepted（2026-10-31）。约束 dev profile 与本地构建卫生；操作细节见
[构建产物与磁盘占用](../../guides/build-hygiene.md)。

## 背景

某个长期开发的工作副本里，`target/` 到了 7.7 GB，而交付物
`target/release/mdview` 只有 4.3 MB。分解后：

| 路径 | 大小 | 内容 |
|---|---|---|
| `target/debug/deps` | 4.1 G | 64,099 个 `.o`、219 个 `.rlib`、512 个 `.rmeta` |
| `target/debug/incremental` | 2.8 G | 221 个历史 session 目录 |
| `target/release` | 644 M | 中间产物 |

同一台机器（macOS arm64、8 核、rustc 1.96.0）用独立 `CARGO_TARGET_DIR` 从零构建，
测得：

| 配置 | 仅 `cargo build --locked` | 加 `cargo test --locked --no-run` |
|---|---|---|
| `debug = 2`（默认） | 722 MB | 867 MB |
| `debug = 1` | 588 MB | 708 MB |
| `debug = 0` | 456 MB | 559 MB |

结论有两个，且第二个更重要：

1. `debug = 1` 相对默认只省 **18%**；
2. 7.7 GB 是干净基线的约 **9 倍**，其中约 90% 是 Cargo 不回收的陈旧指纹与
   incremental 会话，而不是调试信息。

一次完整干净重建约 25 秒，所以囤积旧产物的收益远小于直觉。

## 决定

1. **`[profile.dev] debug = 1`**，三方依赖一并降。保留行号表，panic backtrace 仍能
   指到源码行；放弃变量与类型级调试信息。
2. **`[profile.test]` 不单独配置**。它继承 `dev`，`cargo test` 自动跟随。
3. **保留 incremental**。它是 2.8 G 那一类的来源，但也是日常迭代速度的来源；
   靠清理而不是关闭来解决。
4. **不引入 sccache 或共享 `CARGO_TARGET_DIR`**。单机单项目下，外部缓存带来的失效
   规则与 feature 互相踩的成本大于收益。触发条件写在 docs 页，便于将来重开。
5. **不削减依赖**。`zip` 的多解码器、`.7z`、tar 家族属于
   [ADR 0021](0021-archive-format-expansion.md) 的格式范围。
6. **不加体积守卫脚本或 CI 门槛**。阈值随工具链与依赖漂移，假报警会给
   `tests/run-all.sh` 添与业务无关的噪声。
7. **体积问题由文档承载**：`docs/guides/build-hygiene.md` 写基线表、清理命令与
   清理时机。`GLOSSARY.md` 不收构建术语——它是产品词汇表，工程卫生不是领域概念。

## 考虑过的替代方案

- **`debug = 0`**：再省 18 个百分点（相对默认 −36%），但 backtrace 只剩符号名与
  地址。三方 crate 里出的 panic 基本无法定位，省下的 149 MB 不值。
- **只降三方依赖**：本 crate 保持 `debug = 2`、`[profile.dev.package."*"] = 0`。
  自己的代码可调性最好，但整体收益最小，且配置多一层，解释成本高于收益。
- **关闭 incremental**：直接消灭 2.8 G 那一类，但每次改动重编更多，`run-all.sh`
  会明显变慢。体积问题的主因是“不清理”，不是“有缓存”。
- **sccache / 共享 target**：跨项目复用的收益真实，但要维护外部二进制与缓存键；
  当前只有一个项目，ROI 不成立。
- **体积守卫脚本 + CI 门槛**：“超过 N GB 就失败”看起来自动化，实则把一条本地
  习惯固化成会漂移的门槛；工具链升级或依赖增加都会让它误报。
- **削减依赖换体积**：与 ADR 0021 冲突，且本地产物体积不进入交付物。

## 后果

- 所有人和 CI 会触发一次性全量重编，量级 25 秒。
- 需要变量级调试时用 `CARGO_PROFILE_DEV_DEBUG=2 cargo build` 临时覆盖；会生成
  另一套指纹，用完应清理。
- 体积收益 18%，不要把它宣传成主要修复。真正的修复是“超过 2 GB 就 clean”。
- 交付物不变：release profile 仍是 LTO + `codegen-units = 1` + `strip`。

## 验证

- 独立 `CARGO_TARGET_DIR` 干净构建，复现上面的基线表（三档）；
- `cargo test --locked` 全绿；
- `otool -l target/debug/deps/mdview-*.o | grep -c __debug_line` ≥ 1
  （Linux 用 `readelf -S`），确认行号表仍在；`debug = 0` 时该值为 0；
- `node tests/check-doc-links.mjs` 通过。
