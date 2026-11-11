# 能力降级兜底测试报告（2026-11-11）

- 关联：F-25 / F-53 / F-74 / F-03；本地分支 `fix/wide-layout`（Issue / PR 待建）
- 夹具：`tests/fixtures/capability-fallbacks/README.md`
- 类型：browser（复制/图片放大）+ CLI 默认值

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 分支 / commit | `fix/wide-layout`（本地提交，未推送） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 157.0.8103.39（headless / CDP） |
| 被测根 | `docs/`（截图）/ 探针夹具 |
| 端口 | 8321（截图）/ 探针随机端口 |

## 改动

1. **复制回退**：`copyText` 在 `navigator.clipboard.writeText` 被拒（或非安全上下文）
   时回退到 `document.execCommand('copy')`；`filetools` 复用同一个函数。文件复制失败
   时除了按钮提示，还在页面底部弹出 2.4 秒的 `role="status"` toast。
2. **图片放大兜底**：`<dialog>.showModal` 不可用时不再 `preventDefault`，让 `.zoom`
   链接按普通链接直接打开图片；effect 中也做了保护。
3. **默认监听**：`--host` 默认值从 `0.0.0.0` 改为 `127.0.0.1`；局域网访问需显式
   `--host 0.0.0.0`。

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 101 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=303 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=357 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | ok |
| 文档链接 | `node tests/check-doc-links.mjs` | ok |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

新增断言：

- 把 `navigator.clipboard.writeText` 替换为 reject、`execCommand` 记为成功：
  代码块复制仍显示“已复制”，且 `execCommand` 被调用；
- `execCommand` 返回 false 时，点击文件复制会出现包含“复制失败”的 `.toast`；
- 把 `dialog.showModal` 置空后点击图片：应用不再阻止默认行为，遮罩不打开；
- `src/cli.rs` 的 `defaults_are_stable` 断言默认 host 为 `127.0.0.1`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-53 | 复制回退 | 拒绝 `clipboard.writeText`，点代码块复制 | 回退 `execCommand`，显示“已复制” | 通过 | 探针 |
| F-74 | 失败提示 | `execCommand` 返回 false，点文件复制 | 底部 toast 显示“复制失败…” | 通过 | [`../evidence/2026-11-11/copy-failure-toast.png`](../evidence/2026-11-11/copy-failure-toast.png) |
| F-25 | 放大兜底 | 删除 `showModal`，点图片 | 不拦截点击，图片直接打开 | 通过 | 探针 |
| F-03 | 默认监听 | `cargo test --lib` | host 默认 `127.0.0.1` | 通过 | 单元测试 |

## 发现

- `execCommand('copy')` 已被标记为废弃，但在 Chromium 88+ 仍可用；它只在剪贴板 API
  被拒时作为兜底，成功路径仍走 `navigator.clipboard`；
- 不支持的 `<dialog>` 浏览器里，图片放大退化为“打开图片原图”，比点击无反应好；
- 默认监听改为 `127.0.0.1` 后，从局域网访问必须显式 `--host 0.0.0.0`，这是有意的
  安全默认值变化。

## 覆盖缺口

- 没有在 Safari/旧 WebView 上实机验证 `<dialog>` 兜底；Chromium 88 有 `showModal`，
  探针通过删除实例方法模拟不支持环境。
- `execCommand` 在部分企业浏览器/权限策略下也可能被禁，届时复制会走失败提示。
- 默认监听的局域网不可达只做了 `127.0.0.1` 单测与启动日志核对，未在第二台设备上
  验证。

## 结论

通过。剪贴板被拒、`<dialog>` 不可用两种降级路径都有可用的兜底与明确反馈；
默认监听改为 `127.0.0.1`，安全默认值不再暴露到局域网。自动化与本机全量验收通过。
