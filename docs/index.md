# mdview 示例文档

这是 `--root` 下的第一篇示例，用来验证渲染器的**常用 GFM 子集**。

返回上级目录：[目录索引](/)、[子目录说明](guide/install.md)。

## 行内语法

普通段落里有 **粗体**、*斜体*、***粗斜***、`行内代码`、~~删除线~~，
以及 [站内链接](guide/install.md)、[带锚点的链接](guide/install.md#安装步骤)、
[外链](https://example.com) 和 [锚点跳转](#表格与对齐)。

中文粘着也应当生效：这句话里有**加粗**和*斜体*，还有 `代码`。
但 `2*3*4`、`a*b`、`a__b__c` 这种词内定界符会保持原样。

裸 HTML 一律被转义（这是安全设计，不是 bug）：<script>alert('x')</script> 会原样显示。

转义写法：\*不是斜体\*、\`不是代码\`。

## 裸 URL 自动链接

正文里手写的 URL 不必包成链接，直接就是可点的：访问 https://example.com/mdview 看看。

行内代码与围栏代码块里的 URL **不会**被链接化，按字面显示：`https://example.com/code`。

URL 紧邻句末标点时，标点归句子而不进链接：见 https://example.com/a. 结束。
全角句号同样处理：见 https://example.com/b。结束。
括号按配平判定：https://en.wikipedia.org/wiki/A_(b) 保留整个地址，
而这一句的收尾括号 (见 https://example.com/c) 归句子。

已写成链接的写法不受影响：[外链](https://example.com/d)；
链接标签内部的 URL 也不会嵌套成链接：见 [https://example.com/e 说明](guide/install.md)。

## 列表

紧凑列表（条目间无空行）：

- 第一项
- 第二项
- 第三项

松散列表（条目间有空行，保留段落外壳）：

- 第一项

- 第二项

嵌套列表与任务列表：

- [x] 已完成的任务
- [ ] 未完成的任务
  - 子项一
  - 子项二
    1. 三层嵌套的有序项
    2. 再来一个
- [ ] 第三项

有序列表可以从任意数字开始：

4. 从 4 开始
5. 然后 5

## 引用

> 一层引用：mdview 只用 Python 标准库。
> 续行仍在同一段里。
>
> > 嵌套引用。
>
> 引用里可以有**强调**和`代码`。

## 代码块

带语言标识的围栏会做语法高亮：

```python
import os
from http.server import ThreadingHTTPServer


def main(root: str = ".") -> None:
    """只用标准库启动服务。"""
    total = sum(len(p) for p in os.listdir(root))  # 统计文件名长度
    print(f"total={total}, pi={3.14159}")
    return None
```

```javascript
// JavaScript 也能高亮
const greet = (name) => `hello ${name}`;
let n = 0;
while (n < 3) { n += 1; }
console.log(greet("mdview"));
```

```bash
# Shell：注释、变量、管道
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

不写语言时按通用规则高亮：

```
plain {a: 1, b: "two"}   // 数字与字符串仍然有色
```

~~~text
波浪号围栏同样支持。
里面的 **星号** 不会被解析成强调。
~~~

## 表格与对齐

| 左对齐 | 居中 | 右对齐 | 默认 |
|:-------|:----:|-------:|------|
| a      | b    |   1234 | 普通 |
| `code` | **粗** | ~~删~~ | 长文本会被自动换行处理 |

## 分隔线

---

## 引用式链接

[mdview 仓库说明][repo] 与折叠式 [repo][]，还有简写式 [repo]。

[repo]: https://example.com/mdview "零依赖离线 Markdown 预览"

## 实体

`&copy;` → &copy;、`&amp;` → &amp;、`&lt;` → &lt;、`&#65;` → &#65;

---

下一步：

- [**preview/** —— 支持哪些文件能在浏览器里直接看（渲染效果总览）](preview/index.md)
- [install.md](guide/install.md) —— 相对路径、根路径与图片
- [advanced.md](guide/advanced.md) —— 会被渲染 / 刻意不渲染的边界
- [code-blocks.md](guide/code-blocks.md) —— **代码块专项测试**（12 种语言 + 全部围栏变体）
