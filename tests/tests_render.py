#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mdview 渲染器回归测试 —— 只用 stdlib，直接 `python3 tests_render.py`。

覆盖：标题/锚点、强调 flanking 规则、行内码与转义、链接与图片重写、
引用嵌套、列表嵌套与紧松、任务列表、表格对齐、代码高亮、裸 HTML 转义、
引用式链接、实体、以及搜索/路径解析等路由辅助函数。
"""

import os
import re
import shutil
import sys
import tempfile
import unittest

# mdview.py 在仓库根（本文件位于 tests/），把它加入 sys.path。
# MDVIEW_FILE 可用于指向别处的同名实现（例如压缩版），校验行为一致：
#   MDVIEW_FILE=dist/mdview.min.py python3 tests/tests_render.py
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ALT = os.environ.get("MDVIEW_FILE")
if _ALT:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("mdview", os.path.abspath(_ALT))
    m = _ilu.module_from_spec(_spec)
    sys.modules["mdview"] = m
    _spec.loader.exec_module(m)
    print("[tests_render] 被测文件: %s" % _ALT)
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import mdview as m  # noqa: E402


def r(src, rel="docs/a.md"):
    return m.render_markdown(src, rel)


class TestInline(unittest.TestCase):
    def test_triple_emphasis(self):
        self.assertIn("<strong><em>双</em></strong>", r("***双***"))
        self.assertIn("<strong><em>粗斜</em></strong> 测试", r("***粗斜*** 测试"))
        self.assertIn("中文<strong><em>粗斜</em></strong>中文", r("中文***粗斜***中文"))
        self.assertIn("<strong><em>粗斜</em></strong>", r("___粗斜___"))

    def test_emphasis(self):
        self.assertIn("<strong>粗体</strong>", r("**粗体**"))
        self.assertIn("<em>斜体</em>", r("*斜体*"))
        self.assertIn("<em>斜体</em>。", r("*斜体*。"))
        self.assertIn("<del>删除</del>", r("~~删除~~"))

    def test_underscore_rules(self):
        # ASCII 词内下划线不算强调；CJK 旁可以成对（否则中文文档里强调全失效）
        self.assertIn("a__b__c", r("a__b__c"))
        self.assertNotIn("<strong>", r("a__b__c"))
        self.assertIn("中文<strong>粗</strong>中文", r("中文__粗__中文"))
        self.assertIn("<strong>粗</strong> 与 <em>斜</em> 并存", r("__粗__ 与 _斜_ 并存"))

    def test_asterisk_intraword(self):
        # 两侧都是 ASCII 字母数字 -> 字面量；CJK 旁按标点处理 -> 成对
        self.assertIn("a*b", r("a*b 和 2*3*4"))
        self.assertIn("2*3*4", r("a*b 和 2*3*4"))
        self.assertIn("中<em>插</em>文", r("中*插*文"))

    def test_adjacent_and_unmatched(self):
        self.assertIn("<strong>a</strong><strong>b</strong>", r("**a****b**"))
        out = r("**a*")
        self.assertIn("**a*", out)
        self.assertNotIn("<strong>", out)
        # 中间那个未配对的 ** 会抢走最近的 closer，这是已文档化的行为
        self.assertIn("<strong>粗体 <strong>内</strong> 粗体</strong>",
                      r("见 **粗体 **内** 粗体** 结束"))

    def test_code_span_protects(self):
        self.assertIn("<code>a**b**c</code>", r("`a**b**c`"))
        self.assertIn("<code>a*b*c</code>", r("`a*b*c`"))

    def test_backslash_escape(self):
        out = r(r"\*不是斜体\*")
        self.assertIn("不是斜体", out)
        self.assertNotIn("<em>", out)
        out = r(r"\`不是代码\`")
        self.assertNotIn("<code>", out)
        self.assertIn("不是代码", out)

    def test_escape_and_code_span_do_not_corrupt_tokens(self):
        """转义与行内码混排时不能漏出占位符（曾经漏出字面量 MK0/MK1）。"""
        cases = [
            r"`\*转义\*`",
            r"| `\*转义\*` | 反斜杠转义优先 |",
            r"\*裸转义\* 与 `代码`",
            r"`a` 和 \`b\` 和 `c`",
            r"\`不是代码\`",
            r"转义写法：\*不是斜体\*、\`不是代码\`。",
            r"`**粗体**` 与 **真粗体**",
            r"``双反引号`` 与 \`单个\`",
        ]
        for src in cases:
            out = r(src)
            for junk in ("MK0", "MK1", "\ue000", "\ue001", "\ue002", "\ue003",
                         "\ue010", "\ue013", "\x00"):
                self.assertNotIn(junk, out, "占位符泄漏: %r -> %r" % (src, out))
        # 被转义的定界符不能变成强调
        self.assertIn('<span class="esc">*</span>x<span class="esc">*</span>', r(r"\*x\*"))
        self.assertNotIn("<em>", r(r"\*x\*"))
        # 行内码里的内容仍然原样保留
        self.assertIn("<code>a**b**c</code>", r("`a**b**c`"))
        self.assertIn("<code>代码</code>", r("`代码`"))

    def test_code_fence_html_is_escaped(self):
        """代码块里的 HTML 必须被转义 —— 曾经原样输出，构成真实 XSS 洞。"""
        payloads = [
            '```html\n<script>alert(1)</script>\n```',
            '```\n<img src=x onerror="alert(1)">\n```',
            '```javascript\ndocument.write("<script>x</script>")\n```',
            '~~~text\n<svg onload=alert(1)>\n~~~',
        ]
        for src in payloads:
            out = r(src)
            for tag in ("<script", "<img", "<svg"):
                self.assertNotIn(tag, out, "代码块内 %s 未转义: %r" % (tag, src))
            self.assertIn("&lt;", out, "代码块内容应被转义: %r" % src)
        # 段落与行内码同样不能漏
        self.assertNotIn("<script", r("<script>x</script>"))
        self.assertNotIn("<script", r("`<script>`")) 
        # 正常代码块仍然可读（尖括号转义但内容保留）
        out = r('```python\nif a < b and c > d:\n    pass\n```')
        self.assertIn("&lt;", out)
        self.assertIn("&gt;", out)
        self.assertIn('<span class="kw">if</span>', out)

    def test_raw_html_escaped(self):
        out = r("<script>alert(1)</script>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_image_alt_is_plain_text(self):
        """alt 取标签的**纯文本**（与 markdown-it / VS Code 一致）。

        旧实现把渲染后的标签 HTML 整个塞进 alt，于是 alt 里会出现 `<strong>`，
        嵌套图片时甚至是一个完整的 `<img …>`；而 alt 是属性值，那既是坏标记
        也是注入点（SELFTEST §25）。行内式与引用式现在同一条口径 ——
        引用式旧实现靠外层 parse_emphasis 顺手解析标签，alt 里因此长出标记。
        """
        self.assertIn('alt="粗"', r("![**粗**](p.png)"))
        self.assertIn('alt="i"', r("![![i](i.png)](p.png)"))
        self.assertIn('alt="a&lt;b&gt;c"', r("![a<b>c](p.png)"))
        self.assertIn('alt="a&amp;b"', r("![a&amp;b](p.png)"))
        self.assertIn('alt="粗"', r("![**粗**][r]\n\n[r]: p.png"))
        self.assertIn('alt="粗"', r("![**粗**][]\n\n[**粗**]: p.png"))

    def test_entities(self):
        self.assertIn("©", r("&copy;"))
        self.assertIn("&amp;", r("&amp;"))
        self.assertIn("&#65;", r("&#65;"))

    def test_autolink(self):
        self.assertIn('<a href="https://example.com"', r("<https://example.com>"))

    def test_reference_link(self):
        out = r('[文字][r1]\n\n[r1]: https://example.com "标题"')
        # 外部协议链接现在也会带上 rel（与行内链接一致，属于修复后的行为）
        self.assertIn('<a href="https://example.com" title="标题" '
                      'rel="noreferrer noopener">文字</a>', out)
        out = r("[r1]\n\n[r1]: https://example.com")
        self.assertIn(">r1</a>", out)


class TestBlocks(unittest.TestCase):
    def test_headings_and_anchors(self):
        self.assertIn('<h1 id="标题">标题</h1>', r("# 标题"))
        self.assertIn('<h3 id="三级">三级</h3>', r("### 三级"))
        self.assertIn('<h2 id="重复">重复</h2>', r("## 重复\n\n## 重复"))
        self.assertIn('id="重复-1"', r("## 重复\n\n## 重复"))

    def test_setext(self):
        # 只支持 === ：\n--- 在真实文档里几乎总是分隔线，不是标题下划线
        self.assertIn('<h1 id="一级">一级</h1>', r("一级\n==="))
        self.assertIn("<hr>", r("二级\n---"))

    def test_hr(self):
        self.assertIn("<hr>", r("---"))
        self.assertIn("<hr>", r("***"))
        self.assertIn("<hr>", r("___"))

    def test_lists_tight_and_loose(self):
        tight = r("- a\n- b")
        self.assertIn("<li>a</li>", tight)
        self.assertNotIn("<li><p>a</p></li>", tight)
        loose = r("- a\n\n- b")
        self.assertIn("<li><p>a</p></li>", loose)

    def test_ordered_start(self):
        self.assertIn('<ol start="4">', r("4. a\n5. b"))
        self.assertIn("<ol>", r("1. a"))

    def test_nested_list(self):
        out = r("- 外层\n  - 内层\n    1. 有序")
        self.assertIn("<ul>", out)
        self.assertIn("内层", out)
        self.assertIn("<ol>", out)
        self.assertGreaterEqual(out.count("<ul>"), 2)

    def test_task_list(self):
        out = r("- [ ] 待办\n- [x] 完成")
        self.assertIn('class="task"', out)
        self.assertIn('<input type="checkbox" disabled>', out)
        self.assertIn('<input type="checkbox" disabled checked>', out)

    def test_blockquote_nested(self):
        out = r("> 一层\n> > 二层")
        self.assertIn("<blockquote>", out)
        self.assertEqual(out.count("<blockquote>"), 2)

    def test_code_fence_and_highlight(self):
        out = r('```python\ndef f(x):\n    return "s"\n```')
        self.assertIn('class="language-python"', out)
        self.assertIn('class="codebanner"', out)          # 语言条与代码区两段叠放
        self.assertIn('<span class="lang">Python</span>', out)
        self.assertIn('<span class="kw">def</span>', out)
        self.assertIn('<span class="str">"s"</span>', out)
        # 无语言标识 -> 素色（决定 5：只高亮带语言标识的围栏）
        out = r("```\nx = 1\n```")
        self.assertNotIn("<span", out)
        self.assertIn("x = 1", out)

    def test_dockerfile_highlighting(self):
        """Dockerfile 指令大小写都着色，且镜像标签/区域设置里的数字不被切。"""
        out = r("```dockerfile\nFROM python:3.12-slim AS b\nrun pip install x\nUSER app\n```")
        for kw in ("FROM", "AS", "run", "USER"):
            self.assertIn('<span class="kw">%s</span>' % kw, out,
                          "Dockerfile 指令 %s 未着色" % kw)
        self.assertIn('class="language-dockerfile"', out)
        self.assertIn("Dockerfile</span>", out)          # 语言标签
        # 数字边界：这些都不该出现 <span class="num">
        for code, lang in [("ENV LANG=C.UTF-8", "dockerfile"),
                           ("FROM python:3.12-slim", "dockerfile"),
                           ("x = v1.2.3", "python"),
                           ('ip = "192.168.1.1"', "python"),
                           ("DATE=2024-01-01", "bash")]:
            got = m.highlight(code, lang)
            self.assertNotIn('<span class="num">', got,
                             "%r 里误切出数字: %r" % (code, got))

    def test_docker_compose_highlighting(self):
        out = r("```docker-compose\nservices:\n  web:\n    image: mdview:1.0\n"
                "    ports:\n      - \"8000:8000\"\n```")
        self.assertIn('<span class="kw">services</span>', out)
        self.assertIn('<span class="kw">image</span>', out)
        self.assertIn('<span class="kw">ports</span>', out)
        self.assertIn("Docker Compose</span>", out)

    def test_fence_content_not_parsed(self):
        out = r("```\n# 不是标题\n**不是粗体**\n```")
        self.assertNotIn("<h1", out)
        self.assertNotIn("<strong>", out)

    def test_tilde_fence(self):
        self.assertIn("<pre><code>", r("~~~\nx\n~~~"))

    def test_table_alignment(self):
        out = r("| a | b |\n|:--|--:|\n| 1 | 2 |")
        self.assertIn('<th style="text-align:left">a</th>', out)
        self.assertIn('<th style="text-align:right">b</th>', out)
        self.assertIn("<td", out)

    def test_table_after_hr(self):
        out = r("文字\n---\n\n| a |\n| - |\n| 1 |")
        self.assertIn("<hr>", out)
        self.assertIn("<table>", out)


class TestRewrites(unittest.TestCase):
    def test_md_link_rewritten(self):
        # URL 与磁盘一致（保留 .md）：服务端对 /x.md 渲染 HTML，刷新/收藏都可靠
        self.assertIn('href="/docs/sub/b.md"', r("[x](sub/b.md)"))
        self.assertIn('href="/docs/sub/b.md#锚"', r("[x](sub/b.md#锚)"))
        self.assertIn('src="/docs/img/a.png"', r("![x](img/a.png)"))

    def test_image_and_relative(self):
        self.assertIn('src="/docs/img/a.png"', r("![x](img/a.png)"))
        self.assertIn('src="/docs/img/a.png"', r("![x](../img/a.png)", "docs/sub/a.md"))

    def test_dotdot_clamped(self):
        # 越界链接保留原文（点了会 404），不会改写成根外路径
        out = r("[x](../../../outside/x.md)", "a.md")
        self.assertIn("../../../outside/x.md", out)   # 越界链接保持原样
        self.assertNotIn('href="/outside', out)
        # 根内的 ../ 正常归一化
        self.assertIn('src="/docs/img/a.png"', r("![x](../img/a.png)", "docs/sub/a.md"))

    def test_absolute_and_external(self):
        self.assertIn('href="https://e.com/x"', r("[x](https://e.com/x)"))
        # 站内绝对路径同样归一化为根相对
        self.assertIn('href="/a/b.md"', r("[x](/a/b.md)"))

    def test_cjk_path_encoded(self):
        out = r("[x](中文目录/说明.md)")
        self.assertIn("href=", out)
        self.assertNotIn("中文目录", out)

    def test_anchor_only(self):
        self.assertIn('href="#锚"', r("[x](#锚)"))


class TestTargetEncoding(unittest.TestCase):
    """markdown 目标 -> URL 的编码规则（对齐 VS Code 1.141 的预览行为）。

    期望值来源：VS Code 1.141.0 内置 markdown-it 14.3.2，加上预览自己的
    `Uri.parse` 链路（先按 `[^?#]*` 切分，再对每段 percent-decode）。开发机上
    可以重跑核对（不进交付物）：

        npm install markdown-it@14.3.2 --cache <可写目录>
        node -e "const M=require('markdown-it');const md=new M({html:true});
                 console.log(md.render('![x](my%20file.png)'))"

    对照的是**目标语义**而不是最终字符串：VS Code 输出文档相对目标
    （`my%20file.png`），本渲染器按设计输出根相对 URL（`/docs/my%20file.png`）。
    三者的规矩：先切 `?`/`#` -> 只解 path 段一次 -> 只编码一次。
    """

    def test_percent20_decoded_once_not_twice(self):
        # 本次修复的 bug：图片目标被编码两次（%20 -> %2520）-> 图片 404
        out = r("![x](my%20file.png)")
        self.assertIn('src="/docs/my%20file.png"', out)
        self.assertNotIn("%25", out)                 # 双重编码的回归线

    def test_percent20_in_directory_component(self):
        out = r("![x](img%20dir/my%20file.png)")
        self.assertIn('src="/docs/img%20dir/my%20file.png"', out)
        self.assertNotIn("%25", out)

    def test_literal_percent_filename_is_reachable(self):
        # 文件名里字面的 % 要写成 %25（字面 %20 就是 %2520）—— 与链接同规矩
        self.assertIn('src="/docs/my%2520file.png"', r("![x](my%2520file.png)"))
        self.assertIn('href="/docs/a%2523b.md"', r("[x](a%2523b.md)"))

    def test_split_query_and_fragment_before_decoding(self):
        # 先切后解：# / ? 在被作者写成 %23 / %3F 时属于文件名，不能被劈成片段
        self.assertIn('href="/docs/a%23b.md"', r("[x](a%23b.md)"))
        self.assertIn('href="/docs/a%3Fb.md"', r("[x](a%3Fb.md)"))
        self.assertIn('src="/docs/img/a%23b.png"', r("![x](img/a%23b.png)"))
        self.assertIn('src="/docs/img/a%3Fb.png"', r("![x](img/a%3Fb.png)"))

    def test_query_and_fragment_kept_verbatim(self):
        self.assertIn('href="/docs/doc.md?raw=1#L10"', r("[x](doc.md?raw=1#L10)"))
        self.assertIn('href="/docs/doc.md?q=a%20b"', r("[x](doc.md?q=a%20b)"))
        self.assertIn('href="/docs/doc.md?q=a+b"', r("[x](doc.md?q=a+b)"))  # + 不是空格
        self.assertIn('href="/docs/sub/b.md#锚"', r("[x](sub/b.md#锚)"))

    def test_percent25_round_trips(self):
        # 真的百分号：%25 解成 %、再编回 %25，往返稳定
        self.assertIn('href="/docs/100%25.png"', r("[x](100%25.png)"))
        self.assertIn('src="/docs/100%25.png"', r("![x](100%25.png)"))

    def test_link_and_image_share_one_rule(self):
        """同一个目标，链接的 href 与图片的 src 必须逐字节相同。

        曾经它们是两条分叉的路：链接多解一次、图片少解一次还多编一次，
        于是同一个 %20 在链接里是空格、在图片里是字面量。这条路不许再分叉。
        """
        for target in ("my%20file.png", "a%23b.png", "100%25.png",
                       "sub%20dir/x.png", "a%2Bb.png", "中文.png"):
            link = re.search(r'href="([^"]*)"', r("[x](%s)" % target))
            image = re.search(r'src="([^"]*)"', r("![x](%s)" % target))
            self.assertIsNotNone(link, target)
            self.assertIsNotNone(image, target)
            self.assertEqual(link.group(1), image.group(1), target)

    def test_obfuscated_scheme_never_executes(self):
        # 协议判定用解码后的串；即便走到属性里，%6aavascript: 也只是相对路径
        self.assertNotIn("href=\"javascript:", r("[x](%6aavascript:alert(1))"))
        self.assertIn('src="%6aavascript:alert(1)"',
                      r("![x](%6aavascript:alert(1))"))

    def test_angle_destination_encodes_inner(self):
        """`](<a b.md>)`：CommonMark 的尖括号目标。

        VS Code 拖拽/粘贴插入的正是这种写法（它把裸空格写进 <>，全程不做百分号
        编码），markdown-it 再把内部空格编成 %20。所以两条路要收敛到同一个结果。
        """
        self.assertIn('href="/docs/a%20b.md"', r("[x](<a b.md>)"))
        self.assertIn('href="/docs/a%20b.md" title="t"', r("[x](<a b.md> \"t\")"))

    def test_angle_and_percent_forms_are_identical(self):
        # markdown-it 里 md.normalizeLink 对两种写法返回同一个串：输出必须逐字节相同
        self.assertEqual(r("![x](img/my%20file.png)"), r("![x](<img/my file.png>)"))
        self.assertEqual(r("[x](a%20b.md)"), r("[x](<a b.md>)"))

    def test_angle_destination_keeps_inner_paren(self):
        # `<>` 内的 ) 是字面量（裸写法会在这里结束目标）；编成 %29 后仍指向同一个文件
        self.assertIn('href="/docs/a%29b.md"', r("[x](<a)b.md>)"))

    def test_angle_destination_with_scheme(self):
        self.assertIn('href="https://e.com/a%20b" rel="noreferrer noopener"',
                      r("[x](<https://e.com/a b>)"))

    def test_angle_destination_not_touched_inside_code_span(self):
        # 预处理发生在行内码之后：代码里写的语法示例必须原样显示
        self.assertIn("<code>![](&lt;a b.png&gt;)</code>", r("`![](<a b.png>)`"))

    def test_nested_angle_image_in_link(self):
        self.assertIn('<a href="/docs/y.md"><img src="/docs/a%20b.png" alt="i"></a>',
                      r("[![i](<a b.png>)](y.md)"))

    def test_bare_space_destination_is_not_a_link(self):
        """裸空格：VS Code 与 CommonMark 都让整条链接不成立，按字面文本输出。

        早期实现把它截断成一条指向 /docs/a 的链接 —— 若恰好存在名为 a 的文件，
        就是静默链错文件（这也是本次一并对齐的原因）。
        """
        out = r("[x](a b.md)")
        self.assertNotIn("<a", out)
        self.assertIn("[x](a b.md)", out)
        self.assertNotIn("<img", r("![x](img/my file.png)"))

    def test_trailing_space_and_title_still_are_links(self):
        # 反方向：目标后只有空白、或只有一个合法 title，链接必须仍然成立
        self.assertIn('href="/docs/a"', r("[x](a  )"))
        self.assertIn('href="/docs/a" title="t"', r("[x](a \"t\")"))
        self.assertNotIn("<a", r("[x](a \"t\" junk)"))


class TestReferenceImages(unittest.TestCase):
    """引用式图片：`![x][ref]` / `![x][]` / `![x]`。

    README §4 一直把「引用式」算作链接与图片都支持，但实现里 `_REF_LINK_RE`
    带着 `(?<!!)`，图片形式从未生效。VS Code（markdown-it）三种写法都能渲染。
    """

    def test_full_reference_image(self):
        self.assertIn('<img src="/docs/img/my%20file.png" alt="x">',
                      r("![x][pic]\n\n[pic]: img/my%20file.png"))

    def test_collapsed_reference_image(self):
        self.assertIn('<img src="/docs/img/my%20file.png" alt="x">',
                      r("![x][]\n\n[x]: img/my%20file.png"))

    def test_shortcut_reference_image(self):
        self.assertIn('<img src="/docs/a%20b.png" alt="x">',
                      r("![x]\n\n[x]: a%20b.png"))

    def test_reference_image_with_angle_definition(self):
        self.assertIn('<img src="/docs/a%20b.png" alt="x">',
                      r("![x][pic]\n\n[pic]: <a b.png>"))

    def test_reference_image_title(self):
        self.assertIn('<img src="/docs/a.png" alt="x" title="t">',
                      r("![x][pic]\n\n[pic]: a.png \"t\""))

    def test_reference_attributes_are_not_reparsed_as_markdown(self):
        """引用式产出的 <a>/<img> 必须是 token，不能再过一遍行内解析。

        旧实现把它们字面写回文本，后面的 parse_emphasis 于是把属性值也当
        markdown：`[r]: _x_.png` 的 href 里被插进 `<em>`，链接直接坏掉
        （图片同理，src 坏掉）。行内式没有这个问题（它的 <a>/<img> 一直是
        token），两条路现在收敛（SELFTEST §25）。
        """
        out = r("[x][r]\n\n[r]: _x_.png")
        self.assertIn('href="/docs/_x_.png"', out)
        self.assertNotIn("<em>", out)
        out = r("![i][r]\n\n[r]: _x_.png")
        self.assertIn('src="/docs/_x_.png"', out)
        self.assertNotIn("<em>", out)
        # 引用式标签仍然走行内解析：强调该生效的照旧生效
        self.assertIn('<a href="/docs/u.md"><strong>粗</strong></a>',
                      r("[**粗**][r]\n\n[r]: u.md"))
        self.assertIn('<a href="/docs/u.md"><em>斜</em></a>',
                      r("[_斜_][r]\n\n[r]: u.md"))

    def test_rejected_protocol_stays_literal(self):
        # javascript:/data: 一律不产出属性；图片与链接的退化方式一致（按原文）
        for src in ("![x][r]\n\n[r]: javascript:alert(1)",
                    "![x][r]\n\n[r]: data:text/html,x"):
            out = r(src)
            self.assertNotIn("<img", out)
            self.assertNotIn("href=", out)

    def test_reference_image_needs_definition(self):
        # 没定义就按原文输出，不能凭空造出图片
        self.assertNotIn("<img", r("![x][nope]"))


class TestAutolinkLiteral(unittest.TestCase):
    """裸 URL（GFM autolink literal）：正文里手写的 http(s):// 直接可点。

    只做 http/https（www. 与裸邮件刻意不做）；尾随标点按 GFM 归还句子。
    """

    def test_bare_https_becomes_link(self):
        out = r("访问 https://example.com/a 看看。")
        self.assertIn('<a href="https://example.com/a" '
                      'rel="noreferrer noopener">https://example.com/a</a>', out)
        self.assertIn("访问 ", out)

    def test_bare_http_with_port_and_trailing_slash(self):
        out = r("打开 http://127.0.0.1:8000/ 即可。")
        self.assertIn('href="http://127.0.0.1:8000/"', out)

    def test_scheme_is_case_insensitive(self):
        self.assertIn(">HTTPS://EXAMPLE.COM/A</a>", r("见 HTTPS://EXAMPLE.COM/A 结束"))

    def test_only_http_and_https(self):
        # www. 与裸邮件刻意不链接化（要猜协议 / 误报率高）
        self.assertNotIn("<a", r("见 www.example.com 说明"))
        self.assertNotIn("<a", r("联系 a@b.com 吧"))
        self.assertNotIn("<a", r("见 javascript:alert(1) 说"))

    def test_trailing_punctuation_belongs_to_sentence(self):
        for ch in (".", ",", ":", ";", "!", "?"):
            out = r("见 https://example.com/a%s 结束" % ch)
            self.assertIn('href="https://example.com/a"', out, ch)
            self.assertIn("</a>%s" % ch, out, ch)

    def test_full_width_punctuation_is_sentence_punctuation(self):
        # 刻意偏离 GFM（它只认半角）：中文文档里 URL 后跟全角句号是常态，
        # 不撇开的话「。结束」会被整段吃进链接。
        out = r("见 https://example.com/a。结束")
        self.assertIn('href="https://example.com/a"', out)
        self.assertIn("</a>。结束", out)

    def test_cjk_inside_url_is_kept(self):
        # 例外：URL 里的汉字不是标点，不能被当成句子边界剥掉
        out = r("见 https://zh.wikipedia.org/wiki/中文条目 结束")
        self.assertIn('href="https://zh.wikipedia.org/wiki/中文条目"', out)

    def test_parentheses_balance_like_gfm(self):
        # 尾括号在 URL 内部有未配对的 `(` 时属于 URL
        out = r("见 https://en.wikipedia.org/wiki/A_(b) 结束")
        self.assertIn('href="https://en.wikipedia.org/wiki/A_(b)"', out)
        # 多出来的那个 `)` 归还句子
        out = r("见 https://en.wikipedia.org/wiki/A_(b)) 结束")
        self.assertIn('href="https://en.wikipedia.org/wiki/A_(b)"', out)
        self.assertIn("</a>) 结束", out)
        # 整体被括号包住时，收尾括号归还句子
        out = r("(见 https://example.com/a)")
        self.assertIn('href="https://example.com/a"', out)
        self.assertIn("</a>)", out)

    def test_trailing_quotes_returned_to_sentence(self):
        out = r('见 "https://example.com/a" 结束')
        self.assertIn('href="https://example.com/a"', out)
        self.assertIn('</a>" 结束', out)

    def test_query_string_escaped_once(self):
        out = r("访问 https://e.com/x?a=1&b=2 结束")
        self.assertIn('href="https://e.com/x?a=1&amp;b=2"', out)
        self.assertNotIn("&amp;amp;", out)

    def test_trailing_entity_keeps_its_semicolon(self):
        # `&copy;` 的 `;` 属于实体，不能被当句末标点剥掉（否则页面漏出 "&copy"）
        out = r("见 https://e.com/a&copy; 结束")
        self.assertIn('href="https://e.com/a&amp;copy;"', out)
        self.assertNotIn("&copy</a>", out)

    def test_not_linkified_inside_code(self):
        self.assertIn("<code>https://e.com/a</code>", r("写成 `https://e.com/a` 即可"))
        self.assertNotIn("<a", r("```\nhttps://e.com/a\n```"))

    def test_angle_autolink_still_works(self):
        self.assertIn('<a href="https://example.com" '
                      'rel="noreferrer noopener">https://example.com</a>',
                      r("<https://example.com>"))

    def test_markdown_link_destination_is_not_linkified(self):
        out = r("见 [x](https://e.com/a) 说明")
        self.assertIn('<a href="https://e.com/a" rel="noreferrer noopener">x</a>', out)
        self.assertEqual(out.count("<a "), 1)

    def test_label_url_is_not_nested(self):
        # HTML 不允许 <a> 嵌 <a>：标签里的 URL 保持纯文本
        out = r("[见 https://example.com/a 说明](other.md)")
        self.assertEqual(out.count("<a "), 1)
        self.assertIn("见 https://example.com/a 说明</a>", out)

    def test_image_alt_is_not_linkified(self):
        out = r("![见 https://e.com/a](p.png)")
        # 唯一的 <a> 是图片放大那层包裹链接（见 TestImageZoom）；标签里的 URL
        # 仍然是纯文本，没有被自动链接化。
        self.assertEqual(out.count("<a "), 1)
        self.assertIn('<a class="zoom" href="/docs/p.png">', out)
        self.assertIn('alt="见 https://e.com/a"', out)

    def test_reference_image_source_is_not_corrupted(self):
        # 回归：早期实现把定义里的 URL 也链接化，产出 src="<a href=…>"
        out = r("![a][r]\n\n[r]: https://e.com/p.png")
        self.assertIn('<img src="https://e.com/p.png" alt="a">', out)
        self.assertNotIn('src="<a', out)
        # 站外图片也照常可放大，包裹链接指向同一个 URL
        self.assertIn('<a class="zoom" href="https://e.com/p.png">', out)

    def test_url_after_markdown_link_is_linkified(self):
        out = r("[x](a.md)https://e.com")
        self.assertIn('href="/docs/a.md"', out)
        self.assertIn('href="https://e.com"', out)

    def test_linkified_in_heading_and_table(self):
        self.assertIn('<a href="https://e.com/a"', r("## 见 https://e.com/a"))
        out = r("| a |\n|---|\n| https://e.com/x |")
        self.assertIn('<td><a href="https://e.com/x"', out)

    def test_no_duplicate_when_text_has_no_scheme(self):
        # 快路径不能漏掉正文：没有 :// 时直接返回原文
        self.assertNotIn("<a", r("普通一段没有链接的文字"))


class TestImageZoom(unittest.TestCase):
    """图片放大：服务端把**不在链接里**的 <img> 包成 `<a class="zoom" href="原图">`。

    这层链接有两个职责：没有 JS 时它就是降级路径（点一下打开原图），有 JS 时
    被脚本接管成遮罩。所以它必须由服务端产出，而且**禁用 JS 时不能出现任何
    点不动的死元素** —— 遮罩与关闭按钮全部由脚本运行时创建（与复制按钮同一
    哲学）。`href` 必须与 `src` 逐字节相同：那条「只解码一次、只编码一次」的
    管线不许被走第二遍。
    """

    def test_inline_image_is_wrapped(self):
        self.assertIn('<a class="zoom" href="/docs/p.png">'
                      '<img src="/docs/p.png" alt="x"></a>', r("![x](p.png)"))

    def test_reference_image_is_wrapped(self):
        for src in ("![x][r]\n\n[r]: p.png", "![x][]\n\n[x]: p.png",
                    "![x]\n\n[x]: p.png"):
            self.assertIn('<a class="zoom" href="/docs/p.png">', r(src))
            self.assertIn('<img src="/docs/p.png" alt="x">', r(src))

    def test_href_is_byte_identical_to_src(self):
        for target in ("my%20file.png", "a%23b.png", "100%25.png", "中文.png",
                       "img%20dir/x%20y.png", "<a b.png>"):
            out = r("![x](%s)" % target)
            href = re.search(r'<a class="zoom" href="([^"]*)"', out).group(1)
            src = re.search(r"<img src=\"([^\"]*)\"", out).group(1)
            self.assertEqual(href, src, target)

    def test_badge_image_inside_link_is_not_wrapped(self):
        """`<a>` 不能套 `<a>`：徽章的外层链接必须原样活着。

        真包上去的话浏览器会把外层链接撕成两半，点徽章变成打开图片而不是跳转。
        """
        out = r("[![i](p.png)](u.md)")
        self.assertNotIn('class="zoom"', out)
        self.assertEqual(out.count("<a "), 1)
        self.assertIn('<a href="/docs/u.md"><img src="/docs/p.png" alt="i"></a>',
                      out)

    def test_wrapped_in_every_block_context(self):
        for src in ("## 图 ![x](p.png)", "- 图 ![x](p.png)",
                    "> 引用 ![x](p.png)",
                    "| a |\n|---|\n| ![x](p.png) |"):
            self.assertIn('<a class="zoom"', r(src), src)

    def test_not_wrapped_inside_code(self):
        self.assertEqual(r("`![x](p.png)`").count('<a class="zoom"'), 0)
        self.assertEqual(r("```\n![x](p.png)\n```").count('<a class="zoom"'), 0)

    def test_rejected_protocol_produces_no_wrapper(self):
        out = r("![x](javascript:alert(1))")
        self.assertNotIn("<img", out)
        self.assertNotIn('class="zoom"', out)

    def test_title_stays_on_the_image(self):
        out = r("![x](p.png \"t\")")
        self.assertIn('<a class="zoom" href="/docs/p.png">'
                      '<img src="/docs/p.png" alt="x" title="t"></a>', out)
        self.assertNotIn("title=", out.split("<img")[0])   # 包裹链接上没有 title

    def test_each_image_wrapped_exactly_once(self):
        out = r("![x](p.png) 与 ![y](q.png)")
        self.assertEqual(out.count('<a class="zoom"'), 2)
        self.assertEqual(out.count("</a>"), 2)

    def test_close_button_is_anchored_to_the_dialog(self):
        """关闭按钮必须贴在图片（dialog 盒）的右上角，不能钉在视口右上角。

        曾经写成 `position:fixed`：按钮飘在视口右上角，于是一来会盖在页面内容上
        （裂图时那里正是浏览器画出来的 alt 文字，也就是文件名），二来把"点空白处
        关闭"的点击抢走 —— 用户点右上角空白，实际点到的是按钮（SELFTEST §27）。
        """
        css = re.sub(r"/\*.*?\*/", "", m.CSS, flags=re.S)
        flat = css.replace(" ", "").replace("\n", "")
        self.assertIn("dialog.zoomdlg.zoomclose{position:absolute", flat)
        self.assertNotIn("dialog.zoomdlg.zoomclose{position:fixed", flat)
        # dialog 自身的 modal 定位要显式写出（且落在基础规则里，见下一条），
        # absolute 的包含块才是这个 dialog 盒
        self.assertIn("position:fixed;inset:0;margin:auto", self._rule(flat, "dialog.zoomdlg"))

    def test_overlay_layout_survives_the_close_animation(self):
        """定位与 flex 排版留在**基础规则**里，`[open]` 只切换 display。

        §28 记录的形态：出场一旦有过渡，摘掉 [open] 后盒子还会显示约半程，谁留在
        [open] 里谁就在这半程退回初始值 —— 三个子元素按默认的 row + stretch 重排，
        × 飞到视口右缘、图片名（caption）挤成右侧一列。§29 把出场改成瞬时的，
        所以这条现在是**结构保险**：几何不随可见性开关变化，将来谁再加回出场过渡
        也不会重演。
        """
        flat = re.sub(r"/\*.*?\*/", "", m.CSS, flags=re.S).replace(" ", "").replace("\n", "")
        base = self._rule(flat, "dialog.zoomdlg")
        for decl in ("position:fixed", "inset:0", "margin:auto",
                     "flex-direction:column", "align-items:center", "gap:10px"):
            self.assertIn(decl, base)
        opened = self._rule(flat, "dialog.zoomdlg[open]")
        self.assertIn("display:flex", opened)
        for decl in ("position", "inset", "margin", "flex-direction",
                     "align-items", "gap"):
            self.assertNotIn(decl, opened)

    def test_close_is_instant_not_an_exit_animation(self):
        """遮罩必须**只做入场动画**：关掉就立刻消失，不许有出场过渡。

        曾经给 dialog 写了 `transition:display .15s allow-discrete,overlay …` ——
        退场那 150ms 里图片与遮罩在淡出，而 × 与 caption 没有 opacity 过渡，会原地
        原样亮着直到 display:none：用户报告"关闭图片后，关闭按钮会停留在原位置很
        短的时间，不符合要求"（SELFTEST §29）。入场那条 @starting-style 路径必须
        原样保留，否则会把入场动画一起删掉。
        """
        css = re.sub(r"/\*.*?\*/", "", m.CSS, flags=re.S)   # 注释里会引用那条错写法
        flat = css.replace(" ", "").replace("\n", "")
        self.assertNotIn("allow-discrete", flat)
        self.assertNotIn("transition:display", flat)
        # 入场动画的三件套一件都不能少
        self.assertIn("@starting-style{dialog.zoomdlg[open]img{opacity:0;transform:scale(.97)}}", flat)
        self.assertIn("transition:opacity.15sease,transform.15sease", flat)
        self.assertIn("@starting-style{dialog.zoomdlg[open]::backdrop{opacity:0}}", flat)
        self.assertIn("transition:opacity.15sease}", flat)     # ::backdrop 只过渡 opacity

    @staticmethod
    def _rule(flat_css, selector):
        """从压掉空白的 CSS 里取出某个规则的声明体（不含花括号）。"""
        match = re.search(re.escape(selector) + r"\{([^}]*)\}", flat_css)
        if not match:
            raise AssertionError("CSS 里找不到规则: " + selector)
        return match.group(1)

    def test_close_icon_is_a_centred_svg_not_a_font_glyph(self):
        """× 必须是**现画的 SVG**，并靠 flex 落在按钮正中间，不能用字体字形。

        字体里的 U+00D7 在 em 盒里并不居中，而且各字体偏得还不一样：canvas 实测
        22px 下 macOS 系统字体要抬 ~2.3px，Arial / Hiragino 几乎不用动 —— 写死任何
        px 校正值都会在别的平台翻车（SELFTEST §30）。曾经那条 `font:20px/1 inherit`
        非法简写只影响字形大小，换成 SVG 后字号这条规格作废，因此这里改钉"图标是
        SVG + 按钮 flex 居中 + 不再往按钮里写字形文本"。
        """
        css = re.sub(r"/\*.*?\*/", "", m.CSS, flags=re.S)   # 注释里会引用那条错写法
        flat = css.replace(" ", "").replace("\n", "")
        self.assertNotIn("font:20px/1 inherit", css)        # 那条错写法不许回来
        close = self._rule(flat, "dialog.zoomdlg.zoomclose")   # 已压掉空白
        self.assertIn("display:flex", close)
        self.assertIn("align-items:center", close)
        self.assertIn("justify-content:center", close)
        self.assertIn("width:24px;height:24px",
                      self._rule(flat, "dialog.zoomdlg.zoomclosesvg"))
        # 脚本里必须真的画 SVG（两条对角线、无填充、currentColor 描边）
        self.assertIn('createElementNS(SVG_NS, "svg")', m.COPY_JS)
        self.assertIn('createElementNS(SVG_NS, "path")', m.COPY_JS)
        self.assertIn('setAttribute("d", "M7.5 7.5 16.5 16.5M16.5 7.5 7.5 16.5")', m.COPY_JS)
        self.assertIn('setAttribute("fill", "none")', m.COPY_JS)
        self.assertIn('setAttribute("stroke", "currentColor")', m.COPY_JS)
        self.assertNotIn('textContent = "\u00d7"', m.COPY_JS)   # 不再用字体字形

    def test_open_focus_lands_on_the_dialog_not_the_button(self):
        """打开后的初始焦点必须落在遮罩自己，不能落在 × 上。

        showModal() 会把焦点送给 dialog 里第一个可聚焦元素 —— 那颗 ×。上一轮交互若是
        键盘（例如刚用 Esc 关过一次），这次**程序化**聚焦就会命中 `:focus-visible`：
        再打开时按钮带着一圈白边，看起来像被"选中"了（用户报告，SELFTEST §31）。
        修法是给遮罩 `tabindex="-1"` 并在 showModal() 之后把焦点收回来。
        注意不能为了消白边把键盘焦点指示一起删掉 —— 按 Tab 走到 × 时那圈白环照旧要有。
        """
        self.assertIn("d.tabIndex = -1", m.COPY_JS)
        self.assertIn("zoom.showModal();", m.COPY_JS)
        self.assertIn("zoom.focus();", m.COPY_JS)
        # focus() 必须排在 showModal() 之后，否则会被 showModal() 的自动聚焦盖回去
        self.assertLess(m.COPY_JS.index("zoom.showModal();"),
                        m.COPY_JS.index("zoom.focus();"))
        flat = re.sub(r"/\*.*?\*/", "", m.CSS, flags=re.S).replace(" ", "").replace("\n", "")
        self.assertIn("dialog.zoomdlg:focus{outline:none}", flat)      # 遮罩不是控件
        self.assertIn("dialog.zoomdlg.zoomclose:focus-visible{outline:2pxsolid#fff", flat)

    def test_no_dead_overlay_without_js(self):
        """基线 HTML 里不能有写死的遮罩/关闭按钮；它们全由那段 JS 创建。"""
        page = m._page("t", m.render_markdown("![x](p.png)"))
        body = page.split("<body>")[1].split("<script>")[0]
        self.assertNotIn("<dialog", body)
        self.assertNotIn('class="zoomclose"', body)
        self.assertIn('createElement("dialog")', page)
        self.assertIn("showModal", page)


class TestBackToTop(unittest.TestCase):
    """回到顶部：**只在目录页**出现（文件预览页不装），固定在视口右下角，点击回到顶部。

    按钮由 COPY_JS 运行时创建，服务端只给 `<body>` 打一个 `data-totop` 标记 —— 与复制
    按钮、放大遮罩同一哲学：禁用 JS 的基线里不能出现点不动的死按钮。
    """

    def test_only_dir_pages_get_the_marker(self):
        self.assertEqual('<body data-totop="1">',
                         self._body_tag(m._page("t", "<p>x</p>", to_top=True)))
        self.assertEqual("<body>", self._body_tag(m._page("t", "<p>x</p>")))   # 默认不装
        # 搜索页 / 错误页也走默认分支；文件预览页由端到端断言（selftest.sh 里查真页面）
        self.assertEqual("<body>", self._body_tag(
            m.render_search_page("q", [], [], 0, False)))
        self.assertEqual("<body>", self._body_tag(m._error_page("404", "文件不存在")))

    def test_button_is_injected_by_script_not_baked_in(self):
        page = m._page("t", "<p>x</p>", to_top=True)
        body = page.split("</head>", 1)[1].split("<script>")[0]
        self.assertNotIn('class="totop"', body)          # 基线里没有死按钮
        self.assertEqual('<body data-totop="1">', self._body_tag(page))   # 只有一个标记
        self.assertIn('className = "totop"', m.COPY_JS)  # 按钮由脚本创建
        self.assertIn('document.body.hasAttribute("data-totop")', m.COPY_JS)
        self.assertIn("document.body.appendChild(toTop)", m.COPY_JS)
        self.assertIn('setAttribute("aria-label", "\u56de\u5230\u9876\u90e8")', m.COPY_JS)

    def test_button_is_fixed_to_the_bottom_right_corner(self):
        flat = re.sub(r"/\*.*?\*/", "", m.CSS, flags=re.S).replace(" ", "").replace("\n", "")
        rule = re.search(r"\.totop\{([^}]*)\}", flat)
        self.assertIsNotNone(rule, "CSS 里找不到 .totop 规则")
        for decl in ("position:fixed", "right:20px", "bottom:20px"):
            self.assertIn(decl, rule.group(1))

    def test_click_scrolls_back_to_the_top(self):
        self.assertIn("window.scrollTo({ top: 0, behavior: \"smooth\" })", m.COPY_JS)
        self.assertIn('matchMedia("(prefers-reduced-motion: reduce)")', m.COPY_JS)

    @staticmethod
    def _body_tag(page):
        # CSS 注释里也会出现字面的 <body>，所以只从 </head> 之后找真正的 body 标签
        match = re.search(r"<body[^>]*>", page.split("</head>", 1)[1])
        if not match:
            raise AssertionError("页面里找不到 <body> 标签")
        return match.group(0)


class TestCopyButton(unittest.TestCase):
    """代码块复制按钮：由 JS 注入，基线（禁用 JS）下不能出现死按钮。"""

    def test_page_includes_script_once(self):
        out = m._page("t", "<p>x</p>")
        self.assertEqual(out.count("<script>"), 1)
        self.assertIn("</script>", out)

    def test_button_is_injected_not_hardcoded(self):
        """按钮必须由 JS 创建 —— HTML 里出现 .copybtn 就是死按钮。"""
        page = m._page("t", m.render_markdown("```python\nx = 1\n```"))
        self.assertNotIn('class="copybtn"', page)
        self.assertIn('createElement("button")', page)
        self.assertIn('className = "copybtn"', page)

    def test_button_goes_into_banner(self):
        """按钮追加到语言条右侧（DSH 式两段叠放），无语言块由 JS 补条。"""
        page = m._page("t", "")
        self.assertIn('querySelector(".codebanner")', page)
        self.assertIn("banner.appendChild(btn)", page)
        self.assertIn("insertBefore(banner, block.firstChild)", page)

    def test_banner_only_when_labeled(self):
        """有语言 -> 渲染语言条；无语言 -> 不留空白带（JS 需要时再补）。"""
        self.assertIn('class="codebanner"', r("```python\nx=1\n```"))
        self.assertNotIn('class="codebanner"', r("```\nx=1\n```"))

    def test_clipboard_paths_covered(self):
        """必须同时有 Clipboard API 与 http 场景的 execCommand 兜底。"""
        page = m._page("t", "")
        self.assertIn("navigator.clipboard", page)
        self.assertIn("isSecureContext", page)
        self.assertIn("execCommand", page)

    def test_extracts_rendered_text_from_code(self):
        """复制的内容取自 pre>code 的 innerText，不含按钮自身文字。"""
        page = m._page("t", "")
        self.assertIn('querySelector("pre > code")', page)
        self.assertIn("innerText", page)
        # 反馈文案存在，且复制按钮有 aria 标签（可访问性）
        self.assertIn("aria-label", page)

    def test_css_always_visible(self):
        """按钮常显，不做悬停隐藏。

        注意只在按钮自身的规则块里断言：页面上别处有合法的 opacity:0
        （源码视图的 .srcline:target 高亮）。
        """
        page = m._page("t", "")
        start = page.index(".copybtn{")
        block = page[start:page.index("@media print{.copybtn")]
        self.assertNotIn("opacity", block, "按钮规则里不该有透明度切换")
        self.assertNotIn("@media (hover:none)", page)     # 常显就不需要触屏特例
        self.assertIn(".copybtn:hover{color:var(--accent)}", page)
        self.assertIn("@media print{.copybtn{display:none}}", page)
        # 顶部条是 flex + space-between（左侧语言名、右侧复制按钮）
        self.assertIn(".codeblock .codebanner{display:flex", page)
        self.assertIn("justify-content:space-between", page)


class TestReviewRegressions(unittest.TestCase):
    """第二轮评审（S 系列）发现的缺陷回归。

    每条都对应一个实测过的坏行为，避免以后再犯。
    """

    def test_link_scan_is_linear(self):
        """S17：链接解析必须线性。

        旧正则在 `"[x](" * 20000`（78 KB）上要 59 秒，单请求即可打满线程。
        这里给一个宽松上界（正常应在 0.05 秒内），只为拦住平方级退化。
        """
        import time
        src = "[x](" * 20000
        t = time.time()
        m.render_markdown(src)
        self.assertLess(time.time() - t, 5.0, "链接解析疑似退化成平方级")

    def test_deep_nesting_no_crash(self):
        """S2：极深嵌套不能变成 500。"""
        for src in (">" * 1000, "- " + "- " * 500 + "x", "[".join(["a"] * 200)):
            out = m.render_markdown(src)          # 不应抛异常
            self.assertIsInstance(out, str)
            self.assertTrue(out)

    def test_literal_token_does_not_crash(self):
        """S3：文档里字面写出 token 形式不能 IndexError。"""
        for src in ("\x00MK0\x00", "# \x00MK3\x00", "> \x00MK0\x00"):
            self.assertIsInstance(m.render_markdown(src), str)

    def test_escaped_gt_no_marker_leak(self):
        """S7：转义的大于号曾经漏出私有区标记。"""
        out = m.render_markdown("\\>\n")
        self.assertNotIn("\ue000", out)
        self.assertNotIn("\ue001", out)
        self.assertIn('class="esc"', out)
        self.assertIn("&gt;", out)

    def test_code_span_no_placeholder_leak(self):
        """S8：行内码里的转义不能漏出 MK0 / 屏蔽字符。"""
        for src in ("`\\*`", "`a\\`b`", "`\\>`"):
            out = m.render_markdown(src + "\n")
            self.assertNotIn("MK0", out, "%r 漏出占位符: %r" % (src, out))
            for ch in ("\ue010", "\ue013", "\ue000", "\ue001"):
                self.assertNotIn(ch, out, "%r 漏出屏蔽字符" % src)

    def test_nul_is_stripped(self):
        """S9：NUL 是 HTML 非法字符，且是内部定界符。"""
        out = m.render_markdown("a\x00b\n")
        self.assertNotIn("\x00", out)
        self.assertIn("ab", out)

    def test_heading_ids_never_collide(self):
        """S16：`a` / `a-1` / `a` 曾经生成 a、a-1、a-1。"""
        import re as _re
        for src in ("## a\n## a-1\n## a", "## 重复\n\n## 重复",
                    "# a\n# a\n# a"):
            ids = _re.findall(r'id="([^"]*)"', m.render_markdown(src))
            self.assertEqual(len(ids), len(set(ids)), "id 冲突: %s" % ids)

    def test_link_label_nested_image_survives(self):
        """S5：徽章写法里的 <img> 不能被转义成文本。"""
        out = m.render_markdown("[![build](badge.svg)](https://ci.example/run)\n")
        self.assertIn("<img", out)
        self.assertNotIn("&lt;img", out)
        self.assertIn('href="https://ci.example/run"', out)

    def test_emphasis_inside_inline_link_label(self):
        """S6：行内链接标签里的强调要生效（引用式早就能，行内曾经不能）。"""
        out = m.render_markdown("[**bold**](x.md)\n")
        self.assertIn("<strong>bold</strong>", out)
        self.assertNotIn("**bold**", out)

    def test_url_with_balanced_parens(self):
        """S12：URL 里的配对括号不能被截断。"""
        out = m.render_markdown("[x](https://e.com/wiki/Foo_(bar))\n")
        self.assertIn("Foo_(bar)", out)
        self.assertNotIn("</a>)", out)

    def test_reference_definitions_ignored_in_fences(self):
        """S15：围栏里的 [r]: 不能被当成引用定义。"""
        out = m.render_markdown("```\n[r]: https://evil.example\n```\n\n[r]\n")
        self.assertIn("[r]: https://evil.example", out)
        self.assertNotIn('href="https://evil.example"', out)

    def test_bare_dashes_not_a_table(self):
        """S14：`文字 | 文字` + `---` 必须仍是分隔线，不是表格。"""
        out = m.render_markdown("文字 | 文字\n---\n")
        self.assertNotIn("<table>", out)
        self.assertIn("<hr>", out)

    def test_parse_size_no_overflow_and_exact(self):
        """S19/S20：超大输入要报错而不是 OverflowError；大整数不能丢精度。"""
        self.assertEqual(m._parse_size("9007199254740993"), 9007199254740993)
        with self.assertRaises(ValueError):
            m._parse_size("9" * 309)


class TestParentLinkAtRootBoundary(unittest.TestCase):
    """上级目录链接指到根时不能拼出 `//`。

    `//` 会被浏览器当作**协议相对 URL**（`//host/`），导航被拦成
    about:blank#blocked —— 用户实测报过：在根下的一级子目录里点"上级目录"就中招。
    """

    def test_root_with_trailing_slash_is_single_slash(self):
        self.assertEqual(m.url_for_rel("", trailing_slash=True), "/")
        self.assertEqual(m.url_for_rel("", trailing_slash=False), "/")

    def test_never_double_slash(self):
        for rel in ("", "/", "a", "a/", "a/b", "/a//b", "a//b", "a b/c d"):
            for ts in (False, True):
                url = m.url_for_rel(rel, trailing_slash=ts)
                self.assertFalse(url.startswith("//"),
                                 "%r (trailing_slash=%s) 拼出了 %r" % (rel, ts, url))
                self.assertTrue(url.startswith("/"), url)

    def test_parent_link_href_for_top_level_dir(self):
        """一级子目录的上级必须是 `/`，不是 `//`。"""
        html = m.Handler._parent_link("guide")
        self.assertIn('href="/"', html)
        self.assertNotIn('href="//"', html)

    def test_parent_link_nested(self):
        self.assertIn('href="/guide/"', m.Handler._parent_link("guide/sub"))

    def test_parent_link_empty_at_root(self):
        self.assertEqual(m.Handler._parent_link(""), "")


class TestSniffingFallback(unittest.TestCase):
    """第三层：前两层（白名单 / MIME 表）都没意见时，用内容嗅探兜底。

    这让"没登记过的文本文件"自动可预览，代价是"前 512 字节无 NUL 的二进制"
    会被当成文本（下面 test_known_tradeoff_* 显式记录这一点）。
    """

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _write(self, name, data):
        p = os.path.join(self.d, name)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    # ---- 新增能力：没登记过的文本也能预览 ----
    def test_unregistered_text_previews(self):
        for name in ("weird.random", "notes.xyz", "data.unknown", "x.plist",
                     "a.bin", "no-extension-at-all"):
            p = self._write(name, "纯文本内容，没有 NUL\n".encode())
            ctype, download = m.resolve_ctype(p)
            self.assertEqual(ctype, m.TEXT_MIME_DEFAULT,
                             "%s 应当靠嗅探预览" % name)
            self.assertFalse(download)

    def test_plist_text_now_previews(self):
        """XML 文本的 .plist 不再被下载 —— 嗅探修正了扩展名表的盲区。"""
        p = self._write("x.plist",
                        b'<?xml version="1.0"?>\n<plist><dict/></plist>\n')
        self.assertEqual(m.resolve_ctype(p)[0], m.TEXT_MIME_DEFAULT)

    def test_unregistered_binary_downloads(self):
        for name in ("blob.dat", "x.qwerty", "noext"):
            p = self._write(name, b"header\x00\x01\x02binary")
            self.assertEqual(m.resolve_ctype(p)[0], m.BINARY_MIME,
                             "%s 含 NUL，应当下载" % name)

    # ---- 前两层优先：不能被嗅探抢走 ----
    def test_whitelist_wins_over_sniffing(self):
        """白名单命中就**不读文件**：即使内容里有 NUL 也按文本发。

        这是白名单的价值之一（零开销 + 类型更准）。
        """
        p = self._write("weird.py", b"\x00\x00\x00")
        self.assertEqual(m.resolve_ctype(p)[0], m.TEXT_MIME_DEFAULT)

    def test_mime_table_wins_over_sniffing(self):
        """PDF 前 512 字节几乎全是 ASCII、没有 NUL ——
        嗅探会判成文本，只有 MIME 表能保住它内联显示。"""
        # 用仓库根定位夹具，不能按 m.__file__ —— 被测文件可能位于 dist/
        pdf_path = os.path.join(REPO_ROOT, "docs", "preview", "binary", "real.pdf")
        with open(pdf_path, "rb") as fh:
            pdf = fh.read()
        p = self._write("doc.pdf", pdf)
        self.assertFalse(m._is_binary(p), "前提：这个 PDF 确实没有 NUL")
        self.assertEqual(m.resolve_ctype(p)[0], "application/pdf")

    def test_image_types_unchanged(self):
        for name, want in (("a.png", "image/png"), ("a.gif", "image/gif"),
                           ("a.svg", "image/svg+xml"), ("a.pdf", "application/pdf")):
            p = self._write(name, b"x")
            self.assertEqual(m.resolve_ctype(p)[0], want)

    # ---- 已知代价：显式记录，避免以后被当成 bug 反复"修" ----
    def test_known_tradeoff_ascii_headed_binary_displays_as_text(self):
        """前 512 字节无 NUL 的二进制会被判成文本（有意承担）。

        真实例子：纯 ASCII 头的 `.tar`、头 512 字节恰好没有 NUL 的二进制。

        **曾经写错了这条**：我原先把 `.docx`/`.xlsx` 也列在这里，理由是
        "它们本质是 ZIP"。实测**不成立** —— 真实 Office 文件的 ZIP 本地文件头
        在**偏移 4-5 就有 NUL**，所以正确判为二进制。当时那个"反例"是我自己
        用 `b"PK\x03\x04" + b"text"*n` 造的假样本（纯 ASCII，不是真 ZIP 结构）。
        """
        for name, data in (
            ("photo.png.bak", b"\x89PNG\r\n\x1a\n" + b"x" * 200),
            ("backup.tar", b"x" * 300),
        ):
            p = self._write(name, data)
            self.assertEqual(m.resolve_ctype(p)[0], m.TEXT_MIME_DEFAULT,
                             "前提变了：%s 现在不再被判为文本" % name)

    def test_real_office_files_are_binary(self):
        """真实 Office/ODF 文件必须判为二进制 —— 它们的 ZIP 头偏移 4-5 就有 NUL。

        这条是对上面那个错误结论的纠正：不要因为"本质是 ZIP"就以为嗅探认不出。
        """
        for name, inner in (("real.docx", {"word/document.xml": "<w:document/>"}),
                            ("real.xlsx", {"xl/worksheets/s1.xml": "<worksheet/>"}),
                            ("real.pptx", {"ppt/presentation.xml": "<p/>"}),
                            ("real.odt", {"content.xml": "<office/>"})):
            import io as _io, zipfile as _zip
            for comp in (_zip.ZIP_DEFLATED, _zip.ZIP_STORED):
                buf = _io.BytesIO()
                with _zip.ZipFile(buf, "w", comp) as z:
                    for k, v in inner.items():
                        z.writestr(k, v)
                p = self._write(name, buf.getvalue())
                self.assertTrue(m._is_binary(p),
                                "%s(%s) 应当判为二进制" % (name, comp))
                self.assertEqual(m.resolve_ctype(p)[0], m.BINARY_MIME)

    def test_ascii_utf16_recognized_as_text(self):
        """ASCII 为主的 UTF-16 无 BOM 文件要认成文本（VS Code 的对齐判定）。

        旧实现"有 NUL 即二进制"会把 `h\x00e\x00l\x00l\x00o` 判成二进制。
        """
        for enc in ("utf-16-le", "utf-16-be"):
            p = self._write("u16.txt", "hello world, ascii only\n".encode(enc))
            self.assertFalse(m._is_binary(p), "%s 应当认作文本" % enc)

    def test_cjk_utf16_is_a_known_boundary(self):
        """CJK 开头的 UTF-16 认不出来 —— 高位字节非 NUL，对齐立刻被破坏。

        VS Code 的实现同样如此（实测复刻过它的 oze()）。这条记录边界，
        不是 bug：真要认出来需要完整的编码嗅探。
        """
        p = self._write("cjk16.txt", "中文文本".encode("utf-16-le"))
        self.assertFalse(m._is_binary(p))          # 无 NUL -> 文本（碰巧对了）
        p2 = self._write("cjk16b.txt", "中".encode("utf-16-be") + b"\x00" * 4)
        self.assertTrue(m._is_binary(p2))          # 有了 NUL 但对不齐 -> 二进制

    def test_known_tradeoff_documented_in_module(self):
        """这个代价必须写在被测实现的 resolve_ctype docstring 里。

        对**被测文件本身**断言（而不是去读 mdview.py）—— 否则用
        MDVIEW_FILE 指向别的实现时，这条断言永远在检查另一个文件，形同虚设。
        压缩版刻意去掉所有 docstring，那条路径显式 skip，并说明原因。
        """
        doc = m.resolve_ctype.__doc__
        if not doc:
            self.skipTest("被测实现去掉了 docstring（压缩构建），"
                          "该契约由源码 mdview.py 的测试覆盖")
        self.assertIn("512", doc)
        self.assertIn("代价", doc)


class TestPathAndFileKind(unittest.TestCase):
    """路径夹紧（含符号链接）与常规文件判定（B5/B6/B8）。"""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_traversal_clamped(self):
        for bad in ("/../../etc/passwd", "/..%2f..%2fetc/passwd",
                    "/%2e%2e/%2e%2e/etc/passwd", "//etc/passwd", "/a/../../etc"):
            path, _rel = m._resolve(self.root, bad)
            if path is not None:
                self.assertTrue(m._inside(os.path.realpath(self.root),
                                          os.path.realpath(path)),
                                "%s 逃出了 root: %s" % (bad, path))

    def test_symlink_escape_rejected(self):
        """root 内指向外部的符号链接必须被拒（B6）。"""
        link = os.path.join(self.root, "escape")
        try:
            os.symlink("/etc/passwd", link)
        except (OSError, NotImplementedError):
            self.skipTest("此环境不支持创建符号链接")
        path, _rel = m._resolve(self.root, "/escape")
        self.assertIsNone(path, "符号链接逃逸未被挡住")

    def test_symlink_inside_root_allowed(self):
        target = os.path.join(self.root, "real.txt")
        open(target, "w").write("hi")
        link = os.path.join(self.root, "alias.txt")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("此环境不支持创建符号链接")
        path, _rel = m._resolve(self.root, "/alias.txt")
        self.assertIsNotNone(path, "root 内部的符号链接不该被拒")

    def test_is_regular_file(self):
        f = os.path.join(self.root, "f.txt")
        open(f, "w").write("x")
        self.assertTrue(m._is_regular_file(f))
        self.assertFalse(m._is_regular_file(self.root), "目录不是常规文件")
        self.assertFalse(m._is_regular_file(os.path.join(self.root, "nope")))
        fifo = os.path.join(self.root, "pipe")
        try:
            os.mkfifo(fifo)
        except (OSError, AttributeError, NotImplementedError):
            fifo = None
        if fifo:
            self.assertFalse(m._is_regular_file(fifo), "FIFO 不是常规文件")
            self.assertTrue(m._is_binary(fifo), "FIFO 应被当作二进制（避免 open 阻塞）")

    def test_inside_root_slash(self):
        """--root / 时不能因为 // 而全部 403（B8）。"""
        self.assertTrue(m._inside("/", "/etc/hosts"))
        self.assertTrue(m._inside("/", "/"))


