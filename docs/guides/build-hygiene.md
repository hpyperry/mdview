# 构建产物与磁盘占用

这篇讲本机 `target/` 为什么会长到 GB 级、dev profile 的取舍，以及什么时候该清。
交付物体积是另一回事：`target/release/mdview` 通常 4–5 MB，见
[安装、运行与 Trust](install.md)。

## 结论

`target/` 是本地构建副产物：不进 git、不进发布 artifact、不影响运行时。它变大是
Cargo 的设计，不是产品缺陷。仓库只对 dev profile 做了一个选择——`debug = 1`——剩下
靠清理节奏。

把这件事说清楚的原因：一次干净构建只有几百 MB，但 Cargo **从不回收陈旧指纹**。
依赖、feature 或 profile 一变就产生新的 16 位哈希，旧产物整套保留；实测某个长期
开发的工作副本里攒了 49 套指纹、221 个 incremental 会话，`target/` 到 7.7 GB。

## 实测基线

环境：macOS arm64（Apple Silicon，8 核）、rustc 1.96.0、cargo 1.96.0、2026-10-31。
每次都用独立的 `CARGO_TARGET_DIR` 从零构建。

| 配置 | 仅 `cargo build --locked` | 再加 `cargo test --locked --no-run` |
|---|---|---|
| `debug = 2`（Cargo 默认） | 722 MB | 867 MB |
| `debug = 1`（本仓库） | 588 MB | 708 MB |
| `debug = 0` | 456 MB | 559 MB |

这些数字随依赖、工具链与平台变化，只当量级参考，不当硬门槛。同一台机器一次完整
干净重建约 25 秒。

## dev profile 为什么是 `debug = 1`

`debug = 1` 保留行号表，丢掉变量与类型信息。效果：

- panic backtrace 仍然指到 `src/server.rs:1234`，日常排查够用；
- 相比默认 `debug = 2` 省约 18%；
- 相比 `debug = 0` 多约 25%，但 `debug = 0` 的 backtrace 只剩符号名，三方 crate
  里出的 panic 基本没法定位。

`[profile.test]` 不单独配置——它继承 `dev`，`cargo test` 自动跟随。

需要变量级调试时临时覆盖：

```bash
CARGO_PROFILE_DEV_DEBUG=2 cargo build
```

注意这会生成**另一套**指纹，用完记得清（见下一节）。

## 什么时候该清

```bash
du -sh target                              # 当前占用
find target/debug/deps -maxdepth 1 -name 'mdview-*' \
  | sed -E 's#.*/mdview-([0-9a-f]{16}).*#\1#' | sort -u | wc -l   # 指纹套数
ls target/debug/incremental | wc -l        # incremental 会话数
```

经验阈值：`target/` 超过 2 GB，或指纹套数明显多于 2–3 套，就该清一次。这里重建只要
25 秒，没有理由为了“万一回滚能秒编”囤几十套产物。

## 清理命令

```bash
cargo clean                # 清掉所有 profile 的产物，之后一次全量重建
rm -rf target/debug        # 只清 debug，保留 target/release/mdview
cargo clean -p mdview      # 只清本项目 crate 的产物
```

`cargo clean` 不会删除 `~/.cargo/registry` 里的源码缓存，重编不需要重新下载。
`tools/spike/` 下的探针项目有自己的 `target/`，不常用时可以直接删目录。

## 为什么现在不引入跨项目缓存

`sccache` 或共享 `CARGO_TARGET_DIR` 能让依赖产物跨项目复用，但代价是额外的外部
二进制、缓存失效规则，以及 feature 集合不同时的互相踩。当前是单机单项目，收益不抵
复杂度。出现下面任一情况时值得重新评估：

- 同时维护多个 worktree，或频繁在两个分支间来回构建；
- CI 冷启动构建时间成为瓶颈；
- 同一 feature 集合的项目变多。

## 为什么不动依赖图

体积想再降就得砍依赖，而 `zip` 的多解码器、`.7z`、tar 家族属于
[ADR 0021](../architecture/adr/0021-archive-format-expansion.md) 明确的格式范围。
为了几十 MB 本地产物牺牲格式支持不划算。

## 相关

- [ADR 0023：开发构建体积与 debug 级别](../architecture/adr/0023-dev-build-artifact-size.md)
- [安装、运行与 Trust](install.md)：发布物的构建与跨平台 target
