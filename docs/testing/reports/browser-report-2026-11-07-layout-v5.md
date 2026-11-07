# 布局 v5（顶栏/缝隙/主岛功能区）与文件工具测试报告（2026-11-07）

- 关联：无 Issue / PR；本地分支 `fix/clean-topbar-page-head` 的 8 个未推送提交 +
  本次测试修复（尚未提交）
- 夹具：[`tests/fixtures/layout-v5/README.md`](../../../tests/fixtures/layout-v5/README.md)（根目录可直接作为 `--root`）
- 类型：browser（浏览器/视觉）+ 后端回归

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| 分支 / commit | `fix/clean-topbar-page-head` @ `e51911d`（+ 工作区测试修复） |
| 平台 | macOS 27.2 / arm64 |
| Rust / Node | rustc 1.96.0 / Node v22.22.3 / npm 11.4.2 |
| 浏览器 | Google Chrome 156.0.8078.80（headless） |
| 被测根 | `tests/fixtures/layout-v5/root`；完整套件另用探针临时夹具 |
| 端口 | 探针随机端口；本地手工实例 8290 |

覆盖的未推送提交：

```
e51911d style: 目录页居中留白，文件预览页淡入转场
2368f07 feat: 目录页支持文件夹打包下载
6d238f6 fix: 裸 URL 不再吞掉后续中文句子
8684383 style: 高亮主题切换为 VS Code Light+ / Dark+
cfdc2f7 feat: 文件页支持全文搜索与复制
9251f1a feat: 面包屑移入缝隙，文件信息与操作回到主岛顶部
17a7d0f feat: 顶栏居中文件名，元信息移入岛屿缝隙
e31970c fix: 顶栏恢复三控件，页面身份回到内容区页头岛
```

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元 | `cargo test --lib` | 99 passed |
| 渲染兼容 | `cargo test --test render_compat` | 137 passed |
| Golden | `cargo test --test golden` | 27 用例通过 |
| 格式 / lint | `cargo fmt --all --check`、`cargo clippy --all-targets -- -D warnings` | 通过 |
| 前端类型 | `npm --prefix web run typecheck` | 通过 |
| 文档链接 | `node tests/check-doc-links.mjs` | 498 条通过 |
| CSS 基线 | `node tests/check-css-baseline.mjs` | 3 个样式表通过 |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=301 FAIL=0 |
| TTY Trust | `bash tests/trust-tty.sh` | PASS=9 FAIL=0 |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=332 FAIL=0 |
| 源码页性能 | `node tests/perf-source.mjs` | 4 项预算全过（114/76/104/74 ms） |
| artifact 冒烟 | `bash tests/smoke-artifact.sh target/release/mdview` | PASS=7 FAIL=0 |
| 汇总 | `bash tests/run-all.sh` | `ALL LOCAL CHECKS PASSED` |

