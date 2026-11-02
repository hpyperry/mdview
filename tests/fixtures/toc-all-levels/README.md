# TOC 全层级与深色导航三角复测文档

- 关联：Issue [#34](https://github.com/hpyperry/mdview/issues/34) / F-50
- 夹具根：`tests/fixtures/toc-all-levels/root/`

用于人工复测两件事：

1. 右侧 TOC 细轨/文字大纲覆盖 `h1`–`h6` 全层级，并保持逐级缩进；
2. 深色主题下文件导航目录行的展开三角是 `currentColor` 描边，不再是一块黑三角。

## 启动

在仓库根目录：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/toc-all-levels/root --trust --port 8005 --port-tries 0
```

打开 `http://127.0.0.1:8005/`。

## 入口

| 入口 | 用途 |
|---|---|
| `/all-levels.md` | 7 个标题，覆盖 `h1`、`h2`、`h3`、`h4`、`h5`、`h6` 与另一个 `h2` |
| `/long.md` | 61 个标题，用于验证细轨独立滚动与当前项自动跟随 |

## 复测步骤

1. 窗口宽度 ≥1360px，打开 `/all-levels.md`。
   预期：右侧细轨有 7 个刻度；`h1` 刻度最宽，向下逐级变窄。
   悬停细轨展开文字大纲，7 个条目全部存在；`h3`–`h6` 的缩进逐级增加，
   第一条是正文标题“全层级标题示例”。

2. 切换到深色主题（顶栏主题按钮切到“深色”）。
   预期：未选中刻度仍可辨认（使用 `--border-strong`，不是几乎隐形的 `--border`）；
   当前项仍用强调色。

3. 把窗口缩到 <1360px，重新打开 `/all-levels.md`。
   预期：正文顶部出现“本页目录（7）”折叠块，条目层级与宽屏一致；没有 JS 时不出现。

4. 打开 `/long.md`，滚到页面靠后的章节。
   预期：右侧细轨本身可以滚动；滚动正文时当前刻度自动进入细轨可视区，
   最后一个“Long Section 60”能出现并高亮，不再有够不到的节点。

5. 打开全站导航，展开任意目录，切换到深色主题。
   预期：目录行的展开三角是细描边 `>`，与文件夹图标同为 muted 色；
   不再出现黑色实心三角。展开后三角旋转 90°。

6. 对照 `http://127.0.0.1:8005/all-levels.md?raw=1` 的标题层级，
   确认目录没有漏项或多出 sr-only 的页面标题。

## 自动化覆盖

- `tests/browser-probe.mjs`
  - 页内目录覆盖 `h1`–`h6`、条目数 7、逐级缩进；
  - 宽屏细轨 7 个刻度、逐级变窄、深色 `--border-strong`；
  - `/long.md` 细轨可滚动、当前刻度自动可见；
  - 深色导航三角 `fill: none` 且 `stroke` 非 `none`。
- `node tests/check-css-baseline.mjs`：两份深色色板包含相同的 `--border-strong`。
- `bash tests/run-all.sh`：上述探针与文档链接检查一起跑。

## 已知限制

- TOC 由浏览器运行时生成；禁用 JS 时没有目录。
- 目录文本取自 `textContent`，标题内的 HTML 标签不会保留。
- 正文第一个 `h1` 按约定进入目录，与页面正文标题重复是预期行为。
- 极长标题在文字大纲里按面板宽度换行；细轨刻度只表达位置，不显示文本。
