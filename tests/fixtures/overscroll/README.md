# overscroll 复测夹具

- 关联：F-98 / 2026-11-11 纵向回弹修复（README-only，无新增夹具文件）
- 关联测试报告：`docs/testing/reports/browser-report-2026-11-11-overscroll.md`
- 夹具根：复用 `tests/fixtures/wide-layout/root`（含长文档 `long.md`）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/wide-layout/root --trust --port 8304 --port-tries 0
```

- 入口：`/long.md`（内容足够长，可滚到顶部和底部）

## 复测步骤

1. 视口 ≥901px，打开 `/long.md`，用触控板滚到最顶部后继续向上滑。
   预期：主岛内容不再被拉出弹性回弹，页面保持停住。
2. 滚到最底部后继续向下滑。
   预期：同样不回弹。
3. 横向双指滑动（从左往右）。
   预期：仍可触发浏览器后退/前进手势（`overscroll-behavior-x: auto`）。
4. 打开 DevTools，选中 `.content-card`，确认：
   - `overscroll-behavior-y: none`
   - `overscroll-behavior-x: auto`

## 已知限制

- 回弹是触控板/平台级视觉效果，headless 浏览器无法断言；自动化只验证计算样式，
  物理回弹需要人工用触控板确认。
