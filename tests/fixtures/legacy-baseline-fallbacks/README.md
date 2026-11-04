# 旧引擎基线回退 复测文档

- 关联：Issue [#43](https://github.com/hpyperry/mdview/issues/43) / PR [#44](https://github.com/hpyperry/mdview/pull/44) / F-31、F-93
- 夹具根：README-only；大源码用临时生成，不提交大文件
- 启动：

```bash
cargo build --release
mkdir -p /tmp/mdview-big-source
python3 - <<'PY'
from pathlib import Path
Path('/tmp/mdview-big-source/big.txt').write_text(
    ''.join(f'line {i} the quick brown fox jumps over the lazy dog\n' for i in range(1, 15001)),
    encoding='utf-8',
)
PY
./target/release/mdview --root /tmp/mdview-big-source --trust --port 8003 --port-tries 0
```

- 入口：`/big.txt`
- 自动化覆盖：`tests/check-css-baseline.mjs` 的 `content-visibility` 门禁；`tests/browser-probe.mjs` 的「缺 replaceChildren 仍有行号」；`:modal` 特性检测；本页为旧内核人工复测

## 背景

旧浏览器兼容性审计（`docs/research/legacy-engine-compatibility.md`）发现两处超出 86 基线的隐性依赖：

- `.source-chunk` 的 `content-visibility: auto` 依赖 `contain-intrinsic-width: none`
  （Chrome 98）与 `contain-intrinsic-height`（Chrome 95）。86–97 上声明被丢弃，
  离屏分块按 0 高度布局，滚动条和 `#L<n>` 锚点会跳。
- `source.ts` 用 `Element.replaceChildren`（Chrome 86）清空并重建行号；<86 直接抛错。

修复：把整个 `content-visibility` 优化放进
`@supports (contain-intrinsic-width: none) and (contain-intrinsic-height: 1px)`，
不支持的引擎回退为全量渲染；`replaceChildren` 改为特性检测 + `textContent=''` 回退。

## 复测步骤

1. 操作：现代 Chrome 打开 `/big.txt`，滚动到底部，再访问 `/big.txt#L12000`。
   预期：分块仍懒渲染（`getComputedStyle(.source-chunk).contentVisibility === 'auto'`），
   滚动条长度稳定，`#L12000` 能定位。

2. 操作：在 Chrome 86–97（或用 DevTools 确认
   `CSS.supports('contain-intrinsic-width', 'none') === false`）打开同一页。
   预期：`content-visibility` 不生效（计算值为 `visible`），所有分块正常渲染；
   滚动条与行锚点正常，只是失去离屏优化。

3. 操作：模拟缺失 `replaceChildren`（CDP 注入
   `delete Element.prototype.replaceChildren;` 后再加载 `/big.txt`，或使用旧内核）。
   预期：行号 gutter 仍生成，`#L1`、`#L15001` 存在；控制台没有
   `replaceChildren is not a function`。

4. 操作：在旧内核跑 `node tests/browser-probe.mjs`（必要时用 `CHROME=`）。
   预期：`:modal` 断言在旧内核返回 `null` 并被容忍，不再因未知伪类抛 `SyntaxError`；
   其它断言按实际支持情况通过或跳过。

5. 操作：`npm --prefix tools/build-assets run build` 后检查 `assets/highlight.min.js`。
   预期：构建命令带 `--target=chrome86`；产物不再引入 86+ 之外的语法。

## 自动化覆盖

- `node tests/check-css-baseline.mjs`：出现 `content-visibility: auto` 时，必须存在
  `@supports (contain-intrinsic-width: none) and (contain-intrinsic-height: 1px)`。
- `node tests/browser-probe.mjs`：注入删除 `Element.prototype.replaceChildren` 后，
  源码分块仍生成行号；`:modal` 断言在未知伪类时按跳过处理。
- 旧内核真机/Chromium 快照跑第 2、3 步为人工项。

## 已知限制

- `@supports` 门禁让 Chrome 86–97 失去大源码的离屏优化；内容仍完整可读，性能会下降。
- `<86` 的 `replaceChildren` 回退只覆盖这一处 API；其它 <86 的能力（flex `gap`、
  `:focus-visible` 等）不在本轮范围。
- `app.js` 的语法下限仍是 Chrome 80；更老内核会在解析阶段失败，另开 Issue 处理。
- 旧内核真机行为仍需要现场 `chrome://version` 或 Chromium 快照确认。

## 清理

- 停止临时服务并释放端口（8003）。
- 删除 `/tmp/mdview-big-source`。