class TestLinkSafety(unittest.TestCase):
    """链接安全：属性注入与危险协议（B1）。

    背景：`<a@b.com"onmouseover="x>` 曾被渲染成活的 onmouseover（Chrome 实测触发）。
    """

    @staticmethod
    def _attr_names(tag):
        """按 HTML 的引号规则解析属性名（值里的等号不算属性名）。

        不能用正则直接抓属性名：转义后的值里也含 `onmouseover=`，
        那样会把"已转义的安全文本"误报成属性注入。
        """
        inner = tag[tag.index(" ") + 1:-1] if " " in tag else ""
        names, i, n = [], 0, len(inner)
        while i < n:
            while i < n and inner[i].isspace():
                i += 1
            start = i
            while i < n and not inner[i].isspace() and inner[i] != "=":
                i += 1
            name = inner[start:i]
            while i < n and inner[i].isspace():
                i += 1
            if i < n and inner[i] == "=":
                i += 1
                while i < n and inner[i].isspace():
                    i += 1
                if i < n and inner[i] in "\"'":
                    quote = inner[i]
                    i += 1
                    while i < n and inner[i] != quote:
                        i += 1
                    i += 1
                else:
                    while i < n and not inner[i].isspace():
                        i += 1
            if name:
                names.append(name.lower())
        return names

    def test_no_unexpected_attributes_anywhere(self):
        """核心安全断言：渲染出的标签上不得出现白名单以外的属性名。

        这是 B1（存储型 XSS）的真正判据 —— 修复前 Chrome 实测
        onmouseover 是活的函数；修复后属性名集合严格收在白名单内。
        """
        allowed = {"href", "title", "rel", "src", "alt", "class", "id", "style"}
        payloads = [
            '<foo@bar.com"onmouseover="x>',
            '<a"href="javascript:1@b.co>',
            '<http://e.com/x"onmouseover="y>',
            '<x"onerror="1@a.com>',
            '[a](b.md "t\\" onmouseover=\\"x")',
            '![i](p.png "t\\" onerror=\\"x")',
            '[a](<b"onmouseover="c>)',
            '<img src=x onerror=alert(1)>',
            '[x](javascript:alert(1))',
            '![x](javascript:alert(1))',
            # 标签内容里的裸 HTML 曾经被反转义成真标记（SELFTEST §25）
            '[a<b>c](u.md)',
            '[<script>alert(1)</script>](u.md)',
            '[<img src=x onerror=alert(1)>](u.md)',
            # alt 曾经不转义引号：手写一个 " 就能凭空多出属性（SELFTEST §25）
            '![a" onerror="alert(1)](p.png)',
            '![a" onerror="alert(1)][r]\n\n[r]: p.png',
            '![a" onerror="alert(1)]\n\n[a" onerror="alert(1)]: p.png',
        ]
        for payload in payloads:
            out = m.render_markdown(payload + "\n")
            for tag in re.findall(r"<[a-z]+\b[^>]*>", out):
                extra = set(self._attr_names(tag)) - allowed
                self.assertFalse(extra, "%r 渲染出意外属性 %s: %s"
                                 % (payload, extra, tag))

    def test_autolink_attribute_injection_blocked(self):
        """注入的引号必须落在属性值**内部**（转义成 &quot;），不能闭合属性。

        元素文本里出现字面引号是无害的（文本节点不解析属性），所以要断言的是
        href 属性内部没有未转义的引号，而不是整段输出里没有引号。
        """
        import re as _re
        out = m.render_markdown('<foo@bar.com"onmouseover="document.title=1>\n')
        href = _re.search(r'href="([^"]*)"', out)
        self.assertIsNotNone(href, "应当仍是一个链接")
        # 属性值里出现的引号必须已被转义（否则就闭合了属性）
        self.assertNotIn('"', href.group(1), "href 属性值里出现了未转义引号")
        self.assertIn("&quot;", out)
        # 不能凭空多出属性：整个标签里只应有 href（+ 可选的 rel/title）
        tag = _re.search(r"<a\b[^>]*>", out).group(0)
        self.assertNotIn("onmouseover", tag.replace("&quot;onmouseover=&quot;", ""))

    def test_http_autolink_escapes_text(self):
        out = m.render_markdown('<http://e.com/x"y>\n')
        self.assertNotIn('"y"', out.replace("&quot;", ""))
        self.assertIn("&quot;", out)

    def test_alt_cannot_escape_its_attribute(self):
        """alt 是属性值：引号必须转义，否则能凭空注入属性（SELFTEST §25）。

        三条路都要覆盖：行内式、完整引用式、简写引用式。修复前它们都产出
        `<img src="…" alt="a" onerror="alert(1)">` —— Chrome 里 onerror 是活的。
        """
        payloads = [
            '![a" onerror="alert(1)](p.png)',
            '![a" onerror="alert(1)][r]\n\n[r]: p.png',
            '![a" onerror="alert(1)]\n\n[a" onerror="alert(1)]: p.png',
        ]
        for payload in payloads:
            out = m.render_markdown(payload + "\n")
            self.assertIn("<img", out, payload)
            img = re.search(r"<img\b[^>]*>", out).group(0)
            self.assertEqual(self._attr_names(img), ["src", "alt"], payload)
            alt = re.search(r'\balt="([^"]*)"', img).group(1)
            self.assertNotIn('"', alt, payload)
            self.assertIn("&quot;", alt, payload)

    def test_raw_html_in_label_stays_escaped(self):
        """链接标签是**内容**，里面的裸 HTML 必须保持转义（SELFTEST §25）。

        修复前 `[<script>alert(1)</script>](u.md)` 产出活的 script 标签、`a<b>c`
        产出活的 `<b>` —— 因为标签渲染把文本 token 又反转义了一遍。
        """
        for payload in ("[<script>alert(1)</script>](u.md)",
                        "[<img src=x onerror=alert(1)>](u.md)",
                        "[a<b>c](u.md)"):
            out = m.render_markdown(payload + "\n")
            self.assertNotIn("<script", out, payload)
            self.assertNotIn("<b>", out, payload)
            self.assertNotIn("<img src=x", out, payload)
            self.assertIn("&lt;", out, payload)
        # 行内语法在标签里照旧生效，只是裸 HTML 不再被放行
        out = m.render_markdown("[**粗**<script>x</script>](u.md)\n")
        self.assertIn("<strong>粗</strong>&lt;script&gt;x&lt;/script&gt;", out)

    def test_javascript_scheme_rejected(self):
        for payload in ('[x](javascript:alert(1))',
                        '[x](JavaScript:alert(1))',
                        '[x](JaVaScRiPt:alert(1))',
                        '[x](vbscript:msgbox(1))',
                        '[x](data:text/html,<script>alert(1)</script>)'):
            out = m.render_markdown(payload + "\n")
            self.assertNotIn("href=", out, "危险协议未被拒绝: %s" % payload)
            self.assertIn(">x</a>", out)
        # 前导空格让链接正则直接不匹配 —— 退化成纯文本，同样安全
        out = m.render_markdown("[x](  javascript:alert(1))\n")
        self.assertNotIn("href=", out)

    def test_javascript_scheme_in_reference_and_image(self):
        out = m.render_markdown('[x][r]\n\n[r]: javascript:alert(1)\n')
        self.assertNotIn("href=", out)
        out = m.render_markdown('![i](javascript:alert(1))\n')
        self.assertNotIn("<img", out)

    def test_safe_schemes_preserved(self):
        for url in ("https://e.com/a", "http://e.com/a", "mailto:a@b.com",
                    "ftp://e.com/f", "tel:+123", "#anchor", "/abs/path.md",
                    "rel/path.md"):
            out = m.render_markdown("[x](%s)\n" % url)
            self.assertIn('href="', out, "安全链接被误拒: %s" % url)

    def test_control_chars_stripped_from_url(self):
        """URL 里的制表/换行不能用来伪装协议。"""
        out = m.render_markdown("[x](java\u0000script:alert(1))\n")
        self.assertNotIn("javascript:", out.replace("\x00", ""))

    def test_url_entities_decoded(self):
        """URL 里的 &amp; 要还原成 &，不能被烘成字面量或漏出 token。"""
        for src in ("[a](x&amp;y.md)", "[a](x&y.md)"):
            out = m.render_markdown(src + "\n")
            self.assertNotIn("MK0", out, "token 占位符泄漏: %s" % out)
            self.assertNotIn("&amp;amp;", out)
            self.assertIn("%26", out)


