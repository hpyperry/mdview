# mdview 示例文档

这是 `--root` 下的第一篇示例，用来演示新实现（Rust 单文件）的常用 GFM 子集。

返回上级目录：[目录索引](/)、[子目录说明](guide/install.md)。

## 行内语法

普通段落里有 **粗体**、*斜体*、***粗斜***、`行内代码`、~~删除线~~，
以及 [站内链接](guide/install.md)、[安装页](guide/install.md)、
[外链](https://example.com)。

中文粘着也生效：这句话里有**加粗**和*斜体*，还有 `代码`。
`*` 允许词内强调（`2*3*4` 会变成 2*3*4）；`_` 不允许（`a__b__c` 保持原样），
这与 CommonMark / VS Code 一致。

转义写法：\*不是斜体\*、\`不是代码\`。

裸 HTML 会**原样透传**（Trust + CSP 负责约束脚本）：

<div class="note">这是一个裸 HTML 块；内联 <kbd>Ctrl</kbd>+<kbd>C</kbd> 也能用。</div>

> 新实现不再转义裸 HTML。打开未信任目录时，每个 `.md` 会先出现一次确认页；
> 确认令牌一次性有效。详见 [安装与安全](guide/install.md)。

## 裸 URL 自动链接

正文里手写的 URL 直接可点：访问 https://example.com/mdview 看看。

行内代码与围栏代码块里的 URL 不会被链接化：`https://example.com/code`。

尾随半角标点归句子：见 https://example.com/a. 结束。
括号按配平判定：https://en.wikipedia.org/wiki/A_(b) 保留整个地址，
收尾括号 (见 https://example.com/c) 归句子。

> linkify 采用 comrak 行为（ADR 0007）：`www.example.com` 和裸邮箱也会变成链接；
> 全角句号**会**被算进 URL。这是记录在案的 accepted deviation。

## 列表

紧凑列表：

- 第一项
- 第二项
- 第三项

松散列表（保留段落外壳）：

- 第一项

- 第二项

嵌套列表：

- 外层
  - 子项一
  - 子项二
    1. 三层嵌套的有序项
    2. 再来一个

任务列表按**字面量**显示（与 VS Code 预览一致，不生成 checkbox）：

- [x] 已完成的任务
- [ ] 未完成的任务

有序列表可以从任意数字开始：

4. 从 4 开始
5. 然后 5

## 引用

> 一层引用：mdview 是一个单文件 Rust 程序。
> 续行仍在同一段里。
>
> > 嵌套引用。
>
> 引用里可以有**强调**和`代码`。

## 代码块

围栏内容不在服务端高亮；页面加载后由内嵌的 highlight.js（完整语言包）
在浏览器里着色，语言标识写成 `language-…` 类名：

```python
import os


def main(root: str = ".") -> None:
    """离线预览。"""
    total = sum(len(p) for p in os.listdir(root))  # 统计文件名长度
    print(f"total={total}, pi={3.14159}")
```

```javascript
// JavaScript 也能高亮
const greet = (name) => `hello ${name}`;
console.log(greet("mdview"));
```

~~~text
波浪号围栏同样支持。
里面的 **星号** 不会被解析成强调。
~~~

不写语言时没有语言类名，代码仍然正常显示；禁用 JS 时只是没有颜色。

## 表格与对齐

| 左对齐 | 居中 | 右对齐 | 默认 |
|:-------|:----:|-------:|------|
| a      | b    |   1234 | 普通 |
| `code` | **粗** | ~~删~~ | 长文本 |

## 分隔线

---

## 标题与锚点

新实现**不生成标题 `id`**（VS Code 核心语义），所以站内跳转请使用显式链接或
`#L<n>` 行锚点。源码视图（`?raw=1`）的每一行都有 `id="L<n>"`，搜索命中就跳到那里。

## 引用式链接

[mdview 仓库说明][repo] 与折叠式 [repo][]，还有简写式 [repo]。

[repo]: https://example.com/mdview "离线 Markdown 预览"

## 实体

`&copy;` → &copy;、`&amp;` → &amp;、`&lt;` → &lt;、`&#65;` → &#65;

---

下一步：

- [**preview/** —— 支持哪些文件能在浏览器里直接看](preview/index.md)
- [install.md](guide/install.md) —— 构建、运行、Trust 与路径规则
- [advanced.md](guide/advanced.md) —— 会被渲染 / 刻意不渲染的边界
- [code-blocks.md](guide/code-blocks.md) —— 代码块与围栏变体
