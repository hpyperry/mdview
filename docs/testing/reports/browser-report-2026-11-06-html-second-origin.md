# HTML 第二 origin 浏览器验收报告（2026-11-06）

关联：[Issue #52](https://github.com/hpyperry/mdview/issues/52) ·
[PR #53](https://github.com/hpyperry/mdview/pull/53) ·
[ADR 0025](../../architecture/adr/0025-html-second-origin.md)。
功能：F-75 / F-77 / F-96。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-11-06 |
| 分支 | `feat/html-second-origin` @ `13569c5`（合并后 `main` @ `c7acf34`） |
| 平台 | macOS 27.2 arm64 |
| Rust | 1.96.0 |
| Node | v22.22.3 |
| 浏览器 | Chromium 152.0.7977.167（OpenCode 内嵌） |
| 被测根 1 | `tests/fixtures/html-second-origin` |
| 被测根 2 | 本机 AirGap `web/dist`（用户项目，不入库） |
| 端口 | 夹具主 8270 / 第二 8271；AirGap 主 8272 / 第二 8273 |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元/集成 | `cargo test --lib` | **94 passed** |
| Golden | `cargo test --test golden` | **27 cases passed** |
| 渲染兼容 | `cargo test --test render_compat` | **134 passed** |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | **PASS=292 FAIL=0** |
| 浏览器探针 | `node tests/browser-probe.mjs` | **PASS=271 FAIL=0** |
| TTY 信任 | `bash tests/trust-tty.sh` | **PASS=9 FAIL=0** |
| 源码页性能 | `node tests/perf-source.mjs` | **4 项预算通过** |
| artifact 冒烟 | `bash tests/smoke-artifact.sh target/release/mdview` | **PASS=7 FAIL=0** |
| 全量本地验收 | `bash tests/run-all.sh` | **ALL LOCAL CHECKS PASSED** |

合并前 CI（run `42222682255`）8/8 通过：macOS 15、Ubuntu、Windows 的 test/build，
以及 dependency audit。

## 视觉与交互验收

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-77 | 夹具第二 origin | 打开主 origin `/index.html` | 302 到第二 origin；无外壳/iframe；module/storage/fetch/SW/MIME 全部 ok；console 无错误 | 通过 | [F-77_second-origin-fixture.png](../evidence/2026-11-06/F-77_second-origin-fixture.png) |
| F-75 | HTML 源码页 | 打开 `/index.html?raw=1` | 仍在主 origin；`源码` tab 激活；`预览` 指向第二 origin；无 iframe；有 `#L1` | 通过 | [F-75_source-preview-tab.png](../evidence/2026-11-06/F-75_source-preview-tab.png) |
| F-77 | AirGap 发送端 | 打开 AirGap `/index.html` | 302 到第二 origin；PWA 正常渲染；无 iframe/工具栏；console 无错误 | 通过 | [F-77_airgap-index.png](../evidence/2026-11-06/F-77_airgap-index.png) |
| F-77 | AirGap 接收端 | 打开 AirGap `/receive.html` | 302 到第二 origin；视频选择入口可用；无 iframe/工具栏；console 无错误 | 通过 | [F-77_airgap-receive.png](../evidence/2026-11-06/F-77_airgap-receive.png) |

关键观察：

- 夹具页最终 `location.origin` 是 `http://127.0.0.1:8271`，页面显示
  `module: ok`、`storage: ok`、`fetch: ok`、`sw: registered`、`mime: ok`；
  `iframe=false`、`toolbar=false`、console errors 为空。
- 源码页 `location.origin` 是主 origin `http://127.0.0.1:8270`，
  `document.body.dataset.page = source`；“预览”链接为
  `http://127.0.0.1:8271/index.html`，“源码”为 `/index.html?raw=1`。
- AirGap 两个页面的 `location.origin` 都是 `http://127.0.0.1:8273`，
  `navigator.serviceWorker` 可用，console errors 为空；页面没有 mdview 外壳、
  `html-toolbar` 或 iframe。

## 黑盒证据

`tests/selftest-rust.sh` 覆盖了本次改动的 HTTP 契约：

- 未信任 `/page.html` → 302，`Location` 指向第二 origin；`?view=1` 同样 302；
  `Sec-Fetch-Dest: object` 不能绕过；
- 第二 origin 的 HTML/CSS/JS MIME、目录 404、`_nav` 不返回内部 JSON、
  `_assets` 404；
- 第二 origin 的压缩包容器原文件、包内 HTML 原文；
- 主 origin `?raw=1` 源码页的“预览”链接指向第二 origin；
- `--html-port` 与端口冲突回退。

## 发现

- 没有发现新的产品问题；sandbox 下的 storage/SW/module/CORS 报错在第二 origin
  上全部消失。
- 旧 `airgap.html` 单文件仍从 `fastly.jsdelivr.net` 取 zxing wasm，离线/被墙时
  会出现 `ERR_NAME_NOT_RESOLVED`。这是该页面自身的外部依赖，不属于 mdview；
  本次用 `web/dist`（本地 wasm）验证。

## 覆盖缺口

- 没有在 Chromium 88 上复跑第二 origin 路径。当前基线仍是 88；旧引擎报告覆盖的是
  既有页面路径，不是本次新增的第二 origin。
- 没有测反向代理 / HTTPS 双端口暴露。
- 没有测手机通过局域网 HTTP 访问时的 Service Worker（浏览器安全上下文限制）。
- Windows 只跑自动套件，没有做人工视觉验收。

## 结论

通过。未信任 HTML 已从 sandbox 外壳切换为第二 origin 静态镜像，应用型 HTML
的存储、Service Worker、module 与同源 fetch 恢复正常，同时保留 origin 级隔离。
