# 面包屑返回文件位置测试报告（2026-11-11）

- 关联：F-09；本地分支 `fix/wide-layout`（Issue / PR 待建）
- 夹具：`tests/fixtures/return-position/README.md`
- 类型：browser（目录导航）+ 后端回归

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-11 |
| 分支 / commit | `fix/wide-layout`（本地提交，未推送） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 157.0.8103.39（headless / CDP） |
| 被测根 | `tests/fixtures/return-position/root`（24 个短文档） |
| 端口 | 8305（截图）/ 探针随机端口 |

## 问题与修改

从目录点击文件进入预览后，点面包屑回到目录，列表总是回到顶部，不会停在刚刚
预览的文件行；长目录里需要重新找文件。

修改分三层：

1. 目录页的文件行增加 `data-file="<name>"`；
2. 文件页（Doc / Source）点面包屑时，把 `{dir, file}` 记到 `sessionStorage`
   （`filetools` 岛监听最后一个面包屑链接）；面包屑 URL 保持普通目录地址，
   不再写 `#file=`；
3. 目录页 `dirrows` 岛读取这条记录：有 `file` 时 `scrollIntoView({ block: 'center' })`，
   加上 `is-return` 类并保持约 2.2 秒；没有 `file`（浏览器后退）时恢复离开前的
   `scrollTop`。

无 JS 或禁用存储时只回到目录顶部，属于渐进增强。

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 101 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=303 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=354 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | ok |
| 文档链接 | `node tests/check-doc-links.mjs` | ok |
| 汇总 | `bash tests/run-all.sh` | ALL LOCAL CHECKS PASSED |

新增断言：

- 根目录 / 子目录文件的面包屑链接仍是 `/` 与 `/sub/`，URL 不含文件名；
- 点击面包屑后回到目录且 `location.hash` 为空；
- 返回后目标行带 `is-return` 且在视口内；
- 长目录返回时 `scrollTop > 0` 且目标行在视口内；
- 浏览器后退恢复离开目录时的滚动位置；
- 单元测试覆盖文件行 `data-file`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-09 | 文件页 | 打开 `/item-20.md` | 面包屑根链接仍为 `/`，地址栏没有文件名 | 通过 | [`../evidence/2026-11-11/return-position-file.png`](../evidence/2026-11-11/return-position-file.png) |
| F-09 | 返回目录 | 点击面包屑的根目录 | 回到 `/`（无 hash），列表滚动到 item-20 行并高亮 | 通过 | [`../evidence/2026-11-11/return-position-returned.png`](../evidence/2026-11-11/return-position-returned.png) |
| F-09 | 视口 | 1440×900，24 行列表 | `scrollTop=590`，item-20 行 581–637 落在主岛 100–884 内 | 通过 | CDP 断言 |
| F-09 | 子目录 | `/sub/page.md`（探针夹具） | 父链接 `/sub/`；返回后滚动到 page.md 行 | 通过 | 探针 |

## 发现

- 面包屑 URL 不写文件名，定位完全依赖 `sessionStorage`；禁用存储时退化为回到
  目录顶部，不会产生错误页面；
- `scrollIntoView({ block: 'center' })` 在接近列表底部时会被滚动范围夹紧，
  目标行仍在视口内，属于预期；
- 目标行的 `is-return` 高亮使用 `--accent-soft` + `--accent` 边框，2.2 秒后淡出。

## 覆盖缺口

- 没有单独为压缩包内文件的返回路径出截图；面包屑与来源文件记录走同一套逻辑，
  探针覆盖子目录场景。
- 后退恢复依赖 `sessionStorage`，隐私模式/禁用存储时只退化为浏览器默认行为。
- 没在 Safari/Firefox 实机验证 `scrollIntoView` 与片段解码；Chromium 88 的
  `scrollIntoView` 选项自 61 起可用。
- 无 JS 场景不恢复位置，属预期降级。

## 结论

通过。文件预览的面包屑 URL 保持干净；点面包屑返回目录时列表滚动到来源文件并在
2.2 秒内高亮，浏览器后退恢复原滚动位置；根目录与子目录文件都覆盖，长列表在
1080p 下也能直接落位。
F-09 验收口径、夹具与浏览器探针已同步。
