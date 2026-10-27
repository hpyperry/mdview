# 导航分层预载夹具

用于人工复测全站导航“三层预载 + 当前路径脊柱 + 按需展开”。

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/nav-lazy/root --trust --port 8003 --port-tries 0
```

入口：`http://127.0.0.1:8003/`

## 预期

1. 打开全站导航，初始树包含根文件 `index.md`、`another/` 与 `level1/`；目录只展开到
   `level1/level2/level3`。`level3` 下的 `sibling.md`、`level4/` 在展开前不可见。
2. 展开 `level3` 会发一次 `/_nav?__mdview=nav&dir=level1/level2/level3`，只返回它的
   直接子项；`level4` 仍是占位。
3. 直接打开 `/level1/level2/level3/level4/deep.md`：页面空闲预取带 `active` 脊柱，
   打开导航后祖先链自动展开，`deep.md` 高亮；同级 `other/` 仍是占位。
4. 桌面端在 `level3` 行停留约 150ms 再点击，展开通常无“加载中…”；触屏直接点击。
5. `/_nav?__mdview=nav&dir=../`、`dir=/etc`、`dir=level1/level2/../..` 返回 404。

## 已知限制

- 第 3 层目录在展开前不知道是否为空，统一显示展开箭头；展开空目录会显示“空目录”。
- 单个超大目录仍会一次列出全部条目；本夹具不覆盖分页/虚拟滚动。
