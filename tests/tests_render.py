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

# mdview.py 在仓库根（本文件位于 tests/），把它加入 sys.path
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
        self.assertIn('<a href="https://example.com" title="标题">文字</a>', out)
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
