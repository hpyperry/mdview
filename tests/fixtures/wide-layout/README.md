# wide-layout 复测夹具

对应 2026-11-11 的宽屏布局修复：外壳（顶栏 + 主岛）铺满视口；Markdown 页的
主岛左边缘不动，右边缘缩进目录岛宽度 + 32px；正文在主岛内居中，其他元素不动。

## 启动

```bash
cargo build --release
target/release/mdview \
  --root tests/fixtures/wide-layout/root \
  --trust \
  --host 127.0.0.1 --port 8304 --port-tries 0
```

## 复测入口

| 场景 | URL | 预期 |
|---|---|---|
| 文档 + TOC | `/guide.md` | 主岛 16–2272；正文在主岛内居中（两侧各 528）；目录岛 2304–2544 与顶栏右边缘对齐；工具栏/面包屑位置不变 |
| 长目录 | `/long.md` | TOC 岛与主岛同高、从主岛顶部开始，目录在岛内滚动，「回到顶部」在岛底 |
| 无标题文档 | `/no-toc.md` | 不挂载 TOC 岛，`.no-toc` 恢复单列，主岛重新铺满 |
| 源码页 | `/code.rs` | 主岛铺满，代码与行号栏延伸到主岛底部 |
| 目录页 | `/` | 主岛铺满；列表仍限宽 1100px 居中 |
| 搜索页 | `/search?__mdview=search&q=want` | 页头与结果限宽到正文组宽度并居中 |
| 窄屏回退 | 视口 1200×900 | 恢复 24px 细轨，主岛与正文行为不变 |
| 移动端 | 视口 390×844 | 单列，内联目录，无横向溢出 |

宽度断言在 `tests/browser-probe.mjs` 的 `== shell alignment ==` 与
`== toc island ==` 段，覆盖 1440、1600、2560、1280、1200 与 1000。

关联测试报告：
[`docs/testing/reports/browser-report-2026-11-11-wide-layout.md`](../../../docs/testing/reports/browser-report-2026-11-11-wide-layout.md)。

截图证据：
[`docs/testing/evidence/2026-11-11/`](../../../docs/testing/evidence/2026-11-11/)。
