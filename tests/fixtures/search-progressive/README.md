# 渐进搜索复测文档

- 关联：Issue [#66](https://github.com/hpyperry/mdview/issues/66) / PR（待建）/ F-99
- 关联测试报告：`docs/testing/reports/browser-report-2026-11-07-search-progressive.md`
- 证据：`docs/testing/evidence/2026-11-07/`
- 夹具根：`tests/fixtures/search-progressive/root/`
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/search-progressive/root --trust --port 8006 --port-tries 0
```

- 入口：`/search?__mdview=search&q=batchneedle`
- 自动化覆盖：`src/server.rs` 的 `search_resumes_in_batches_from_cursor`；`tests/browser-probe.mjs` 的首批 40 / 继续搜索 / 追加 45 / 计数更新 / 按钮移除。

## 复测步骤

1. 操作：打开入口。
   预期：只显示前 40 个文件，不一次性渲染 45 个；底部出现“已扫描前 N 个文件，
   当前显示这一批结果”和「继续搜索」按钮。

2. 操作：点「继续搜索」。
   预期：按钮短暂显示“正在加载…”，随后把剩余 5 个文件追加到列表末尾；已有结果
   不重复；页头计数变成 45 个文件 / 45 条结果；按钮消失。

3. 操作：禁用 JavaScript 后重新打开入口，再点「继续搜索」。
   预期：链接直接导航到下一批（`cursor=...`），页面只显示该批结果；功能仍可用。

4. 操作：在非常大的目录（例如 `/Users/hpy`）搜索一个很宽的关键词。
   预期：请求在约 1.2 秒或 2000 个文件内返回，不会阻塞到整个目录扫完；出现
   「继续搜索」时由用户决定是否继续。

## 已知限制

- 每批最多 40 个文件组、200 条结果；单个文件最多展示 5 条命中。
- 继续搜索会从头遍历到 cursor，跳过文件不读内容；超大目录的后续批次仍有遍历成本。
- 结果按路径排序仅在每批内进行；追加后不重新全局排序。
- 无 JS 时“继续搜索”是下一页，不保留上一批结果。

## 清理

- 停止临时服务，释放端口。