class TestDownloadButton(unittest.TestCase):
    """目录索引里每个文件都有下载按钮；目录没有。"""

    def test_listing_has_button_for_files_only(self):
        out = m.render_dir_listing("docs/preview", "preview")
        self.assertIn('class="dl"', out)
        self.assertIn("?download=1", out)
        # 目录行不该有下载按钮
        import re as _re
        for row in _re.findall(r'<li class="d">.*?</li>', out):
            self.assertNotIn("download=1", row, "目录行不该有下载按钮")
        # 文件行必须有
        files = _re.findall(r'<li class="">.*?</li>', out)
        self.assertTrue(files, "应当有文件行")
        for row in files:
            self.assertIn("download=1", row, "文件行应当有下载按钮")

    def test_button_has_title_and_aria(self):
        out = m.render_dir_listing("docs/preview", "preview")
        self.assertIn('title="下载', out)
        self.assertIn('aria-label="下载', out)

    def test_force_download_keeps_accurate_type(self):
        """下载按钮不能把类型退化成 octet-stream。"""
        for name, want in (("a.md", "text/markdown"), ("a.png", "image/png"),
                           ("a.py", "text/plain"), ("a.pdf", "application/pdf")):
            ctype, download = m.resolve_ctype(name, force_download=True)
            self.assertTrue(download)
            self.assertTrue(ctype.startswith(want),
                            "%s 应为 %s，实际 %s" % (name, want, ctype))

    def test_force_download_off_by_default(self):
        self.assertFalse(m.resolve_ctype("a.md")[1])
        self.assertFalse(m.resolve_ctype("a.py")[1])

    def test_content_disposition_has_filename(self):
        """必须显式给文件名，否则浏览器自己推导会改名。

        实测：裸 attachment 时 Chrome 把 .gitignore 存成 gitignore.txt
        （点被当隐藏文件标记去掉，还按类型硬加了 .txt）。
        """
        cd = m._content_disposition(".gitignore")
        self.assertIn('filename=".gitignore"', cd)
        self.assertIn("filename*=UTF-8''", cd)

    def test_content_disposition_is_latin1_safe(self):
        """HTTP 头只能编 latin-1；中文写进 filename 会抛异常让响应挂掉。"""
        cd = m._content_disposition("测试 文件.md")
        cd.encode("latin-1")                      # 不抛异常才算合格
        self.assertNotIn("测试", cd)
        self.assertIn("filename*=UTF-8''", cd)     # 中文靠 filename* 还原
        self.assertIn("%E6%B5%8B%E8%AF%95", cd)

    def test_content_disposition_sanitizes_fallback(self):
        """回退名里不能留引号/分号/斜杠等会破坏头的字符。"""
        for name in ('a"b.txt', "a;b.txt", "a\\b.txt", "a\nb.txt"):
            cd = m._content_disposition(name)
            header_value = cd.split("filename*=UTF-8''")[0]
            self.assertEqual(header_value.count('"'), 2,
                             "%r 的回退名破坏了引号配对: %s" % (name, cd))
            cd.encode("latin-1")

    def test_content_disposition_never_empty(self):
        """空文件名也要给一个可用的回退名。"""
        cd = m._content_disposition("")
        self.assertIn('filename="download"', cd)


