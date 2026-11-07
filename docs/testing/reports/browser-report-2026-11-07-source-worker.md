# 源码页铺满与大块高亮 Worker 测试报告（2026-11-07）

- 关联：PR（待创建）/ 上一版 Issue [#74](https://github.com/hpyperry/mdview/issues/74)
- 夹具：`tests/fixtures/layout-v5/README.md`（大源码场景以仓库根为 `--root`）
- 类型：browser（浏览器/视觉）+ 后端回归

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `fix/source-page-fill` @ `9e8994d`（+ 本次文档提交） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `tests/fixtures/layout-v5/root`；大源码用仓库根 |
| 端口 | 8290 / 探针随机端口 |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 100 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=303 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=338 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

新增断言：大单块不分块、Worker 请求出现、Worker 后 `code.hljs`、
`worker-src 'self'` CSP、`hlworker.js` 资产 200/MIME、1MB 少行文件不出现分块提示。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| 新增 | 短源码铺满 | `code.rs?raw=1`，1440×900 | 代码背景/行号栏到主岛底部，无提示 | 通过 | `../evidence/2026-11-07/source-page-fill.png` |
| 新增 | 1MB 少行文件 | `assets/highlight.min.js?raw=1` | 不分块、无“文件较大”；Worker 高亮 | 通过 | `../evidence/2026-11-07/source-worker-highlight.png` |
| 新增 | Worker 性能 | 同页，记录 DOM 完成时间 | 约 0.5s，滚动不阻塞 | 通过 | 高亮约 479ms、52,927 span |
| 回归 | 大源码分块 | `/big.txt`、`/big.rs` | 仍分块、可见块逐个高亮、行锚点正常 | 通过 | 探针 |
| 回归 | 高亮主题 | 浅/深切换 | VS Code Light+/Dark+ token | 通过 | 探针 + 既有证据 |

## 发现

- 初次实现把 `.source-wrap` 的 `min-height` 设为 0，长源码变成内层滚动容器，
  “滚动后继续着色”失败；移除该属性后恢复 `.content-card` 单滚动容器。
- Worker 路由需要在 `MDVIEW_WEB_PREBUILT` 发布构建中也被复制；`build.rs` 已补齐
  `hlworker.js`。
- Markdown 超大围栏块仍保留“高亮已关闭”，未迁移。

## 覆盖缺口

- 未在 Linux/Windows 实机跑 Worker；CI 的 Ubuntu/macOS 浏览器探针覆盖同源
  Worker 加载。
- 3 秒超时路径没有构造真实阻塞输入，只在代码层验证回收逻辑。
- 未测 10 MB 以上单块、低端 CPU 与省电模式。

## 结论

源码页两种观感问题和 1 MB 文件无高亮均解决；全量本机验收通过。
