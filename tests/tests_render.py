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