class TestPreviewLimitAndSniffing(unittest.TestCase):
    """大小上限 + 无扩展名嗅探（2026 设计：20 MiB + 前 512 字节 NUL 判定）。"""

    # ---- 大小参数解析 ----
    def test_parse_size_units(self):
        self.assertEqual(m._parse_size("20M"), 20 * 1024 * 1024)
        self.assertEqual(m._parse_size("512K"), 512 * 1024)
        self.assertEqual(m._parse_size("2G"), 2 * 1024 ** 3)
        self.assertEqual(m._parse_size("20m"), 20 * 1024 * 1024)   # 大小写不敏感
        self.assertEqual(m._parse_size("20971520"), 20971520)      # 纯字节
        self.assertEqual(m._parse_size("0"), 0)                    # 0 = 不限制
        self.assertEqual(m._parse_size("20MiB"), 20 * 1024 * 1024)
        self.assertEqual(m._parse_size("1.5M"), int(1.5 * 1024 * 1024))

    def test_parse_size_rejects_garbage(self):
        for bad in ("abc", "", "-5", "M", "12X"):
            with self.assertRaises(ValueError, msg="应拒绝 %r" % bad):
                m._parse_size(bad)

    def test_default_limit_constant(self):
        self.assertEqual(m.DEFAULT_MAX_PREVIEW, 20 * 1024 * 1024)
        self.assertEqual(m.BINARY_SNIFF_BYTES, 512)

    # ---- 嗅探 ----
    def test_is_binary_uses_first_bytes_only(self):
        d = tempfile.mkdtemp()
        try:
            cases = {
                "nul_at_start": (b"DIRC\x00\x00\x01", True),
                "nul_at_511":   (b"A" * 511 + b"\x00", True),
                "nul_at_512":   (b"A" * 512 + b"\x00", False),   # 只看前 512 字节
                "nul_far":      (b"A" * 5000 + b"\x00", False),
                "no_nul":       ("中文文本\n".encode(), False),
                "gbk_no_nul":   ("中文 GBK\n".encode("gbk"), False),
                "empty":        (b"", False),
            }
            for name, (data, want) in cases.items():
                path = os.path.join(d, name)
                with open(path, "wb") as fh:
                    fh.write(data)
                self.assertEqual(m._is_binary(path), want, name)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ---- 类型判定优先级 ----
    def test_resolve_ctype_extensionless_text_and_binary(self):
        d = tempfile.mkdtemp()
        try:
            txt = os.path.join(d, "plain")
            binf = os.path.join(d, "binfile")
            open(txt, "wb").write("中文\n".encode())
            open(binf, "wb").write(b"\x00\x01\x02")
            self.assertEqual(m.resolve_ctype(txt), (m.TEXT_MIME_DEFAULT, False))
            self.assertEqual(m.resolve_ctype(binf), (m.BINARY_MIME, False))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_resolve_ctype_oversized_keeps_type_and_downloads(self):
        """超大文件保留准确类型（C' 方案），并要求下载。"""
        ctype, download = m.resolve_ctype("x.md", force_download=True)
        self.assertTrue(download)
        self.assertEqual(ctype, "text/markdown; charset=utf-8")
        ctype, download = m.resolve_ctype("x.png", force_download=True)
        self.assertTrue(download)
        self.assertEqual(ctype, "image/png")

    def test_resolve_ctype_ordering(self):
        """.md 渲染、源码文本、MIME 表、未知扩展名下载。"""
        self.assertEqual(m.resolve_ctype("a.py"), (m.TEXT_MIME_DEFAULT, False))
        self.assertEqual(m.resolve_ctype("a.png"), ("image/png", False))
        self.assertEqual(m.resolve_ctype("a.zip"), (m.BINARY_MIME, False))
        self.assertEqual(m.resolve_ctype("a.unknownext"), (m.BINARY_MIME, False))
        self.assertFalse(m.resolve_ctype("a.py")[1])

    def test_sniff_only_applies_to_extensionless(self):
        """有扩展名的文件不读内容：一个 .py 里就算有 NUL 也按文本发。"""
        d = tempfile.mkdtemp()
        try:
            weird = os.path.join(d, "weird.py")
            open(weird, "wb").write(b"\x00\x00\x00")
            self.assertEqual(m.resolve_ctype(weird)[0], m.TEXT_MIME_DEFAULT)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestInlineDisplayableTypes(unittest.TestCase):
    """Content-Type 必须让浏览器内联显示，而不是下载。

    实测结论（Chrome）：决定内联还是下载的**只有 Content-Type** ——
    `Content-Disposition: inline` 对 text/csv 完全无效。
    只有 text/csv 与 text/tab-separated-values 会被强制下载，其余文本类都内联。
    """

    def test_csv_is_not_text_csv(self):
        """text/csv 在 Chrome 里必被下载，所以刻意声明为 text/plain。"""
        self.assertEqual(m.MIME[".csv"], "text/plain; charset=utf-8")
        self.assertNotEqual(m.MIME[".csv"].split(";")[0], "text/csv")

    def test_no_other_type_forces_download(self):
        """表里不能再出现会让浏览器下载的文本类型。"""
        banned = {"text/csv", "text/tab-separated-values"}
        for ext, ctype in m.MIME.items():
            self.assertNotIn(ctype.split(";")[0].strip(), banned,
                             "%s 声明了会被下载的类型 %s" % (ext, ctype))

    def test_inline_types_carry_charset(self):
        """内联显示的文本类都要带 charset，否则中文会乱码。"""
        for ext in (".csv", ".txt", ".json", ".xml", ".yaml", ".toml", ".js", ".css"):
            self.assertIn("charset=utf-8", m.MIME[ext], "%s 缺 charset" % ext)


