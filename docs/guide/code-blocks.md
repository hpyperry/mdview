# 代码块渲染测试

这篇文档专门压测**代码块**：每一种内置语言的围栏（17 种）、所有围栏变体、以及刻意不解析的情况。
用它一句话验收：**每个块下面标注的「期望」都应该成立**。

对照表见 [README 的语法矩阵](../../README.md) 与 [边界与约定](advanced.md)。

---

## 1. 语言标识与高亮

### 1.1 Python（`python` / `py`）

期望：`def`/`import`/`return` 着色为关键字，字符串与注释着色，函数名着色。

```python
#!/usr/bin/env python3
import os
from typing import Dict, List, Optional

MAX_RETRY = 3          # 常量与数字
PI = 3.14159


class MarkdownView:
    """三引号字符串也算字符串。"""

    def __init__(self, root: str, depth: int = 0) -> None:
        self.root = root
        self.depth = depth
        self._cache: Dict[str, str] = {}

    def render(self, paths: List[str]) -> Optional[str]:
        if not paths:
            return None
        parts = [self._cache[p] for p in paths if p in self._cache]
        return "\n".join(parts) or f"{len(paths)} files, {PI=}"
```

### 1.1.1 复制按钮

每个代码块由**语言条 + 代码区两段叠放**构成：语言名在左上，复制按钮在右上，
**一直显示**（鼠标移上去变蓝，点击后短暂变绿提示已复制）。
没有语言标识的块不渲染语言条，避免多出一条空白带。
点击后按钮短暂变成「已复制」，复制的是**渲染后的代码文本**——不含高亮标签、
也不含按钮自己的文字。

按钮是**由脚本注入**的：禁用 JavaScript 时页面上不会出现一个点了没反应的死按钮，
代码依然可以正常阅读和手动选择复制。

> 如果你在 `http://` 下访问（内网常见），`navigator.clipboard` 因非安全上下文不可用，
> 脚本会自动回落到 `document.execCommand("copy")`，功能不受影响。

### 1.2 JavaScript / TypeScript（`javascript` `js` `typescript` `ts`）

期望：模板字符串、箭头函数、`const`/`let`/`async` 着色。

```javascript
// 单行注释
const greet = (name) => `hello ${name}`;
let total = 0;

async function load(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error("bad status");
  return res.json();
}

class Widget {
  constructor(id) { this.id = id; }
  static create(id) { return new Widget(id); }
}

/* 块注释
   跨行 */
console.log(greet("mdview"), total, Widget.create(1));
```

```typescript
interface Doc { id: number; title: string; tags?: string[] }

type Loader = (path: string) => Promise<Doc>;

const load: Loader = async (path) => {
  const doc: Doc = { id: 1, title: path, tags: ["md"] };
  return doc;
};

export default load;
```

### 1.3 Go（`go`）

期望：`func`/`package`/`defer`/`chan` 着色。

```go
package main

import "fmt"

type Server struct {
	Name string
	Port int
}

func (s *Server) Addr() string {
	defer fmt.Println("done") // defer 也是关键字
	if s.Port == 0 {
		return s.Name
	}
	return fmt.Sprintf("%s:%d", s.Name, s.Port)
}

func main() {
	s := &Server{Name: "mdview", Port: 8000}
	fmt.Println(s.Addr())
}
```

### 1.4 Rust（`rust` / `rs`）

期望：`fn`/`impl`/`let mut`/`match` 着色。

```rust
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct Doc {
    pub id: u64,
    pub title: String,
}

impl Doc {
    fn new(id: u64, title: &str) -> Self {
        Doc { id, title: title.to_string() }
    }

    fn is_empty(&self) -> bool {
        self.title.is_empty()
    }
}

fn main() {
    let mut map: HashMap<u64, Doc> = HashMap::new();
    map.insert(1, Doc::new(1, "readme"));
    match map.get(&1) {
        Some(doc) => println!("{:?}", doc),
        None => eprintln!("missing"),
    }
}
```

### 1.5 Java（`java`）

期望：`public`/`class`/`@Override`/`new` 着色。

```java
package com.example.mdview;

import java.util.List;

public class Renderer {
    private static final int LIMIT = 100;
    private final List<String> paths;

    public Renderer(List<String> paths) {
        this.paths = paths;
    }

    @Override
    public String toString() {
        return String.format("Renderer(%d, limit=%d)", paths.size(), LIMIT);
    }
}
```

### 1.6 C / C++（`c` `cpp` `c++` `h`）

期望：预处理指令按注释色处理（`#` 开头），指针与类型着色。

```c
#include <stdio.h>
#include <stdlib.h>

#define MAX 128

struct node {
    int value;
    struct node *next;
};

int main(void) {
    struct node *head = malloc(sizeof(struct node));
    if (head == NULL) {
        return 1;   /* 老式块注释 */
    }
    head->value = MAX;
    printf("value=%d\n", head->value);
    free(head);
    return 0;
}
```

