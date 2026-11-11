# return-position 复测夹具

对应 2026-11-11 的“面包屑返回文件位置”修复：从文件预览点面包屑回到目录时，
目录列表滚动到刚刚预览的文件行并短暂高亮；URL 保持普通目录地址，不写文件名。

## 启动

```bash
cargo build --release
target/release/mdview \
  --root tests/fixtures/return-position/root \
  --trust \
  --host 127.0.0.1 --port 8305 --port-tries 0
```

夹具根是 `root/`，里面是 24 个短文档，列表在 900px 高度下可滚动。

## 复测入口

| 场景 | URL | 预期 |
|---|---|---|
| 直接打开文件 | `/item-20.md` | 面包屑最后一级链接仍是 `/`，URL 不含文件名 |
| 点面包屑返回 | 在 `/item-20.md` 点面包屑的根目录 | 回到 `/`（无 hash），滚动到 item-20 行并短暂高亮 |
| 浏览器后退 | 在 `/` 滚到中间，打开一个文件后点浏览器后退 | 目录恢复到离开时的滚动位置 |
| 无 JS / 禁用存储 | `/item-20.md` 点面包屑 | 回到目录顶部（增强功能，不做兜底） |

自动化覆盖：`tests/browser-probe.mjs` 的 `== return to file position ==` 段。

关联测试报告：
[`docs/testing/reports/browser-report-2026-11-11-return-position.md`](../../../docs/testing/reports/browser-report-2026-11-11-return-position.md)。

截图证据：
[`docs/testing/evidence/2026-11-11/`](../../../docs/testing/evidence/2026-11-11/)。