class TestPreviewSamples(unittest.TestCase):
    """docs/preview 下的渲染样例必须真实可用。

    图片是纯标准库构造的，容易写出"看起来像图片、浏览器解不开"的假文件，
    所以这里校验魔数，并在端到端里校验可访问性。
    """

    ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "preview")

    def test_preview_dir_exists(self):
        self.assertTrue(os.path.isdir(self.ROOT), "docs/preview 应存在")
        self.assertTrue(os.path.isfile(os.path.join(self.ROOT, "index.md")))
        self.assertTrue(os.path.isfile(
            os.path.join(self.ROOT, "make_preview_samples.py")))

    def test_index_links_all_resolve(self):
        """索引页里的每个相对链接都必须在磁盘上存在。"""
        idx = os.path.join(self.ROOT, "index.md")
        with open(idx, encoding="utf-8") as fh:
            text = fh.read()
        links = [l for l in re.findall(r"\]\(([^)#][^)]*)\)", text)
                 if not l.startswith("http")]
        self.assertTrue(links, "索引页应当有链接")
        for link in links:
            target = os.path.normpath(os.path.join(self.ROOT, link))
            self.assertTrue(os.path.exists(target),
                            "链接指向的文件不存在: %s" % link)

    def test_image_files_have_real_magic(self):
        """图片样例必须是真图（魔数正确），不能是占位文本。"""
        magic = {
            "sample.png": b"\x89PNG\r\n\x1a\n",
            "sample.gif": b"GIF89a",
            "sample.bmp": b"BM",
            "sample.ico": b"\x00\x00\x01\x00",
            "sample.svg": b"<svg",
        }
        for name, head in magic.items():
            path = os.path.join(self.ROOT, "media", name)
            self.assertTrue(os.path.isfile(path), "%s 应存在" % name)
            with open(path, "rb") as fh:
                got = fh.read(len(head))
            self.assertEqual(got, head, "%s 的头部不是合法图片" % name)

    def test_gbk_sample_is_not_utf8(self):
        """故意放一个非 UTF-8 文件，用来验证编码声明。"""
        path = os.path.join(self.ROOT, "text", "gbk-encoded.txt")
        with open(path, "rb") as fh:
            raw = fh.read()
        self.assertIn("中文".encode("gbk"), raw)
        with self.assertRaises(UnicodeDecodeError):
            raw.decode("utf-8")

    def test_samples_cover_both_text_paths(self):
        """样例要覆盖两条文本路径：TEXT_EXT 与 MIME 表。"""
        # 路径一：源码/配置类扩展名表
        for ext in (".py", ".sh", ".go", ".rs", ".ts", ".sql", ".ini", ".log"):
            self.assertIn(ext, m.TEXT_EXT, "%s 应在 TEXT_EXT 里" % ext)
        # 路径二：MIME 表（csv/json/xml/yaml/toml 等由表给出更精确的类型）
        for ext in (".csv", ".json", ".xml", ".yaml", ".toml", ".txt"):
            self.assertIn(ext, m.MIME, "%s 应在 MIME 表里" % ext)
            self.assertIn("charset", m.MIME[ext], "%s 应带 charset" % ext)
        # 路径三：无扩展名 / 点文件按文件名判定
        for name in ("Makefile", "Dockerfile", ".gitignore", "README"):
            self.assertTrue(m._is_textual(os.path.join(self.ROOT, name)),
                            "%s 应判为文本" % name)


