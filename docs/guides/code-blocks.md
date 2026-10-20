# 代码块与围栏

这篇文档压测**代码块**：围栏变体、行内码保护、缩进式代码块，以及高亮/复制按钮的
实际行为。

## 1. 高亮由浏览器完成

服务端只输出标准结构：

```html
<pre><code class="language-python">…</code></pre>
```

页面加载后，内嵌的 highlight.js 11.11.1（完整语言包）只对**有明确
`language-*` 类且不超过 256 KB** 的 `pre code` 调用 `highlightElement`。因此：

- 语言标识映射为 `language-…` 类名，常见语言都有颜色；
- 不写语言时**不做自动探测**，保持纯文本（与 VS Code Markdown 预览一致）；
- 写了未知语言（例如 `foobar`）时保持纯文本；
- `text` / `plaintext` / `txt` 明确声明纯文本，不着色；
- 超过 256 KB 的代码块跳过高亮，语言条标注“高亮已关闭”；
- 禁用 JavaScript 时没有颜色，但代码内容完整可读。

### Python

```python
#!/usr/bin/env python3
import os
from typing import Dict, List, Optional

MAX_RETRY = 3          # 常量与数字
PI = 3.14159


class MarkdownView:
    """三引号字符串也算字符串。"""

    def __init__(self, root: str) -> None:
        self.root = root
        self._cache: Dict[str, str] = {}

    def render(self, paths: List[str]) -> Optional[str]:
        if not paths:
            return None
        return "\n".join(self._cache[p] for p in paths if p in self._cache)
```

### JavaScript / TypeScript

```javascript
// 单行注释
const greet = (name) => `hello ${name}`;
let total = 0;

async function load(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("bad status");
  return res.json();
}

console.log(greet("mdview"), total);
```

```typescript
interface Doc { id: number; title: string; tags?: string[] }

function pick(doc: Doc): string {
  return doc.tags?.[0] ?? doc.title;
}
```

### Shell / SQL / YAML

```bash
#!/usr/bin/env bash
set -euo pipefail
for f in *.md; do
  echo "== $f"
  grep -n "TODO" "$f" | head -5
done
```

```sql
-- SQL 关键字大小写都能识别
SELECT id, title FROM docs
WHERE status = 'active' AND score > 90
ORDER BY score DESC LIMIT 10;
```

```yaml
services:
  web:
    image: mdview:2.0
    ports:
      - "8000:8000"
    environment:
      MODE: offline
```

### Dockerfile / Makefile

围栏语言写 `dockerfile` / `makefile`；源码查看页对这两个文件名也会自动套用语言类。

```dockerfile
FROM scratch
COPY mdview /mdview
RUN ["/mdview", "--version"]
USER 1000
```

```makefile
all:
	cargo build --release

test:
	cargo test
	cargo clippy --all-targets -- -D warnings
```

## 2. 复制按钮

每个代码块由脚本注入一个「复制」按钮，位置在代码块右上角：

- **悬停或键盘聚焦时显示**，触摸屏上点击代码块即可看到；
- 复制内容是 `code.innerText`（渲染后的文本，不含高亮标签与按钮自身）；
- `navigator.clipboard` 不可用（例如 `http://` 非安全上下文）时回落到
  `document.execCommand("copy")`；
- 按钮只在 JS 运行时创建；禁用 JS 的基线 HTML 里没有死按钮。

## 3. 围栏变体

### 3.1 波浪号围栏

~~~text
波浪号围栏里的 **星号** 和 `反引号` 都是字面量
~~~

### 3.2 更长的围栏（4 个反引号）

````text
````
三个反引号在内层只是普通文本：
```python
print("这层不会被解析成独立代码块")
```
````
````

### 3.3 缩进的围栏（最多 3 个空格）

   ```python
   x = 1  # 围栏前面缩进 3 个空格
   ```

### 3.4 未闭合的围栏

```python
def tail():
    return "EOF"
```

未闭合围栏会一直吃到文档结尾，不报错。

## 4. 刻意不解析的情况

### 4.1 围栏内的 Markdown

下面块里不会出现 `<h1>`、`<strong>`、`<a>`、`<ul>`：

```markdown
# 这不是标题
**这不是粗体**
- 这不是列表
[这不是链接](https://example.com)
> 这不是引用
<div>这不是 HTML</div>
```

### 4.2 行内代码保护

- `` `**不是粗体**` `` → `**不是粗体**`
- `` `2*3*4` `` → `2*3*4`
- `` `[不是链接](x.md)` `` → `[不是链接](x.md)`
- 双反引号：`` `` `反引号` `` `` → `` `反引号` ``

行内码里的反斜杠按 CommonMark 保留（不处理转义）。

### 4.3 缩进式代码块

CommonMark 支持 4 空格缩进的代码块，下面四行会渲染成 `<pre><code>`：

    this is indented four spaces
    it renders as code, not a paragraph
    because four leading spaces start an indented code block

### 4.4 围栏里的引用定义

```markdown
[r]: https://evil.example
```

上面的定义留在代码块里，不会被当成文档级引用定义；正文里的 `[r]` 仍然是字面量。

## 5. 混排场景

### 5.1 表格里的代码

| 语法 | 渲染 | 说明 |
|------|------|------|
| 围栏 | ```` ```python ```` | 输出 `language-python` |
| 行内 | `code` | 素色，无高亮 |
| 未知语言 | ```` ```foobar ```` | 保持纯文本 |
| 纯文本 | ```` ```text ```` | 明确不着色 |

### 5.2 引用里的代码块

> 引用内也能放代码块：
>
> ```python
> def in_quote():
>     return "引用里的代码块"
> ```
>
> 以及行内 `code`。

### 5.3 列表里的代码块

1. 第一步：

   ```bash
   cargo build --release
   ```

2. 第二步：

   ```bash
   ./target/release/mdview --root docs
   ```

### 5.4 相邻的多个代码块

```python
first = 1
```
```python
second = 2
```
```python
third = 3
```

三个块独立渲染，不合并。

---

[返回首页](../index.md) · [边界与约定](advanced.md) · [安装说明](install.md)
