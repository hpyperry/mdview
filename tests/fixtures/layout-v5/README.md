# layout-v5 复测夹具

对应 2026-11-07 的未推送布局迭代（顶栏居中文件名、缝隙面包屑、主岛文件信息/操作、
文件内查找与复制、目录居中留白、文件夹打包下载、VS Code 高亮）。

## 启动

```bash
cargo build --release
target/release/mdview \
  --root tests/fixtures/layout-v5/root \
  --trust \
  --host 127.0.0.1 --port 8300 --port-tries 0
```

夹具根可以直接作为 `--root`；`--trust` 是文件夹打包下载和文件内查找的前提。

## 复测入口

| 场景 | URL | 预期 |
|---|---|---|
| 目录页 | `/` | 列表限宽 1100px 居中；面包屑在顶栏与主岛之间的缝隙；无“项目数” |
| 文件夹下载 | `/sub/?download=zip` 或目录行下载图标 | 全屏遮罩后下载 `sub.zip`，临时文件随后删除 |
| 文档预览 | `/guide.md` | 文件名在顶栏居中；主岛顶部 sticky 栏左侧搜索/复制/下载/源码/导出，右侧文件信息；淡入转场 |
| 文件内查找 | `/guide.md` 点搜索，输入 `needle` | 浮层显示 `1/1`，命中高亮，Enter/上下切换，Esc 关闭并清高亮 |
| 复制全文 | `/guide.md` 点复制 | 剪贴板为 Markdown 原文，图标变勾并显示「已复制」 |
| 源码页 | `/code.rs` | 文件名/信息同文档页；左侧搜索/复制/下载，行号完整；无 TOC |
| HTML 源码 | `/page.html?raw=1` | 无“预览/源码”分段条；预览入口在主岛功能区 |
| 高亮主题 | `/code.rs` 切浅色/深色 | 注释绿、关键字蓝/深蓝、字符串红/橙，浅色不再复用深色 token |
| 目录留白 | `/` 视口 1440 | 列表左右各约 170px 留白；文件页恢复铺满 |

关联测试报告：
[`docs/testing/reports/browser-report-2026-11-07-layout-v5.md`](../../../docs/testing/reports/browser-report-2026-11-07-layout-v5.md)。

截图证据：
[`docs/testing/evidence/2026-11-07/`](../../../docs/testing/evidence/2026-11-07/)。
