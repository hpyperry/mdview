# 浏览器验收：HTML 文件 Trust 门控（2026-10-21）

**被测版本**：mdview 2.0.0 工作树（ADR 0015 最终版，未提交）
**验收方式**：release 二进制 + headless Chrome；实际页面截图 + 自动探针
**结论**：已信任根恢复静态原文（Python/静态服务器行为），未信任根使用沙箱外壳；
`192` 项浏览器探针全绿。

## 环境

| 项 | 值 |
|---|---|
| 平台 | macOS 27.0.0 arm64 |
| Rust / Node | Rust 1.96.0 / Node 22.22.3 |
| 浏览器 | Google Chrome 155.0.8059.85 |
| trusted 服务 | `http://127.0.0.1:18143`，`--root /tmp/mdv-evidence-root --trust` |
| untrusted 服务 | `http://127.0.0.1:18144`，同一 root，`--untrusted` |
| 视口 | 1280×1000 桌面、390×900 移动 |
| 证据 | [`evidence/2026-10-21/`](evidence/2026-10-21/) |

## 覆盖结果

| 编号 | 功能 / 页面 | 操作与预期 | 结果 | 证据 |
|---|---|---|---|---|
| V1 | F-75 trusted 原文 | 打开 `report.html`：只有报告本身，无 mdview 外壳/iframe/沙箱；脚本、localStorage、同源 fetch 正常 | 通过 | [F-75 dark](evidence/2026-10-21/F-75_html-trusted-raw-dark.png) |
| V2 | F-75 trusted 浅色 | 报告自己的 `light-dark()` 随 `prefers-color-scheme` 生效 | 通过 | [F-75 light](evidence/2026-10-21/F-75_html-trusted-raw-light.png) |
| V3 | F-75 trusted 移动端 | 390×900 只有报告，无横向溢出 | 通过 | [F-75 mobile](evidence/2026-10-21/F-75_html-trusted-raw-mobile.png) |
| V4 | F-76 源码切换 | `?raw=1` 进源码页；顶部 `预览 / 源码` tabs；行锚点；无 iframe | 通过 | [F-76](evidence/2026-10-21/F-76_html-source.png) |
| V5 | F-77 untrusted 沙箱 | 同一 `.html` 在未信任根：外壳 + 沙箱 iframe；脚本运行、相对 CSS 生效 | 通过 | [沙箱 dark](evidence/2026-10-21/F-77_html-sandbox-dark.png) · [light](evidence/2026-10-21/F-77_html-sandbox-light.png) · [mobile](evidence/2026-10-21/F-77_html-sandbox-mobile.png) |
| V6 | F-77 沙箱隔离 | iframe 内 localStorage、父页面、同源 fetch 被阻断 | 通过（自动） | `tests/browser-probe.mjs` |
| V7 | F-78 SVG 直开 | 带 `<script>` 的 SVG 直开不执行脚本；`<img>` 内嵌不受影响 | 通过（自动） | `tests/browser-probe.mjs` |
| V8 | F-09 / F-79 目录入口 | `report.html` 用 file-code 图标；大小/时间/操作固定列；悬停出现源码与下载图标（36px 点击区） | 通过 | [F-79](evidence/2026-10-21/F-79_html-directory.png) |

## 自动断言

- `node tests/browser-probe.mjs`：**PASS=192 FAIL=0**；新增 trusted 原文
  （无外壳、脚本/localStorage/同源 fetch）、untrusted 沙箱（iframe、相对 CSS、
  storage/fetch 阻断）、源码切换与 SVG 脚本阻断。
- `bash tests/selftest-rust.sh`：**PASS=183 FAIL=0**；覆盖 trusted 原文头部、
  untrusted 裸页 CSP、`Sec-Fetch-Dest: style` 的 CSS MIME、HTML 搜索行
  `?raw=1#L<n>`、safe 模式源码。
- `bash tests/run-all.sh`：**ALL LOCAL CHECKS PASSED**（含 golden、TTY、性能、冒烟）。

## 已知边界

1. **Trusted 原文是同源顶层页面**：脚本能读 `/_nav`、搜索与站点内其他文件；
   这是 Python 版行为，也是 Trust 必须真实的原因。未信任根不提供 raw。
2. **未信任沙箱的限制**：`target="_top"`/`_parent` 被拦，`_blank` 继承沙箱，
   下载默认被拦；iframe 固定高度，内部滚动。它是安全兜底，不是可信文档的默认路径。
3. **SVG 是例外**：即使 trusted，直开 SVG 仍带 `CSP: sandbox`，脚本不执行；
   这是对 Python 行为的刻意安全偏差。
4. **编码**：原文不强制 UTF-8，由文档 BOM/`meta charset` 决定；Python 的强制
   UTF-8 不再沿用。
