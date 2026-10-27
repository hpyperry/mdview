# 浏览器验收：压缩包预览（2026-10-21）

> 历史快照：本报告的 198 项黑盒计数记录当时状态；当前计数见
> [`selftest.md`](selftest.md)（82/238/210）。

**被测版本**：mdview 2.0.0 工作树（ADR 0016 实现）
**验收方式**：release 二进制 + headless Chrome；实际页面截图 + 自动探针
**结论**：ZIP / tar.gz / 7z 虚拟目录、包内 Markdown/HTML/源码/图片、整包与条目下载、
嵌套包不递归、移动端布局均通过；全量浏览器探针 `203` 项、黑盒 `198` 项全绿。

## 环境

| 项 | 值 |
|---|---|
| 平台 | macOS 27.0.0 arm64 |
| Rust / Node | Rust 1.96.0 / Node 22.22.3 |
| 浏览器 | Google Chrome 155.0.8059.85 |
| trusted 服务 | `http://127.0.0.1:18201`，`--root tests/fixtures/archives --trust` |
| untrusted 服务 | `http://127.0.0.1:18202`，同一 root，`--untrusted` |
| 视口 | 1280×1000 桌面、390×900 移动 |
| 证据 | [`evidence/2026-10-21/`](evidence/2026-10-21/) |

## 覆盖结果

| 编号 | 功能 / 页面 | 操作与预期 | 结果 | 证据 |
|---|---|---|---|---|
| V1 | F-81 / F-85 包根页 | `/sample.zip/`：包名、`ZIP · 大小 · 条目数`、下载压缩包；`docs/` 可进入，`inner.zip` 是普通文件 | 通过 | [F-81 root](evidence/2026-10-21/F-81_archive-root.png) |
| V2 | F-81 包内 Markdown | `/sample.zip/docs/a.md`：Markdown 渲染，相对图片解析为 `/sample.zip/docs/pic.png` | 通过 | [F-81 entry](evidence/2026-10-21/F-81_archive-entry.png) |
| V3 | F-75 / F-81 包内 HTML（trusted） | 包内 `page.html` 直接原文，自己的 CSS/脚本生效 | 通过 | [F-81 html](evidence/2026-10-21/F-81_archive-html.png) |
| V4 | F-77 / F-81 包内 HTML（untrusted） | 同一包内 `page.html` 走沙箱外壳；iframe 内 CSS/脚本生效 | 通过 | [F-77 sandbox](evidence/2026-10-21/F-77_archive-html-sandbox.png) |
| V5 | F-81 移动端 | 390×900 包根页无横向溢出；格式/大小/条目数可读 | 通过 | [F-81 mobile](evidence/2026-10-21/F-81_archive-mobile.png) |
| V6 | F-82 / F-83 缓存/安全 | 二次访问复用解压缓存；穿越、重复路径、真实目录名 `not.zip`、safe 模式 | 通过（自动） | 服务端单测 + 黑盒 |
| V7 | F-84 编码 | UTF-8 → GBK 回退单测 | 通过（自动，CP437 委托 zip） | `src/archive.rs` 单测 |

## 自动断言

- `node tests/browser-probe.mjs`：**PASS=203 FAIL=0**；新增包根页、包内 Markdown
  相对图片、包内 HTML trusted/untrusted、包内源码。
- `bash tests/selftest-rust.sh`：**PASS=198 FAIL=0**；覆盖 zip/tar.gz/7z 条目、
  301、整包/条目下载、嵌套 zip 不递归、包内 HTML、safe 404。
- `cargo test --lib`：**68 passed**，含压缩包解压、缓存复用、路径穿越/重复、GBK。
- `bash tests/run-all.sh`：ALL LOCAL CHECKS PASSED。

## 已知边界

1. **7z solid 包**必须整包解压；首次打开大包会有延迟。
2. **上限**：包 200 MB / 解压 1 GB / 2 万条 / 单条 100 MB；加密、多卷、软链/硬链、
   设备文件、重复路径整包拒绝。
3. **嵌套压缩包**不递归；包内 `.zip` 作为普通文件下载。
4. 包内条目不进全站搜索，也不展开到导航树；导航只显示压缩包文件。
5. ZIP 非 UTF-8 名称按 UTF-8 → GBK → CP437 回退；CP437 由 `zip` crate 处理。