本次没有推送，因此没有远程 CI run；以上为本机完整 `run-all.sh` 结果。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-100 | 目录页留白 | 启动夹具，打开 `/`，视口 1440 | 列表限宽 1100px 居中，左右留白；仅保留面包屑 | 通过 | `../evidence/2026-11-07/layout-dir-centered.png` |
| F-100 | 文件页铺满 + 转场 | 打开 `/guide.md` | 主岛铺满；`card-enter` 240ms 淡入 | 通过 | `../evidence/2026-11-07/layout-file-preview.png` |
| F-100 | 顶栏/缝隙/主岛 | 文档页 1440 | 文件名顶栏居中；面包屑缝隙左对齐；主岛 sticky 栏左操作右信息 | 通过 | 同上 |
| 新增 | 文件内查找 | `/guide.md` 点搜索，输入 `needle` | 计数 1/1，命中高亮，Enter/上下切换，Esc 清除 | 通过 | `../evidence/2026-11-07/file-find-panel.png` |
| 新增 | 源码页查找 | `/code.rs` 搜索 `fn` | 行号栏不命中，命中滚动到视口中间 | 通过 | `../evidence/2026-11-07/source-find-panel.png` |
| 新增 | 复制全文 | `/guide.md` 点复制 | 剪贴板为 Markdown 原文，图标变勾 | 通过 | 探针断言 + 自动化读取剪贴板 |
| 新增 | 文件夹打包下载 | `/` 点文件夹下载 | 全屏遮罩；生成 zip；下载后临时文件删除 | 通过 | `../evidence/2026-11-07/dir-folder-zip-overlay.png` |
| 新增 | 下载按钮对齐/文案 | 目录页悬停文件夹与文件下载 | 同列右缘对齐；浮层只显示「下载」 | 通过 | `../evidence/2026-11-07/dir-folder-download-hover.png` |
| F-22 | 中文裸 URL | `/guide.md` 写入 `http://example.com/　说明` | 空格/全角标点截断，句子不进链接 | 通过 | `render_compat` 新用例 + golden |
| 新增 | 高亮主题 | `/code.rs` 浅色/深色 | VS Code Light+ / Dark+ token | 通过 | `../evidence/2026-11-07/highlight-light.png`、`highlight-dark.png` |

## 发现

### 测试期间修掉的问题

1. **黑盒脚本 20 处旧 UI 断言**：`个项目`、`更新于`、旧岛清单、`html-toolbar`、
   旧压缩包标签、旧编码徽标、`title=下载 …` 等，按新布局更新为
   `gap-crumb` / `island-meta` / `island-actions` / `data-tip` / 面包屑当前项。
2. **浏览器探针 4 处崩溃 + 多处旧选择器**：`.doc-head`/`.source-head`/`.dir-head`/
   `.page-head`、`.page-actions`、`.html-toolbar .seg` 全部迁移到新结构；同时修正
   目录下载区尺寸统计（忽略隐藏的行内「更多」按钮）。
3. **下载完成反馈失效**：`export.ts` 仍查询 `.page-actions a.action`，操作迁到
   `.island-actions` 后监听不到；改为同时覆盖 `.island-actions` 与 `.more-panel`。
4. **打包遮罩关闭按钮提前显示**：`.action` 的 `display:inline-flex` 覆盖了
   `[hidden]`；补 `.zip-dialog .action[hidden] { display: none; }`。
5. **归档目录 `data-islands` 重复 `more`**：归档目录同时命中 island head 与
   directory 分支；改为只在缺少 island head 时补一次。
6. **未推送测试数据脱敏**：U+3000 用例里的真实域名换成 `example.com`。

### 需要人工确认的项

- 转场动画只验证了 `animationName=card-enter`、`240ms` 与 reduced-motion 关闭，
  没有逐帧录屏。
- 文件夹 zip 的临时文件清理用「下载完成后查找 `mdview-zip-*` 为空」验证；
  进程被杀、客户端长时间挂起等异常仅由 `CleanupFile` Drop + token TTL 兜底。

## 覆盖缺口

- 只测 macOS arm64，未在 Linux/Windows 与手机实机复跑；Windows 下“打开中的
  临时文件删除”未实测。
- 浏览器只跑 Chrome 156；Chromium 88 仅由静态 CSS 基线检查，未跑旧内核探针。
- 未做超大文件夹（GB 级/大量小文件）的压力与磁盘满测试。
- 未在反向代理、局域网访问、`--safe` + 文件夹下载组合外的人工场景复测。
- 本版尚未登记新的 `F-xx`（当前沿用 F-100/F-22 作为回归基线），
  `features.md` 与 ADR 0033 需要后续补条目。

## 结论

- 8 个未推送提交在当前实现上全部通过本机完整验收：`run-all.sh` 全绿。
- 测试期间发现的 6 个问题均已修复并复跑。
- 可以进入下一阶段（提交/评审）；建议先补 `features.md` 的 F-xx 登记与
  ADR/布局文档，再决定是否推送。
