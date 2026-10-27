# <Feature 或 Fix 名称> 复测文档

- 关联：Issue #N / PR #N / F-xx（没有 F-xx 的修复写 Issue/PR）
- 夹具根：`tests/fixtures/<slug>/`（使用子目录 root 时写完整路径）
- 启动：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/<slug> --trust --port 8003 --port-tries 0
```

- 入口：`/`
- 自动化覆盖：单元 / 黑盒 / 浏览器探针 / 手工视觉

## 复测步骤

1. 操作：…
   预期：…
2. 操作：…
   预期：…

## 已知限制

- …

## 清理

- 停止临时服务，释放端口；删除临时生成的夹具或缓存。
