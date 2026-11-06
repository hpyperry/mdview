# 渐进搜索与扫描上限测试报告（2026-11-07）

- 关联：Issue [#66](https://github.com/hpyperry/mdview/issues/66) / PR（待建）/ F-99
- 夹具：`tests/fixtures/search-progressive/README.md`（root 为 `tests/fixtures/search-progressive/root/`）
- 类型：browser（浏览器/视觉）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `refactor/page-head-component`（PR 待建） |
| 平台 | macOS arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `tests/fixtures/search-progressive/root` |
| 启动 | `target/release/mdview --root tests/fixtures/search-progressive/root --trust --port 8006 --port-tries 0` |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 / 集成 | `cargo test` | 96 + 134 + 27 passed |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=292 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=330 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/artifact-smoke.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-99 | 首批上限 | 打开 `/search?__mdview=search&q=batchneedle` | 只显示 40 个文件组，底部出现“已扫描前 40 个文件”和「继续搜索」 | 通过 | [F-99_search-progressive-1440.png](../evidence/2026-11-07/F-99_search-progressive-1440.png) |
| F-99 | 继续搜索追加 | 点「继续搜索」 | 按钮显示“正在加载…”，剩余 5 个文件追加到末尾；不重复；计数变成 45 个文件 / 45 条结果；按钮消失 | 通过 | 浏览器探针断言 |
| F-99 | 无 JS 回退 | 禁用 JS 后点「继续搜索」 | 直接导航到 `cursor=...` 的下一批页面，结果仍可读 | 通过 | 浏览器探针无 JS/链接断言 |
| F-99 | 大目录上限 | 在 `--root /Users/hpy` 搜索宽关键词 | 请求在约 1.2 秒或 2000 个文件内返回，不再等全树扫完 | 通过 | 手动观察；服务端常量与单元测试 |
| F-99 | cursor 不重复 | 连续两批 | 第一批 40、第二批 5，并集 45，无重复 | 通过 | `search_resumes_in_batches_from_cursor` |

## 发现

- 原先搜索会先遍历整个 root 再返回；现在每批有 2000 文件/1.2 秒/40 组/200 条/单文件 5 条预算。
- `WalkDir` 目录顺序在不同请求间不保证一致，cursor 按条目序号续扫会重叠；已加
  `.sort_by_file_name()` 固定顺序，并用单元测试钉住 40 + 5 无重复。
- 有 JS 时搜索结果追加并更新页头计数；无 JS 时「继续搜索」是普通链接。
- 首批没有结果但仍有更多文件时，页面提示已扫描文件数并可继续，而不是直接显示
  “没有找到”。

## 覆盖缺口

- 仅 Chromium 156；Firefox/Safari 未人工复测。
- 超大目录的后续批次仍要遍历到 cursor，未做持久化 walker；只验证了上限与正确性。
- 无 JS 的继续页只显示下一批，不保留上一批；这是有意的降级行为。
- 结果只在批内排序，追加后不做全局排序。

## 结论

- 通过。搜索不再一次扫完整棵树，首屏有硬上限并可渐进追加；F-99 与全量本地套件
  通过，可以进入 PR 评审。
