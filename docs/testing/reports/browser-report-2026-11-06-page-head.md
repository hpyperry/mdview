# 统一页头（PageHead）测试报告（2026-11-06）

- 关联：Issue [#65](https://github.com/hpyperry/mdview/issues/65) / PR（待建）/ F-29、F-45、F-95
- 夹具：`tests/fixtures/page-head/README.md`（可直接作为 `--root`）
- 类型：browser（浏览器/视觉）

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-06 |
| 分支 / commit | `refactor/page-head-component`（PR 待建） |
| 平台 | macOS arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `tests/fixtures/page-head` |
| 启动 | `target/release/mdview --root tests/fixtures/page-head --trust --port 8004 --port-tries 0` |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 / 集成 | `cargo test` | 95 + 134 + 27 passed |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=292 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=322 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算通过 |
| artifact 冒烟 | `bash tests/artifact-smoke.sh` | PASS=7 FAIL=0 |

全量入口：`bash tests/run-all.sh` → `ALL LOCAL CHECKS PASSED`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-45 | Markdown 页头 | 1440px 打开 `/doc.md` | 面包屑 + 文件名 H1 + `Markdown`/大小/编码/更新时间徽标；右侧源码/下载/导出；正文 H1 在下方 | 通过 | [F-45_page-head-doc.png](../evidence/2026-11-06/F-45_page-head-doc.png) |
| F-29 | 源码页头 | 打开 `/doc.md?raw=1` | 与 Markdown 页头同结构；徽标增加行数；右侧仅保留预览，不再有下载 | 通过 | [F-45_page-head-source.png](../evidence/2026-11-06/F-45_page-head-source.png) |
| F-45 | 目录页头 | 打开 `/` | 面包屑 + 目录名 H1 + 项目数徽标 | 通过 | [F-45_page-head-dir.png](../evidence/2026-11-06/F-45_page-head-dir.png) |
| F-45 | 搜索页头 | 1440px 打开搜索页 | 查询标题 + 文件数/结果数徽标；搜索表单在右侧同一行 | 通过 | [F-45_page-head-search.png](../evidence/2026-11-06/F-45_page-head-search.png) |
| F-45 | 窄屏搜索页头 | 800px 打开搜索页 | 表单换到标题下方，保持紧凑，不被挤到页面底部 | 通过 | [F-45_page-head-search-800.png](../evidence/2026-11-06/F-45_page-head-search-800.png) |
| F-95 | 下载完成反馈 | 点击文档页「下载」 | 图标换成绿色对勾，`aria-disabled=true`；500ms 内再次点击被阻止；约 500ms 后恢复原图标 | 通过 | 浏览器探针断言；图标状态见 [F-95_toolbar-download-done.png](../evidence/2026-11-06/F-95_toolbar-download-done.png) |
| F-95 | 导出图片完成反馈 | 点击「导出图片」 | 生成完成后图标换成绿色对勾、按钮短暂 `disabled`；只显示“图片已导出”约 500ms；随后恢复 | 通过 | 浏览器探针断言（MutationObserver + disabled/status） |

浏览器探针新增/更新断言：

- 文档页：`.doc-head h1` 为文件名；`.page-meta .badge` 至少 3 个且含 `Markdown`；
  操作依次为源码/下载/导出图片/导出 PDF。
- 源码页：标题文件名、类型标签、信息徽标、预览按钮与面包屑。
- 目录页：目录名标题与“个项目”徽标；压缩包仍显示 ZIP/JAR/EPUB/CBZ 标签。
- 搜索页：查询标题、文件数/结果数徽标、右侧表单、800px 紧凑布局。
- 原有导出/下载完成图标、打印隐藏页头、面包屑与几何断言继续通过。

## 发现

- 四类页头已使用同一 `PageHead` 结构；Markdown 页头新增文件名与徽标后，与源码页
  视觉一致，正文标题不再被 `sr-only` 副本重复。
- 800px 搜索页最初因 `.grow` 的 `flex-basis: 420px` 在纵向布局里变成高度，表单被
  推到页面底部；已改为 `flex: 0 1 auto` 并由探针钉住。
- 页头 CSS 已收敛到 `.page-head` / `.page-head-inner` / `.page-meta` /
  `.page-actions` 一套；删除了 `article-toolbar`、`doc-meta`、`source-tags`、
  `dir-head-main`、`search-head-inner` 等旧规则。
- 下载/导出完成反馈改为约 500ms 的完成图标 + 禁用窗口，防止连续点击；导出成功后
  只短暂显示“图片已导出”，不再使用“图片已生成”长提示；错误提示（过长/失败）仍保留。

真实鼠标连点验证（1440px，下载按钮中心点，两次点击间隔 150ms）：

```text
Network ?download=1 requests: 1
第一次点击后:   is-done=true, aria-disabled=true, pointer-events=none
第二次点击时:   is-done=true, aria-disabled=true, pointer-events=none
再等 600ms 后: is-done=false, aria-disabled=null, pointer-events=auto
```

说明第二次点击命中不到链接，只产生一次下载请求；500ms 窗口结束后才恢复。

## 覆盖缺口

- 仅验证 Chromium 156；Firefox/Safari 未人工复测。
- Chromium 88 只跑 CSS 基线 lint 与既有旧内核回退夹具，未在真机重跑页头截图。
- 压缩包页头只由浏览器探针断言标签，未单独截图。
- 信任页/错误页是专用面板，不在 PageHead 范围内，未做视觉改动。

## 结论

- 通过。四类页面共用服务端 `PageHead`，F-29/F-45 验收项与浏览器探针、全量本地
  套件均通过；可以进入 PR 评审。