class TestSearchJumpCentering(unittest.TestCase):
    """搜索跳转的落点要竖向居中，而不是贴到视口最上沿。

    背景：搜索结果是 /x.md?raw=1#L51，浏览器默认把 #L51 顶到视口最上沿。
    实测过 scrollIntoView({block:"center"}) 会被原生锚点滚动盖掉（仍停在上方），
    所以改成自己算坐标 scrollTo。
    """

    def test_css_scroll_margin_fallback(self):
        """没有 JS 时也要不贴顶（上多下少的偏移）。"""
        page = m._page("t", "")
        self.assertIn("pre.rawsrc .srcline{scroll-margin-top:20vh;scroll-margin-bottom:70vh}",
                      page)

    def test_js_centers_with_explicit_scroll(self):
        page = m._page("t", "")
        self.assertIn("window.scrollTo", page)
        self.assertIn("window.innerHeight / 2", page)
        # 只对 L 开头的锚点生效，普通标题锚点不动
        self.assertIn('h.charAt(1) !== "L"', page)

    def test_js_clamps_and_avoids_repeat_scroll(self):
        page = m._page("t", "")
        self.assertIn("if (y < 0) y = 0;", page)          # 顶部不越界
        self.assertIn("if (y > max) y = max;", page)      # 底部不越界
        self.assertIn("replaceState", page)               # 已居中就不再滚
        self.assertIn('addEventListener("load"', page)    # 补一次，压过原生锚点滚动

    def test_raw_view_emits_line_anchors(self):
        """居中的前提：源码视图每行都有可定位的 id（读实现源码确认）。"""
        import inspect
        src = inspect.getsource(m.Handler._raw_page)
        self.assertIn('id="L%d"', src)
        self.assertIn("srcline", src)


