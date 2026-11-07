# 源码页铺满主岛与大块高亮 Worker

**Status**: accepted（2026-11-07）

## 背景

2.5.0 的源码页有两种观感问题：

- 短文件的代码背景与左侧行号栏只画到内容末尾，下面留一大片空白主岛；
- >256 KB 的源码一律进入分块模式，即使只有 11 行也会显示“文件较大”，而且
  >256K 字符的代码块直接关闭高亮，1 MB 的压缩文件只能看纯文本。

## 决定

1. **分块条件**改为 >256 KB **且** >500 行。少行大文件保持单块，不再出现
   “文件较大”提示；分块提示改为“已分块加载完整内容”。
2. **源码页铺满主岛**：`.content-card` 在源码页使用纵向 flex，`.source-wrap`
   `flex: 1 0 auto`，`.source` `min-height: 100%`。短文件的代码背景与行号栏
   延伸到主岛底部；长文件仍由 `.content-card` 作为唯一滚动容器。
3. **行号栏**最小宽度 46px、等宽数字、右边框随内容铺满。
4. **大块高亮移入同源 Worker**：单块文本 >256K 字符时，`source.ts` 把代码发给
   `/_assets/hlworker.js`，3 秒超时；超时或报错时终止 Worker、回落纯文本，并在
   下一次请求时重建。小代码块仍在主线程同步高亮。
   - Worker 由 `web/build.mjs` 复用 `assets/highlight.min.js` 生成，不引入新依赖；
   - `MDVIEW_WEB_PREBUILT` 路径也会复制 `hlworker.js`；
   - CSP 增加 `worker-src 'self'`，`script-src` 仍只信任 per-page nonce，
     不使用 `blob:`，也不放宽到 `'self'`/`'unsafe-inline'`；
   - Worker 输出再写回 `<code>`，只接受 JSON 的 `html` 字段，失败即回落。

## 后果

- 二进制多内嵌一份约 1 MB 的 worker 资产；换来主线程不因 1 MB 压缩文件卡住。
- 超大 Markdown 围栏代码块仍走“高亮已关闭”（语言条有提示），暂未迁移到 Worker。
- Chromium 88 基线不变；`Worker`、`postMessage`、`ObjectURL` 均不在使用范围内
  （worker 从同源 URL 加载）。

## 测试

`tests/fixtures/layout-v5/README.md`；
`docs/testing/reports/browser-report-2026-11-07-source-worker.md`。
