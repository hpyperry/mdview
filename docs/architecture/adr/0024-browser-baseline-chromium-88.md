# 浏览器兼容基线：Chromium 88

**Status**: accepted（2026-11-04）。取代 [ADR 0022](0022-browser-baseline-chromium-86.md)
的 Chromium 86 基线；CSS 约束仍由
[`tests/check-css-baseline.mjs`](../../../tests/check-css-baseline.mjs) 执行。

## 背景

[ADR 0022](0022-browser-baseline-chromium-86.md) 把基线定为 Chromium 86，依据是
360 信创版/UOS 内置浏览器的常见内核。但这条基线一直没有在 86 上真正跑过：

- macOS arm64 没有 Chromium 86 构建，也没有 Rosetta；
- Google 快照桶里 M86 的 revision（如 800218）返回 404，取不到可执行构建；
- 现有自动化只有最新 headless Chrome，旧内核验收靠人工。

2026-11-04 用 Docker + Ubuntu amd64（qemu）+ Chromium **88.0.4287.0** 跑了一轮
25 项 CDP 断言，全部通过：旧请求头 MIME 兜底、`content-visibility` 的 intrinsic-size
回退、大源码 `#L1`/`#L15001`、导出 PNG（白底/签名/尺寸）、主题、导航、TOC、放大、
搜索。报告见
[`docs/testing/reports/legacy-chromium-88-2026-11-04.md`](../../testing/reports/legacy-chromium-88-2026-11-04.md)。

继续承诺 86 意味着承诺一个没有证据的版本；继续找 86 构建的收益低于成本。

## 决定

1. **支持下限改为 Chromium 88**。覆盖 Chrome/Edge、360 信创版、统信 UOS 内置浏览器
   等 88+ 内核；**Chromium 86/87 不再承诺**，更早版本不支持。
2. **构建 target 对齐**：`web/build.mjs` 与 `tools/build-assets` 的 esbuild 从
   `chrome86` 改为 `chrome88`，避免产物引入 89+ 语法。
3. **CSS lint 基线改为 88**：`tests/check-css-baseline.mjs` 的 `BASELINE = 88`；
   `inset`（87）、`aspect-ratio`（88）、`:is`/`:where`（88）、`text-underline-offset`
   （87）从黑名单移除；89+ 特性仍然拦截。
4. **保留 86 时代的回退作为加固**：`content-visibility` 仍放在
   `@supports (contain-intrinsic-width: none) and (contain-intrinsic-height: 1px)` 里
   （88–97 需要回退全量渲染，见 PR #44）；`replaceChildren` 的 `textContent` 回退保留，
   但不构成对 86 的支持承诺。
5. **历史文档不改写**：`CHANGELOG.md`、`docs/releases/*` 里的“Chromium 86”是当时
   的发布事实；当前文档、README、AGENTS 与 ADR 使用 88。

## 考虑过的替代方案

- **维持 86 承诺**：没有 86 实测，和证据不一致；出现回归时无法判断是否在承诺范围内。
- **继续找精确 86 构建**：M86 快照不可得，Playwright 旧镜像 1.5 GB 在当前网络下
  拉取超时；收益只是把 88 换成 86，而 86–94 在这些特性上同档。
- **直接降到 80**：没有实测证据，且 `app.js` 语法/API 下限、`replaceChildren` 等
  都会扩大测试面；不做。

## 后果

- Chromium 86/87 用户不再被承诺；这是明确的支持范围收缩。
- CSS lint 放宽到 88 后，`inset`/`aspect-ratio`/`:is`/`:where` 可以正常使用；
  但仍需注意 `content-visibility` 与 intrinsic-size 的 95/98 门槛。
- 旧引擎验证仍是人工/临时 harness，尚未进 CI；88 的验证环境是 Docker/qemu，
  与真实信创浏览器可能有滚动、字体、Canvas 差异。

## 验证

- `node tests/check-css-baseline.mjs`：基线 88、黑名单与深色色板同步。
- `bash tests/run-all.sh`：Chrome 侧全量回归。
- Chromium 88：`docs/testing/reports/legacy-chromium-88-2026-11-04.md`（25/25）。
- 旧内核自检页：`tests/fixtures/chromium-baseline/probe.html`。