class TestEcosystemWhitelist(unittest.TestCase):
    """前端 / Java / .NET 等生态的常见文本文件要能预览。

    这些文件大多没有扩展名（或扩展名很冷门），曾经一律走 octet-stream 下载。
    """

    NEW = [
        # 前端包管理与锁文件
        "yarn.lock", "bun.lock", "Pipfile.lock", "poetry.lock", "Cargo.lock",
        "Gemfile.lock", "mix.lock", "pubspec.lock", "Package.resolved",
        "pnpm-lock.yaml", "package.json", ".npmrc", ".nvmrc", ".yarnrc",
        ".browserslistrc", ".stylelintrc", ".lintstagedrc", ".swcrc",
        ".commitlintrc", ".markdownlintrc", ".pnpmfile.cjs",
        "rollup.config.mjs", "vite.config.ts", "webpack.config.js",
        # Java / Gradle / Maven
        "pom.xml", "build.gradle", "settings.gradle", "gradle.properties",
        "build.gradle.kts", "settings.gradle.kts", "gradlew", "mvnw",
        "MANIFEST.MF", "Manifest.mf", "jvm.config", "maven.config",
        # Go / Rust / autotools / Xcode / Swift
        "go.mod", "go.sum", "Makefile.am", "Makefile.in", "configure.ac",
        "project.pbxproj", "Podfile", "Podfile.lock", "Package.swift",
        # .NET / NuGet
        "App.csproj", "proj.sln", "Directory.Build.props", "app.targets",
        "res.resx", "pkg.nuspec", "packages.config", "NuGet.Config",
        "Directory.Packages.props", "App.csproj.user",
        # 其他
        ".terraform.lock.hcl", "CMakeLists.txt", ".editorconfig",
    ]

    def test_all_preview_as_text(self):
        d = tempfile.mkdtemp()
        try:
            for name in self.NEW:
                path = os.path.join(d, name.replace("/", "_"))
                with open(path, "wb") as fh:
                    fh.write(b"text content\n")
                ctype, download = m.resolve_ctype(path)
                self.assertFalse(download, "%s 不该被要求下载" % name)
                self.assertNotEqual(ctype, m.BINARY_MIME,
                                    "%s 仍被判为二进制（会下载）" % name)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_bun_lockb_stays_binary(self):
        """bun.lockb 是二进制锁文件，**不能**因为收了 .lock 就被带成文本。"""
        self.assertNotIn(".lockb", m.TEXT_EXT)
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "bun.lockb")
            with open(path, "wb") as fh:
                fh.write(b"bun-lockb\x01" + b"\x00" * 40)
            ctype, _ = m.resolve_ctype(path)
            self.assertEqual(ctype, m.BINARY_MIME)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_real_binaries_still_binary(self):
        """扩容不能把真二进制放进来。"""
        for ext in (".zip", ".png", ".pdf", ".mp4", ".docx", ".so", ".dylib",
                    ".exe", ".lockb", ".wasm", ".woff2"):
            d = tempfile.mkdtemp()
            try:
                path = os.path.join(d, "x" + ext)
                with open(path, "wb") as fh:
                    fh.write(b"\x00\x01\x02")
                ctype, _ = m.resolve_ctype(path)
                self.assertNotEqual(ctype, m.TEXT_MIME_DEFAULT,
                                    "%s 不该被当成文本" % ext)
            finally:
                shutil.rmtree(d, ignore_errors=True)