```cpp
#include <string>
#include <vector>

namespace mdview {

template <typename T>
class Stack {
public:
    void push(const T& v) { items_.push_back(v); }
    bool empty() const { return items_.empty(); }
private:
    std::vector<T> items_;
};

}  // namespace mdview

int main() {
    mdview::Stack<std::string> s;
    s.push("hello");
    return s.empty() ? 1 : 0;
}
```

### 1.7 Shell（`shell` `bash` `sh` `zsh` `console`）

期望：`#` 之后整行是注释，变量与管道着色。

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-docs}"
PORT="${PORT:-8000}"

if [ ! -d "$ROOT" ]; then
  echo "no such dir: $ROOT" >&2
  exit 1
fi

echo "serving $ROOT on :$PORT"
for f in "$ROOT"/*.md; do
  printf '  %s (%s lines)\n' "$f" "$(wc -l < "$f")"
done | sort | head -20

python3 mdview.py --root "$ROOT" --port "$PORT" &
```

### 1.8 SQL（`sql` `mysql` `postgres` `sqlite`）

期望：大写关键字与 `--` 注释着色。

```sql
-- 查询活跃文档
SELECT d.id,
       d.title,
       COUNT(c.id) AS comments
FROM docs AS d
LEFT JOIN comments AS c ON c.doc_id = d.id
WHERE d.status = 'active'
  AND d.score > 90
GROUP BY d.id, d.title
HAVING COUNT(c.id) > 0
ORDER BY comments DESC
LIMIT 10;

INSERT INTO docs (title, status) VALUES ('new doc', 'draft');
UPDATE docs SET status = 'active' WHERE id = 1;
DELETE FROM comments WHERE created_at < '2024-01-01';
```

### 1.9 JSON / YAML（`json` `yaml` `yml`）

```json
{
  "name": "mdview",
  "version": "1.0.0",
  "deps": [],
  "features": { "search": true, "highlight": true, "count": 3 },
  "tags": ["offline", "stdlib", null]
}
```

```yaml
name: mdview
version: 1.0.0
deps: []
serve:
  host: 0.0.0.0
  port: 8000
  depth: 0
  safe: false
features:
  - search
  - highlight
  - toc: false
```

### 1.10 未知语言与不写语言

`brainfuck` 不在内置表里 → 退化为**通用规则**：注释、字符串、数字仍然着色。

```brainfuck
// 未知语言：关键字识别不到，但注释/字符串/数字仍会着色
++++++++[>++++[>+++<-]<-]>>.   # 这一行按注释处理
"a string" 12345
```

不写语言标识 → **整块素色**，并且不显示语言标签（避免空标题栏）。
这是刻意的：高亮只服务于"声明了语言"的块，没写语言的块按原文看待。

```
plain text {a: 1, b: "two"}  // 这里不会出现任何着色 span
没有任何语法的普通文本
```

### 1.11 Dockerfile（`dockerfile` / `docker` / `containerfile`）

期望：指令**大小写都识别**（`RUN` 与 `run` 都着色），`#` 整行注释，
镜像标签里的 `3.12` 与 `C.UTF-8` 里的 `8` **不应该**被当成数字。

```dockerfile
# 多阶段构建：builder 里装依赖，运行时镜像只带成品
FROM python:3.12-slim AS builder
ARG PIP_INDEX_URL=https://pypi.example.com/simple
ENV PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
run pip install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY mdview.py docs ./docs/
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
VOLUME ["/app/docs"]
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:8000/ || exit 1
LABEL org.opencontainers.image.title="mdview"
ENTRYPOINT ["python3", "mdview.py"]
CMD ["--root", "docs", "--host", "0.0.0.0"]
```

### 1.12 Docker Compose（`docker-compose` / `compose`）

期望：顶层键与常用子键着色，引号里的端口映射是字符串色。

```docker-compose
version: "3.9"

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - PIP_INDEX_URL=https://pypi.example.com/simple
    image: mdview:1.0.0
    container_name: mdview-web
    command: ["--root", "docs", "--port", "8000"]
    ports:
      - "8000:8000"
    volumes:
      - ./docs:/app/docs:ro
    environment:
      - PORT=8000
      - TZ=Asia/Shanghai
    depends_on:
      - cache
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 3s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"

  cache:
    image: redis:7-alpine
    command: redis-server --save ""
    volumes:
      - cache-data:/data

volumes:
  cache-data: {}
```

### 1.13 TOML / INI / Makefile

```toml
# TOML 注释
[server]
host = "0.0.0.0"
port = 8000
safe = true
tags = ["offline", "stdlib"]
```

```ini
; INI 的 ; 注释目前不着色（分号在 C/JS 里是语句结束符，不能全局当注释）
[mdview]
host=0.0.0.0
port=8000
safe=true
# 井号注释可以着色
verbose=false
```

```makefile
# Makefile：ifeq/endif 等着色，菜谱行按 shell 处理
PY := python3
PORT ?= 8000

.PHONY: run test clean

run:
	$(PY) mdview.py --root docs --port $(PORT)

test:
	$(PY) tests/tests_render.py && bash tests/selftest.sh

ifeq ($(OS),Darwin)
open-browser:
	open http://127.0.0.1:$(PORT)/
endif

clean:
	rm -rf __pycache__
```

### 1.14 明确指定纯文本

`text` / `plaintext` / `txt` / `none` / `raw` 都被当作"纯文本声明" → 整块素色
（与"不写语言"行为一致，但**会显示语言标签**，便于读者知道这是刻意的）。

```text
这里 **不应** 出现任何 token 着色
2 + 2 = 4
"引号" 也保持原样
```

---

## 2. 围栏变体

### 2.1 波浪号围栏

期望：与反引号围栏等价，内部 `**` 不被解析。

~~~text
波浪号围栏里的 **星号** 和 `反引号` 都是字面量
~~~

### 2.2 更长的围栏（4 个反引号）

期望：内部可以安全包含 3 个反引号。

````text
````
三个反引号在内层只是普通文本：
```python
print("这层不会被解析成独立代码块")
```
````
````

### 2.3 缩进的围栏（最多 3 个空格）

期望：仍然识别为代码块。

   ```python
   x = 1  # 围栏前面缩进 3 个空格
   ```

### 2.4 未闭合的围栏

期望：一直吃到文档结尾（下面是文档最后一行，不影响其它块的渲染）。

```python
def tail():
    return "EOF"
```

---

## 3. 刻意不解析的情况

### 3.1 围栏内的 Markdown 语法

期望：下面块里**不应该**出现 `<h1>`、`<strong>`、`<a>`、`<ul>`。

```markdown
# 这不是标题
**这不是粗体**
- 这不是列表
[这不是链接](https://example.com)
> 这不是引用
<div>这不是 HTML</div>
```

### 3.2 行内代码保护

期望：行内码里的语法不生效，且内容原样。

- `` `**不是粗体**` `` → `**不是粗体**`
- `` `2*3*4` `` → `2*3*4`
- `` `[不是链接](x.md)` `` → `[不是链接](x.md)`
- 双反引号：`` `` `反引号` `` `` → `` `反引号` ``
- 行内码里含转义：`` `\*转义\*` `` → `\*转义\*`

### 3.3 转义反引号

期望：`\`` 显示为字面反引号（带虚线标记），**不会**开启行内码。

转义写法：\`不是代码\`，而 `这才是代码`。

### 3.4 缩进式代码块（4 空格）

本渲染器**不支持**缩进式代码块（有意取舍：它在真实文档里几乎总是误判）。
下面这四行会被当作普通段落：

    this is indented four spaces
    it renders as a paragraph, not code

期望：上面两行以 `<p>` 呈现，没有 `<pre>`。

---

## 4. 混排场景

### 4.1 表格单元格里的代码

| 语法 | 渲染 | 说明 |
|------|------|------|
| 围栏 | ```python | 带语言标签与高亮 |
| 行内 | `code` | 素色，无高亮 |
| 未知语言 | ```foobar | 退化通用规则 |
| 空语言 | ``` | 通用规则 + 无标签 |

### 4.2 引用里的代码块

> 引用内也能放代码块：
>
> ```python
> def in_quote():
>     return "引用里的代码块"
> ```
>
> 以及行内 `code`。

### 4.3 列表里的代码块

1. 第一步：

   ```bash
   python3 mdview.py --root docs
   ```

2. 第二步：

   ```bash
   curl http://127.0.0.1:8000/
   ```

### 4.4 相邻的多个代码块

```python
first = 1
```
```python
second = 2
```
```python
third = 3
```

期望：三个独立代码块，不合并。

---

## 5. 验收清单

逐条对照上面的块，全部成立才算通过：

| # | 检查项 | 期望 |
|---|--------|------|
| 1 | 17 种语言标识 | 各自关键字着色正确（含 Dockerfile / Compose / TOML / INI / Makefile） |
| 2 | 未知语言（写了标识但不在表里） | 通用规则，注释/字符串/数字有色 |
| 3 | 未写语言 / `text` / `plaintext` / `txt` | 完全不着色（未写语言还不显示标签） |
| 4 | 波浪号围栏 | 与反引号等价 |
| 5 | 4 个反引号围栏 | 内层 3 个反引号保持字面量 |
| 6 | 缩进 3 空格的围栏 | 仍识别为代码块 |
| 7 | 未闭合围栏 | 吃到文末，不报错 |
| 8 | 围栏内的 Markdown | 完全不被解析 |
| 9 | 行内码 | 保护内部语法，内容原样 |
| 10 | 转义反引号 | 字面量，不开启行内码 |
| 11 | 缩进 4 空格 | 当段落（不支持缩进式代码块） |
| 12 | 表格 / 引用 / 列表里的代码块 | 均正常渲染 |
| 13 | 相邻代码块 | 不合并 |
| 14 | 语言标签 | 有语言才显示，空语言不显示空标题栏 |
| 15 | Dockerfile 指令大小写 | `RUN` 与 `run` 都着色 |
| 16 | 数字边界 | `python:3.12`、`C.UTF-8`、`v1.2.3`、`192.168.1.1`、`2024-01-01` 里不切数字 |

---

[返回首页](../index.md) · [边界与约定](advanced.md) · [安装说明](install.md)
