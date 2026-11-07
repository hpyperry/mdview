# mdview 使用手册测试记录与问题清单（2026-11-07）

本文件记录使用 browser-use 与 headless Chrome 对 2.5.1 当前功能做可视化验收时
发现的问题。按要求**只记录、不修改**。

## 测试方式

- in-app browser（browser-use）：导航、DOM 断言、点击查找/复制/导航/主题/文件夹
  打包、HTML/Turst/压缩包/编码/错误页；
- headless Chrome：截图与需要可见窗口的懒加载岛（source、IntersectionObserver）。
  in-app browser 的 desktop 窗口未处于前台时，截图与 `document.hasFocus()` 不可用，
  因此截图改由 headless Chrome 完成；功能断言仍由 browser-use 执行。

## 问题

| # | 类型 | 位置 | 现象 | 影响 | 证据 |
|---|---|---|---|---|---|
| 1 | 文档 | `docs/reference/features.md` | F-29/F-35/F-45/F-101 仍是旧页头/旧分块/旧上限描述；F-31 未写 >500 行条件；F-33 未区分源码页 Worker | 功能矩阵与 2.5.x 实际行为不一致 | 手动对照 |
| 2 | 文档 | `docs/README.md` | 开头仍写“这里是 2.4 文档的入口” | 版本文案过期 | `docs/manual/images/02-markdown.png` |
| 3 | 交互 | 文档/源码页“复制” | 浏览器未聚焦或无剪贴板权限时，失败反馈只改 hover 浮层文案（1.5s），不悬停看不到；控制台/页面无提示 | 用户可能误以为已复制 | browser-use 中 `done=false`，headless 授权后通过 |
| 4 | 文档 | 搜索页 | 在超大根目录里搜索时，首批会先扫 2000 个文件再提示“继续搜索”，可能暂时看不到目标文件 | 行为符合分批设计，但用户容易误判为无结果 | 根目录 `/Users/hpy` 搜索 `comrak` |
| 5 | 测试方法 | in-app browser | Review 窗口不可见时 `screenshot` 报 “needs a visible tab”，`document.hasFocus()` 为 false，剪贴板与可见性懒加载岛不可用 | 不影响产品；影响纯 browser-use 截图/复制验收 | browser-use 返回错误 |

## 结论

- 未发现阻塞使用的功能缺陷；上述 1–2 为文档过期，3 为可改进的失败反馈，4 为预期
  行为但需要手册说明，5 为测试环境限制。
- 本次不修改这些项；后续可单独立 Issue 处理。