class TestTextExtensions(unittest.TestCase):
    """源码/配置类文件必须按 UTF-8 文本发送，否则中文乱码或直接下载。

    回归背景：`.py` 曾被发成不带 charset 的 `text/x-python`，浏览器猜编码 ->
    中文注释变乱码。同批还有 `.ts`（stdlib 认成 video/mp2t）、以及 `.go`/`.rs`/
    `.ini`/`.log` 等未收录扩展名（回落 octet-stream -> 点开即下载）。
    """

    def test_source_extensions_are_textual(self):
        for ext in ("py", "pyw", "sh", "bash", "zsh", "c", "h", "cc", "cpp", "hpp",
                    "cs", "java", "go", "rs", "ts", "tsx", "jsx", "rb", "php", "pl",
                    "lua", "sql", "ini", "cfg", "conf", "properties", "log", "diff",
                    "patch", "env", "mk", "bat", "ps1", "vue", "svelte", "tsv",
                    "rst", "tex"):
            self.assertTrue(m._is_textual("x." + ext), ".%s 应判为文本" % ext)

    def test_typescript_is_not_video(self):
        """stdlib 把 .ts 认成 video/mp2t；这里必须当文本，否则 TypeScript 变视频。"""
        import mimetypes
        self.assertEqual(mimetypes.guess_type("x.ts")[0], "video/mp2t")
        self.assertTrue(m._is_textual("x.ts"))
        # 命中文本表 -> 实际发送的类型必须带 charset
        self.assertIn("charset", m.MIME.get(".ts", m.TEXT_MIME_DEFAULT))

    def test_extensionless_text_filenames(self):
        for name in ("Makefile", "Dockerfile", ".gitignore", "LICENSE", "README",
                     "docker-compose.yml", "Jenkinsfile"):
            self.assertTrue(m._is_textual("/tmp/" + name), "%s 应判为文本" % name)

    def test_binary_stays_binary(self):
        for name in ("a.zip", "a.png", "a.jpg", "a.pdf", "a.docx", "a.mp4",
                     "a.gz", "a.unknownext", "a.bin"):
            self.assertFalse(m._is_textual("/tmp/" + name), "%s 不应判为文本" % name)

    def test_binary_mime_table_untouched(self):
        """图片/PDF 的类型不能被文本判定影响。"""
        for ext, want in ((".png", "image/png"), (".svg", "image/svg+xml"),
                          (".pdf", "application/pdf"), (".jpg", "image/jpeg")):
            self.assertEqual(m.MIME.get(ext), want)
            self.assertFalse(m._is_textual("x" + ext))


class TestRoutingHelpers(unittest.TestCase):
    def test_resolve_stays_in_root(self):
        root = os.path.abspath(os.sep + "tmp")
        ok, rel = m._resolve(root, "/a/b.md")
        self.assertTrue(ok.startswith(root))
        # ../ 一律夹紧在 root 内，绝不可能越界
        clamped, _ = m._resolve(root, "/../../etc/passwd")
        self.assertTrue(clamped.startswith(root))
        self.assertNotEqual(os.path.normpath(clamped), os.path.normpath("/etc/passwd"))

    def test_resolve_percent_decode(self):
        root = os.path.abspath(os.sep + "tmp")
        p, rel = m._resolve(root, "/%E4%B8%AD%E6%96%87/a.md")
        self.assertEqual(rel, "中文/a.md")

    def test_slugify(self):
        self.assertEqual(m.slugify("Hello World"), "hello-world")
        self.assertEqual(m.slugify("中文 标题!"), "中文-标题")
        self.assertEqual(m.slugify("<em>x</em> y"), "x-y")

    def test_quote_seg_path(self):
        self.assertEqual(m.quote_seg_path("/a b/c.md"), "/a%20b/c.md")
        self.assertEqual(m.quote_seg_path("https://e.com/a b"), "https://e.com/a b")

    def test_highlight_unknown_lang(self):
        out = m.highlight("x = 1", "brainfuck")
        self.assertIn("<span", out)
        out = m.highlight("plain text", "")
        self.assertIn("plain text", out)

    def test_plain_fences_are_not_highlighted(self):
        """不写语言、或声明 text/plaintext/txt 的围栏都必须素色。

        注意：语言标签本身是 <span class="meta">，所以这里检测的是
        **token 类**（kw/str/com/num/fn/op），不是任意 span。
        """
        token = re.compile(r'<span class="(?:kw|str|com|num|fn|op)">')
        for opener in ("```", "```text", "```plaintext", "```txt"):
            out = r(opener + "\nplain 123 # hash\n```")
            self.assertIsNone(token.search(out), "%r 不该产生 token 着色" % opener)
            self.assertIn("plain 123 # hash", out)
        # 声明了语言（哪怕未知）仍然走通用规则
        self.assertIsNotNone(token.search(r("```brainfuck\nx = 1\n```")))

    def test_mark_highlight(self):
        self.assertIn("<mark>ab</mark>", m._mark("xabcy", "ab"))
        self.assertIn("<mark>AB</mark>", m._mark("xABy", "ab"))


class TestSearch(unittest.TestCase):
    def test_search_finds_body_and_name(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sub"))
            with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as f:
                f.write("# 标题\n\n这里有 关键词 出现\n")
            with open(os.path.join(d, "关键词.md"), "w", encoding="utf-8") as f:
                f.write("# 另一个\n")
            with open(os.path.join(d, "b.txt"), "w", encoding="utf-8") as f:
                f.write("关键词\n")
            body_hits, name_hits, scanned, truncated = m.search_markdown(d, "关键词")
            rels = {x[0] for x in body_hits} | set(name_hits)
            self.assertIn("a.md", rels)              # 正文命中
            self.assertIn("关键词.md", rels)          # 仅文件名命中也要出现
            self.assertNotIn("b.txt", rels)          # 只扫 .md
            self.assertEqual(scanned, 2)
            self.assertFalse(truncated)

    def test_search_filename_only_hit(self):
        """名字里含关键词、正文完全不含的文件也必须列出（回归：曾整个消失）。"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "sub"))
            with open(os.path.join(d, "sub", "zzz-unicorn-guide.md"), "w",
                      encoding="utf-8") as f:
                f.write("# 完全无关的标题\n\n正文里没有任何关键词。\n")
            with open(os.path.join(d, "other.md"), "w", encoding="utf-8") as f:
                f.write("# 另一个\n\n这里也没提到那个词。\n")
            body_hits, name_hits, scanned, _trunc = m.search_markdown(d, "unicorn")
            self.assertEqual(body_hits, [], "正文不该命中")
            self.assertEqual(name_hits, ["sub/zzz-unicorn-guide.md"],
                             "仅文件名命中的文件必须出现")
            self.assertEqual(scanned, 2)

    def test_search_case_insensitive(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.md"), "w", encoding="utf-8") as f:
                f.write("Hello World\n")
            body_hits, _name, _scanned, _trunc = m.search_markdown(d, "hello")
            self.assertEqual(len(body_hits), 1)

    def test_search_skips_hidden_dirs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, ".git"))
            with open(os.path.join(d, ".git", "x.md"), "w", encoding="utf-8") as f:
                f.write("needle\n")
            body_hits, name_hits, scanned, _trunc = m.search_markdown(d, "needle")
            self.assertEqual(body_hits, [])
            self.assertEqual(name_hits, [])
            self.assertEqual(scanned, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
