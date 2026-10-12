#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mdview.py — 零依赖离线 Markdown 预览服务器（只用 Python 标准库）。

用法:
    python3 mdview.py                       # 默认 0.0.0.0:8000，根=当前目录
    python3 mdview.py --port 9000 --root ~/notes
    python3 mdview.py --depth 3             # 首页展开 3 层目录树
    python3 mdview.py --safe                # 只服务 .md + 图片，其余 404
    python3 mdview.py --no-search           # 关闭全文搜索

设计约束（来自需求评审）:
    * 严格零第三方依赖：只用 stdlib（http.server / socketserver / re / html / urllib.parse / argparse）。
    * 服务端渲染：Markdown -> HTML 在 Python 侧完成，页面无需任何 JS 即可阅读。
    * 默认 0.0.0.0 + 任意文件可读：等同于一个好看一点的静态文件服务器；启动 banner 会
      显式打印真实暴露范围。需要收紧时用 --safe。
    * 路径穿越防护：解决后的路径必须仍在 root 内，否则 403。
    * 虚拟主机名不参与路由；所有 .md 一律渲染，?raw=1 返回纯文本。

SECTION 导航（本文件按功能分块，行号会随修改漂移，用关键字搜索定位）:
    [1] 常量与配置          SECTION 1  CONSTANTS
    [2] 内联 CSS            SECTION 2  CSS
    [3] HTML 模板           SECTION 3  TEMPLATES
    [4] 语法高亮器          SECTION 4  HIGHLIGHTER
    [5] 内联解析            SECTION 5  INLINE
    [6] 链接/图片重写       SECTION 6  URL REWRITE
    [7] 块级解析            SECTION 7  BLOCKS
    [8] 目录索引 / 搜索页   SECTION 8  DIRECTORY & SEARCH
    [9] HTTP 处理器         SECTION 9  HANDLER
    [10] CLI 与启动         SECTION 10 CLI

已知行为（写在代码里而不是靠口头约定）:
    * 裸 HTML 全部转义，不透传 —— 100% 消除 .md 作为 XSS 载体。
    * 列表/引用可嵌套；未标语言的围栏代码块按通用规则高亮。
    * 单层目录不限制条目数（--max-list 可调），大目录可能较慢。
    * 单文件渲染不限制大小；非 UTF-8 用 errors="replace" 解码。
    * 隐藏目录（.git / .svn / node_modules 等）不进索引与搜索，但仍可直接按 URL 访问。
"""

import argparse
import html
import os
import posixpath
import re
import socket
import sys
import threading
import time
import unicodedata
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

__version__ = "1.0.0"

# ============================================================================
# SECTION 1  CONSTANTS
# ============================================================================

MD_EXT = ".md"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".avif"}
# 简写式引用链接 [ref]：必须放在完整式/折叠式替换之后，且排除紧跟 ( [ 的情况
_REF_SHORT_RE = re.compile(r"\[([^\[\]]+)\](?![\(\[(])")
SAFE_EXT = {MD_EXT} | IMAGE_EXT
SKIP_DIRS = {".git", ".svn", ".hg", ".idea", ".vscode", "node_modules", "__pycache__",
             ".venv", "venv", ".tox", "dist", "build"}
MD_SEARCH_CAP = 400          # 单次搜索最多返回多少条命中行
SEARCH_CONTEXT = 2           # 每条命中上下各带几行

MIME = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".py": "text/plain; charset=utf-8",
    ".yaml": "text/plain; charset=utf-8",
    ".yml": "text/plain; charset=utf-8",
    ".toml": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".avif": "image/avif",
    ".pdf": "application/pdf",
}


# ============================================================================
# SECTION 2  CSS
# ============================================================================

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --soft:#f6f8fa;
  --accent:#0969da; --mark:#fff3bf; --markfg:#1f2328;
  --t-kw:#cf222e; --t-str:#0a3069; --t-com:#6e7781; --t-num:#0550ae;
  --t-fn:#8250df; --t-op:#cf222e;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --soft:#151b23;
    --accent:#4493f8; --mark:#5c4b00; --markfg:#f0f6fc;
    --t-kw:#ff7b72; --t-str:#a5d6ff; --t-com:#8b949e; --t-num:#79c0ff;
    --t-fn:#d2a8ff; --t-op:#ff7b72;
  }
}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC",
  "PingFang SC","Microsoft YaHei",Helvetica,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:28px 20px 72px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
header.bar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:22px}
header.bar .brand{font-weight:600;font-size:15px;color:var(--muted)}
header.bar .spacer{flex:1 1 auto}
header.bar form input[type=search]{background:var(--soft);color:var(--fg);
  border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:14px;min-width:200px}
header.bar form button,header.bar a.btn{background:var(--soft);color:var(--fg);
  border:1px solid var(--line);border-radius:6px;padding:6px 11px;font-size:14px;cursor:pointer;
  text-decoration:none;display:inline-block}
header.bar form button:hover,header.bar a.btn:hover{background:var(--line);text-decoration:none}
.crumbs{font-size:14px;color:var(--muted);margin:0 0 18px}
.crumbs a{color:var(--muted)}
h1,h2,h3,h4,h5,h6{line-height:1.3;margin:26px 0 12px;font-weight:600}
h1{font-size:1.85em;border-bottom:1px solid var(--line);padding-bottom:.25em}
h2{font-size:1.45em;border-bottom:1px solid var(--line);padding-bottom:.22em}
h3{font-size:1.22em} h4{font-size:1.05em} h5,h6{font-size:.95em;color:var(--muted)}
p{margin:0 0 14px}
ul,ol{margin:0 0 14px;padding-left:1.9em}
li{margin:.2em 0}
li>ul,li>ol{margin:.25em 0 .3em}
li.task{list-style:none;margin-left:-1.4em}
li.task input{margin-right:.5em;vertical-align:middle}
blockquote{margin:0 0 14px;padding:.2em 0 .2em 1em;border-left:4px solid var(--line);color:var(--muted)}
blockquote>:last-child{margin-bottom:0}
code{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,
  "Liberation Mono",monospace;font-size:.88em;background:var(--soft);
  border-radius:5px;padding:.16em .38em}
pre{background:var(--soft);border:1px solid var(--line);border-radius:8px;
  padding:13px 15px;overflow-x:auto;margin:0 0 16px;line-height:1.5}
.codeblock pre{line-height:1.5}
pre code{background:none;border:none;padding:0;font-size:.86em;white-space:pre}
table{border-collapse:collapse;margin:0 0 16px;display:block;max-width:100%;overflow-x:auto;width:max-content}
th,td{border:1px solid var(--line);padding:7px 13px;text-align:left}
th{background:var(--soft);font-weight:600}
tr:nth-child(2n) td{background:var(--soft)}
img{max-width:100%;height:auto}
hr{border:0;border-top:1px solid var(--line);margin:26px 0}
mark{background:var(--mark);color:var(--markfg);border-radius:3px;padding:0 2px}
.codeblock{border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:0 0 16px}
.codeblock .codehdr{background:var(--soft);border-bottom:1px solid var(--line);
  padding:5px 13px;font-size:12px;color:var(--muted);
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.codeblock .codehdr:empty{display:none}
.codeblock pre{margin:0;border:0;border-radius:0;background:var(--soft)}
.codeblock pre code{background:none;border:0;padding:0;font-size:.86em}
.kw{color:var(--t-kw)} .str{color:var(--t-str)} .com{color:var(--t-com);font-style:italic}
.num{color:var(--t-num)} .fn{color:var(--t-fn)} .op{color:var(--t-op)}
.dirlist{list-style:none;padding:0;margin:0}
.dirlist li{border-bottom:1px solid var(--line);padding:7px 2px;display:flex;
  align-items:baseline;gap:10px}
.dirlist li .nm{flex:1 1 auto;min-width:0;overflow-wrap:anywhere}
.dirlist li .meta{color:var(--muted);font-size:13px;white-space:nowrap}
.dirlist li.d a{font-weight:600}
.note{background:var(--soft);border:1px solid var(--line);border-radius:8px;
  padding:12px 15px;color:var(--muted);font-size:14px;margin:0 0 18px}
.hit{background:var(--soft);border:1px solid var(--line);border-radius:8px;
  padding:12px 15px;margin:0 0 14px}
.hit .where{font-size:13px;color:var(--muted);margin-bottom:8px}
.hit pre{margin:0;background:transparent;border:none;padding:0;font-size:13px;
  white-space:pre-wrap;overflow-wrap:anywhere}
.hit .ln{color:var(--muted);user-select:none;display:inline-block;min-width:3.4em;text-align:right;margin-right:.9em}
.tree ul{list-style:none;padding-left:1.2em;margin:.15em 0}
.tree>ul{padding-left:0}
.tree li{padding:2px 0}
.esc{border-bottom:1px dashed var(--line);padding-bottom:1px}
.bad{color:var(--t-kw)}
@media print{
  header.bar,.crumbs,.note{display:none}
  body{background:#fff;color:#000}
  .wrap{max-width:none;padding:0}
  pre,table,blockquote,code{border-color:#999;background:#f7f7f7}
}
"""


# ============================================================================
# SECTION 3  TEMPLATES
# ============================================================================

def _page(title, body, nav_right="", show_search=True, search_q="", depth_nav=""):
    """包一层完整 HTML 页面。样式内联，页面零额外请求。"""
    search = ""
    if show_search:
        search = ('<form action="/search" method="get" role="search">'
                  '<input type="search" name="q" placeholder="搜索 Markdown…" '
                  'value="%s" aria-label="搜索"></form>' % html.escape(search_q, quote=True))
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"color-scheme\" content=\"light dark\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<div class=\"wrap\">\n"
        "<header class=\"bar\"><a class=\"brand\" href=\"/\">mdview</a>"
        "%s<div class=\"spacer\"></div>%s%s</header>\n"
        "%s\n</div>\n</body>\n</html>\n"
    ) % (html.escape(title), CSS, depth_nav, search, nav_right, body)


def _crumbs(rel_path):
    """面包屑：根 / a / b.md —— 只对目录部分生成链接。"""
    parts = [p for p in rel_path.split("/") if p]
    out = ['<a href="/">根</a>']
    upto = []
    for i, p in enumerate(parts):
        upto.append(p)
        if i == len(parts) - 1:
            out.append(html.escape(p))
        else:
            href = "/" + "/".join(quote_seg(x) for x in upto) + "/"
            out.append('<a href="%s">%s</a>' % (href, html.escape(p)))
    return '<p class="crumbs">%s</p>' % " / ".join(out)


def _error_page(status, message, detail=""):
    body = ('<h1>%s</h1>\n<p>%s</p>\n' % (status, html.escape(message)))
    if detail:
        body += '<pre><code>%s</code></pre>\n' % html.escape(detail)
    body += '<p><a href="/">返回目录索引</a></p>\n'
    return _page("%s %s" % (status, message), body)


def _fmt_size(n):
    if n < 1024:
        return "%d B" % n
    for unit in ("KB", "MB", "GB"):
        n /= 1024.0
        if n < 1024:
            return "%.1f %s" % (n, unit)
    return "%.1f TB" % n


# ============================================================================
# SECTION 4  HIGHLIGHTER
# ============================================================================
# 只对带语言标识的围栏代码块做 token 着色（以及识别不到语言时用通用规则）。
# 未知语言 -> 通用规则；完全不给语言 -> 通用规则。内联 code 一律素色。

COMMON_KEYWORDS = {
    # C 家族 / 通用
    "if", "else", "elif", "for", "while", "do", "switch", "case", "default", "break",
    "continue", "return", "goto", "sizeof", "struct", "union", "enum", "typedef",
    "static", "const", "volatile", "extern", "inline", "register", "unsigned", "signed",
    "void", "char", "short", "int", "long", "float", "double", "class", "public",
    "private", "protected", "virtual", "override", "final", "new", "delete", "this",
    "super", "extends", "implements", "interface", "package", "import", "export",
    "from", "namespace", "using", "template", "typename", "try", "catch", "finally",
    "throw", "throws", "instanceof", "typeof", "in", "of", "with", "as", "is",
    "function", "var", "let", "async", "await", "yield", "lambda", "match", "when",
    # 真值/空值
    "true", "false", "null", "nil", "None", "True", "False", "undefined", "NaN",
    # Python
    "def", "pass", "raise", "except", "global", "nonlocal", "assert", "del", "and",
    "or", "not", "print",
    # Go / Rust / Java 常见
    "func", "defer", "chan", "select", "go", "range", "map", "impl", "trait", "mut",
    "pub", "crate", "mod", "fn", "where", "unsafe", "dyn", "ref", "loop", "move",
    "String", "Vec", "Option", "Result", "Some", "Ok", "Err", "println", "printf",
    # Shell
    "echo", "cd", "ls", "export", "local", "source", "then", "fi", "esac", "done",
    "until", "sudo", "set", "unset", "readonly", "alias",
    # SQL
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "GROUP", "ORDER", "BY", "HAVING",
    "LIMIT", "OFFSET", "CREATE", "TABLE", "INDEX", "DROP", "ALTER", "AND", "OR",
    "NOT", "NULL", "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "DISTINCT", "AS",
}

LANG_KEYWORDS = {
    "python": set("""and as assert async await break class continue def del elif else except
        finally for from global if import in is lambda nonlocal not or pass raise return
        try while with yield None True False self match case""".split()),
    "py": None,  # 占位，下面统一填充
    "javascript": set("""async await break case catch class const continue debugger default
        delete do else export extends finally for function if import in instanceof let new
        of return static super switch this throw try typeof var void while with yield
        null true false undefined NaN""".split()),
    "typescript": set("""abstract any as async await boolean break case catch class const
        constructor continue declare default delete do else enum export extends finally for
        from function if implements import in instanceof interface keyof let namespace never
        new null number object of private protected public readonly return static string
        super switch symbol this throw try type typeof undefined union unknown var void while
        yield true false""".split()),
    "go": set("""break case chan const continue default defer else fallthrough for func go
        goto if import interface map package range return select struct switch type var
        nil true false make len cap append new panic recover string int int64 float64
        bool byte rune error""".split()),
    "rust": set("""as async await break const continue crate dyn else enum extern fn for if
        impl in let loop match mod move mut pub ref return self Self static struct super
        trait type unsafe use where while true false Some None Ok Err String Vec Option
        Result i32 i64 u32 u64 usize f32 f64 str bool""".split()),
    "java": set("""abstract assert break case catch class const continue default do else enum
        extends final finally for goto if implements import instanceof interface native new
        package private protected public return static strictfp super switch synchronized
        this throw throws transient try void volatile while var record sealed yield
        true false null String Integer Long Double Boolean List Map Set""".split()),
    "c": set("""auto break case char const continue default do double else enum extern float
        for goto if inline int long register restrict return short signed sizeof static
        struct switch typedef union unsigned void volatile while NULL true false size_t""".split()),
    "cpp": set("""alignas alignof auto bool break case catch char class const constexpr
        continue decltype default delete do double else enum explicit export extern false
        float for friend goto if inline int long mutable namespace new noexcept nullptr
        operator private protected public register return short signed sizeof static
        static_cast struct switch template this throw true try typedef typename union
        unsigned using virtual void volatile while std string vector""".split()),
    "shell": set("""if then else elif fi for while until do done case esac function return
        in local export readonly declare typeset unset shift trap set source alias echo
        printf cd pwd ls cp mv rm mkdir rmdir cat grep sed awk find xargs sort uniq head
        tail cut tr wc chmod chown sudo kill ps top df du tar curl wget git docker
        true false""".split()),
    "sql": set(k for k in COMMON_KEYWORDS if k.isupper() or k in
               ("select", "from", "where", "insert", "update", "delete", "join")),
    "json": set("true false null".split()),
    "yaml": set("true false null yes no on off".split()),
}
LANG_KEYWORDS["py"] = LANG_KEYWORDS["python"]
LANG_KEYWORDS["js"] = LANG_KEYWORDS["javascript"]
LANG_KEYWORDS["ts"] = LANG_KEYWORDS["typescript"]
LANG_KEYWORDS["golang"] = LANG_KEYWORDS["go"]
LANG_KEYWORDS["rs"] = LANG_KEYWORDS["rust"]
LANG_KEYWORDS["bash"] = LANG_KEYWORDS["shell"]
LANG_KEYWORDS["sh"] = LANG_KEYWORDS["shell"]
LANG_KEYWORDS["zsh"] = LANG_KEYWORDS["shell"]
LANG_KEYWORDS["console"] = LANG_KEYWORDS["shell"]
LANG_KEYWORDS["c++"] = LANG_KEYWORDS["cpp"]
LANG_KEYWORDS["h"] = LANG_KEYWORDS["c"]
LANG_KEYWORDS["yml"] = LANG_KEYWORDS["yaml"]
LANG_KEYWORDS["mysql"] = LANG_KEYWORDS["sql"]
LANG_KEYWORDS["postgres"] = LANG_KEYWORDS["sql"]
LANG_KEYWORDS["postgresql"] = LANG_KEYWORDS["sql"]
LANG_KEYWORDS["sqlite"] = LANG_KEYWORDS["sql"]
LANG_KEYWORDS["dockerfile"] = set("""
    FROM RUN CMD LABEL MAINTAINER EXPOSE ENV ADD COPY ENTRYPOINT VOLUME USER WORKDIR
    ARG ONBUILD STOPSIGNAL HEALTHCHECK SHELL AS NONE CMD-SHELL
    from run cmd label maintainer expose env add copy entrypoint volume user workdir
    arg onbuild stopsignal shell as none scratch true false
""".split())
LANG_KEYWORDS["docker"] = LANG_KEYWORDS["dockerfile"]
LANG_KEYWORDS["containerfile"] = LANG_KEYWORDS["dockerfile"]
LANG_KEYWORDS["docker-compose"] = set("""
    version services networks volumes configs secrets
    image build context dockerfile args target cache_from labels
    container_name command entrypoint environment env_file ports expose
    volumes depends_on links networks restart deploy healthcheck
    logging ulimits user working_dir stdin_open tty privileged
    read_only cap_add cap_drop devices dns extra_hosts hostname
    init ipc pid platform profiles pull_policy shm_size stop_grace_period
    stop_signal sysctls tmpfs
""".split())
LANG_KEYWORDS["compose"] = LANG_KEYWORDS["docker-compose"]
LANG_KEYWORDS["yml-docker"] = LANG_KEYWORDS["docker-compose"]
LANG_KEYWORDS["toml"] = set("""
    true false
""".split())
LANG_KEYWORDS["makefile"] = set("""
    ifeq ifneq ifdef ifndef else endif include define endef export unexport
    override vpath SHELL MAKEFLAGS .PHONY .DEFAULT .SUFFIXES
""".split())
LANG_KEYWORDS["ini"] = set("""
    true false yes no on off none
""".split())
LANG_KEYWORDS["mk"] = LANG_KEYWORDS["makefile"]
LANG_KEYWORDS["cfg"] = LANG_KEYWORDS["ini"]
LANG_KEYWORDS["conf"] = LANG_KEYWORDS["ini"]
LANG_KEYWORDS["properties"] = LANG_KEYWORDS["ini"]
LANG_KEYWORDS["plaintext"] = set()
LANG_KEYWORDS["text"] = set()
LANG_KEYWORDS[""] = set()

# 这些语言的关键字匹配忽略大小写（Dockerfile 里 run/RUN 都合法）
LANG_ICASE = {"dockerfile", "docker", "containerfile", "docker-compose", "compose",
              "makefile", "mk", "ini", "cfg", "conf", "properties", "markdown", "md"}

LANG_LABEL = {
    "python": "Python", "py": "Python", "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript", "go": "Go", "golang": "Go",
    "rust": "Rust", "rs": "Rust", "java": "Java", "c": "C", "cpp": "C++", "c++": "C++",
    "shell": "Shell", "bash": "Shell", "sh": "Shell", "zsh": "Shell", "sql": "SQL",
    "json": "JSON", "yaml": "YAML", "yml": "YAML", "toml": "TOML", "html": "HTML",
    "css": "CSS", "xml": "XML", "markdown": "Markdown", "md": "Markdown",
    "dockerfile": "Dockerfile", "docker": "Dockerfile",
    "containerfile": "Containerfile", "docker-compose": "Docker Compose",
    "compose": "Docker Compose", "toml": "TOML", "makefile": "Makefile",
    "mk": "Makefile", "ini": "INI", "cfg": "INI", "conf": "INI", "properties": "Properties",
}


def _token_re(keywords, icase=False):
    kw = ""
    if keywords:
        ordered = sorted(keywords, key=len, reverse=True)
        kw = r"|(?P<kw>\b(?:%s)\b)" % "|".join(re.escape(k) for k in ordered)
    return re.compile(
        r"(?P<com>/\*.*?\*/|<!--.*?-->|(?<![:\w])//[^\n]*|#[^\n]*)"
        r"|(?P<str>\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)"
        r"|(?P<num>(?<![\w.\-])(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(?![\w.\-]))"
        + kw +
        r"|(?P<fn>\b[A-Za-z_]\w*(?=\s*\())"
        r"|(?P<id>\b[A-Za-z_]\w*\b)",
        re.DOTALL | (re.IGNORECASE if icase else 0),
    )


_HL_RE_CACHE = {}


def _lang_of(info):
    """从围栏 info string 里取出语言名，例如 'python title="x"' -> 'python'。"""
    if not info:
        return ""
    return info.strip().split()[0].strip().lower().lstrip("{.").rstrip("}")


def highlight(code, info=""):
    """把代码文本转成带 <span class> 的 HTML。未知语言退化为通用关键字规则。

    进入正则前先把 < > 换成私有区占位符：高亮器逐 token 做 html.escape，
    但行内阶段的 _TAG_RE 会把代码里形如 <div> 的片段当成「受保护的裸 HTML」
    原样放行 —— 那会让代码块里的 <script> 真的执行。这里彻底堵死。
    """
    if "<" in code or ">" in code:
        code = code.replace("<", _LT_SHIELD).replace(">", _GT_SHIELD)
    lang = _lang_of(info)
    if lang in LANG_KEYWORDS:
        keywords = LANG_KEYWORDS[lang]
    else:
        keywords = COMMON_KEYWORDS
    rx = _HL_RE_CACHE.get(lang)
    if rx is None:
        rx = _token_re(keywords, icase=lang in LANG_ICASE)
        _HL_RE_CACHE[lang] = rx
    cls = {"com": "com", "str": "str", "num": "num", "kw": "kw", "fn": "fn", "id": None}

    def sub(m):
        kind = m.lastgroup
        c = cls.get(kind)
        text = html.escape(m.group(0), quote=False)
        return '<span class="%s">%s</span>' % (c, text) if c else text

    out = rx.sub(sub, code)
    return out.replace(_LT_SHIELD, "&lt;").replace(_GT_SHIELD, "&gt;")


# ============================================================================
# SECTION 5  INLINE
# ============================================================================

ALIASES = {
    "nbsp": "\u00a0", "copy": "©", "reg": "®", "trade": "™", "hellip": "…",
    "mdash": "—", "ndash": "–", "laquo": "«", "raquo": "»", "times": "×",
    "divide": "÷", "plusmn": "±", "deg": "°", "middot": "·", "bull": "•",
    "larr": "←", "rarr": "→", "uarr": "↑", "darr": "↓", "harr": "↔",
    "check": "✓", "cross": "✗", "star": "★", "hearts": "♥", "euro": "€",
    "pound": "£", "yen": "¥", "sect": "§", "para": "¶", "dagger": "†",
    "ldquo": "“", "rdquo": "”", "lsquo": "‘", "rsquo": "’",
}

_AUTOLINK_RE = re.compile(r"<((?:https?|ftp|mailto)://[^\s<>]+|[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>")
_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_ENTITY_RE = re.compile(r"&(#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;|\s+\"([^\"]*)\")?\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;|\s+\"([^\"]*)\")?\)")
_REF_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\[([^\]]*)\]")
_REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*(\S+)(?:\s+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?\s*$")
_DELIM_SYMBOLS = ("***", "___", "**", "__", "~~", "*", "_", "~")
_DELIM_RUN_RE = re.compile(r"\*+|_+|~+")
_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_ESC_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|$])")
_TOKEN_RE = re.compile(r"\x00MK(\d+)\x00")
TOKEN_FMT = "\x00MK%d\x00"
# 行内阶段的私有区标记（正常文本里不可能出现）。四个码位互不重叠 ——
# 曾经把「屏蔽 token」和「转义起止」用了同一个码位，导致转义标记被换成 NUL、
# 页面上漏出字面量 "MK0"、强调配错位。
_ESC_OPEN, _ESC_CLOSE = "\ue000", "\ue001"
_CODE_OPEN, _CODE_CLOSE = "\ue002", "\ue003"
_TOKEN_SHIELD = "\ue010"
# 代码块高亮期间占位尖括号的字符（高亮器自身会做转义，但 _TAG_RE 会把
# 代码里的 <div>/<script> 当成"受保护标签"原样放行 —— 那就是一个 XSS 洞）
_LT_SHIELD, _GT_SHIELD = "\ue014", "\ue015"
# 行内码匹配期间用来占位反引号的字符（见 parse_inline 的 shield 步骤）
_BT_SHIELD = "\ue013"


def _entity_sub(m):
    body = m.group(1)
    if body.startswith("#"):
        return m.group(0)
    return ALIASES.get(body.lower(), m.group(0))


def _autolink_sub(m):
    target = m.group(1)
    if "@" in target and "://" not in target:
        return '<a href="mailto:%s">%s</a>' % (target, target)
    return '<a href="%s" rel="noreferrer noopener">%s</a>' % (
        html.escape(target, quote=True), target)


def parse_inline(text, ctx):
    """行内解析：受保护区间（转义/行内码/标签/自动链接/实体）先抽成 token，最后还原。

    顺序至关重要：
      1) 反斜杠转义必须最先 —— 否则 \\` 会被行内码正则当成定界符；
      2) 裸 HTML 标签与自动链接在文本转义之前摘除，避免正则跨标签匹配；
      3) 强调解析放在最后，且只吃已转义文本，不会碰到 token。
    """
    tokens = []

    def stash(s):
        tokens.append(s)
        return TOKEN_FMT % (len(tokens) - 1)

    # 转义用私有区标记承载，不进 token 池：
    # 若把它塞进 tokens，而行内码内容里正好也含 token，还原时下标就会错位，
    # 页面上会漏出字面量 "MK0"/"MK1"。
    text = _ESC_RE.sub(lambda m: _ESC_OPEN + m.group(1) + _ESC_CLOSE, text)
    # 行内码匹配前先隐去两类字符，匹配后逐次还原：
    #   * NUL —— 已有 token 的内容，参与匹配会打乱 token 下标；
    #   * 转义标记内的反引号（\`）—— 否则行内码正则会跨标记配对，把转义吃掉。
    # 普通反引号必须保留，否则真正的行内码就匹配不到了。
    shield_count = {"\x00": text.count("\x00"), "`": 0}
    shielded = text.replace("\x00", _TOKEN_SHIELD)
    bt_open = re.escape(_ESC_OPEN) + "`"
    bt_close = "`" + re.escape(_ESC_CLOSE)
    shield_count["`"] = len(re.findall(bt_open, shielded)) + len(re.findall(bt_close, shielded))
    shielded = re.sub(bt_open, _ESC_OPEN + _BT_SHIELD, shielded)
    shielded = re.sub(bt_close, _BT_SHIELD + _ESC_CLOSE, shielded)
    code_spans = []

    def stash_code(m):
        code_spans.append(html.escape(m.group(2).strip(), quote=False))
        return _CODE_OPEN + str(len(code_spans) - 1) + _CODE_CLOSE

    shielded = _CODE_SPAN_RE.sub(stash_code, shielded)
    for _ in range(shield_count["\x00"]):
        shielded = shielded.replace(_TOKEN_SHIELD, "\x00", 1)
    for _ in range(shield_count["`"]):
        shielded = shielded.replace(_BT_SHIELD, "`", 1)
    text = shielded
    text = _TAG_RE.sub(lambda m: stash(html.escape(m.group(0), quote=False)), text)
    text = _AUTOLINK_RE.sub(lambda m: stash(_autolink_sub(m)), text)
    text = _ENTITY_RE.sub(lambda m: stash(_entity_sub(m)), text)

    text = html.escape(text, quote=False)

    # 引用式链接：完整式 [t][r] -> 折叠式 [r][] -> 简写 [r]
    text = _REF_DEF_LINK(text, ctx)
    text = _REF_SHORT_RE.sub(lambda m: _shortcut_ref(m, ctx), text)

    def img_sub(m):
        return stash('<img src="%s" alt="%s"%s>' % (
            html.escape(ctx.rewrite_image(m.group(2)), quote=True),
            html.escape(m.group(1), quote=True),
            ' title="%s"' % html.escape(m.group(3) or m.group(4) or "", quote=True)
            if (m.group(3) or m.group(4)) else ""))

    text = _IMAGE_RE.sub(img_sub, text)

    def link_sub(m):
        label = m.group(1)
        title = m.group(3) or m.group(4) or ""
        try:
            href = urllib.parse.unquote(m.group(2))
        except Exception:
            href = m.group(2)
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href):
            target = m.group(2)
            extra = ' rel="noreferrer noopener"'
        else:
            target = html.escape(ctx.rewrite_link(href), quote=True)
            extra = ""
        return stash('<a href="%s"%s%s>%s</a>' % (
            target, ' title="%s"' % html.escape(title, quote=True) if title else "",
            extra, label))

    text = _LINK_RE.sub(link_sub, text)
    text = parse_emphasis(text)
    # 先还原 token，再还原行内码与转义（行内码内容不含 token，顺序无关但更直观）
    text = _TOKEN_RE.sub(lambda m: tokens[int(m.group(1))], text)
    text = re.sub(re.escape(_CODE_OPEN) + r"(\d+)" + re.escape(_CODE_CLOSE),
                  lambda m: "<code>%s</code>" % code_spans[int(m.group(1))], text)
    # 中间必须正好一个非标记字符：否则 (.) 会跨越标记把 <em>…</em> 整段吞掉
    esc_atom = "([^" + re.escape(_ESC_OPEN + _ESC_CLOSE) + "])"
    text = re.sub(re.escape(_ESC_OPEN) + esc_atom + re.escape(_ESC_CLOSE),
                  lambda m: '<span class="esc">%s</span>' %
                  html.escape(m.group(1), quote=False), text)
    return text


def _REF_DEF_LINK(text, ctx):
    """[text][ref] 与折叠式 [ref][]。"""
    def sub(m):
        label = m.group(1)
        key = (m.group(2) or label).strip().lower()
        target = ctx.refs.get(key)
        if target is None:
            return m.group(0)
        url, title = target
        return '<a href="%s"%s>%s</a>' % (
            html.escape(ctx.rewrite_link(urllib.parse.unquote(url)), quote=True),
            ' title="%s"' % html.escape(title, quote=True) if title else "",
            label or key)
    return _REF_LINK_RE.sub(sub, text)


def _shortcut_ref(m, ctx):
    """简写式引用链接 [ref]：只有 refs 里确实定义了才替换。"""
    label = m.group(1).strip()
    target = ctx.refs.get(label.lower())
    if target is None:
        return m.group(0)
    url, title = target
    return '<a href="%s"%s>%s</a>' % (
        html.escape(ctx.rewrite_link(urllib.parse.unquote(url)), quote=True),
        ' title="%s"' % html.escape(title, quote=True) if title else "",
        label)


def _is_punct(ch):
    """ASCII 标点 + Unicode 标点/符号 —— 否则 *斜体*。 这种中文句末标点会关不掉。"""
    if not ch:
        return False
    if ch in _PUNCT:
        return True
    return unicodedata.category(ch)[0] in ("P", "S")


def _ascii_word(ch):
    """ASCII 字母/数字才算「词内」；CJK 不是 —— 中文*强调*中文 应当生效。"""
    return ch.isascii() and ch.isalnum()


def _flanking(text, sym, start, end, prev=None, nxt=None):
    """返回 (can_open, can_close)。

    按 CommonMark 的 flanking 公式，但字符分类改成 ASCII 视角：
      * 空白            -> blank
      * ASCII 字母/数字 -> word（拉丁词内，不算强调）
      * 其它（含 CJK、标点、符号）-> punct-like

    「其它」一律当作标点，于是：
      中文*强调*中文  可以成对（否则中文文档里几乎没一处强调能生效）；
      a*b / 2*3*4     不成对（两侧是 ASCII 词字符，另有硬性词内保护）；
      **粗体**和**又** 也能正常成对（"和" 是 punct-like，不再是死结）。
    """
    if prev is None:
        prev = text[start - 1] if start > 0 else " "
    if nxt is None:
        nxt = text[end] if end < len(text) else " "
    prev_ws, next_ws = prev.isspace(), nxt.isspace()
    prev_p = (not prev_ws) and (not _ascii_word(prev))
    next_p = (not next_ws) and (not _ascii_word(nxt))
    left_flank = (not next_ws) and (not next_p or prev_ws or prev_p)
    right_flank = (not prev_ws) and (not prev_p or next_ws or next_p)
    can_open = left_flank and (not right_flank or prev_p)
    can_close = right_flank and (not left_flank or next_p)
    if _ascii_word(prev) and _ascii_word(nxt):
        can_open = can_close = False        # 拉丁词内一律不成对
    if sym[0] == "_" and _ascii_word(prev):
        can_open = False                    # 词内下划线不算强调
    if sym[0] == "_" and _ascii_word(nxt):
        can_close = False
    return can_open, can_close


# 恰好三个定界符（前后都不能再挨着同类字符），内部允许 ** 之类但不含三连
_T3 = r"(?<!\*)\*{3}(?!\*)"
_T3U = r"(?<!_)_{3}(?!_)"


def _rewrite_triple(text):
    """成对的三连定界符直接产出最终标签：***x*** -> <strong><em>x</em></strong>。

    不在配对算法里处理三连：3 = 2+1 的混合定价边界情况太多，越修越脆。
    这里先一步到位（连同被转义内容一起跳过），扫描器就只需面对
    「同字符同长度」这一种配对规则。
    """
    rx = re.compile(r"(?<![A-Za-z0-9_*])\*{3}(?=\S)((?:(?!\*{3}).)+?)(?<!\s)\*{3}",
                    re.DOTALL)
    rxu = re.compile(r"(?<![A-Za-z0-9_])_{3}(?=\S)((?:(?!_{3}).)+?)(?<!\s)_{3}",
                     re.DOTALL)
    for _ in range(4):      # 允许少量嵌套
        new_text = rx.sub(lambda m: "<strong><em>%s</em></strong>" % m.group(1), text)
        new_text = rxu.sub(lambda m: "<strong><em>%s</em></strong>" % m.group(1), new_text)
        if new_text == text:
            break
        text = new_text
    return text


def _split_run(run, prev_ch, next_ch):
    """把完整的 run 切成可配对的块。返回 [(offset, sym, 左邻, 右邻)]。

    ** _ __ 等长 run 整块处理；*** 与更长的 run 按 2+2+… 切块，
    **_**** 这种就是「关一个 ** + 开一个 **」；*** 切成 (** , *)。
    块的左右邻居用显式字符：run 内部相邻的是 * 而不是词字符，
    否则 **** 整块会被判成「词内」而永远关不上。
    """
    if run.startswith("~"):
        return [(0, run[:2] if len(run) >= 2 else run, prev_ch, next_ch)]
    n = len(run)
    if n <= 2:
        return [(0, run, prev_ch, next_ch)]
    if n == 3:
        chunks = [(0, run[:2]), (2, run[2:])]
    else:
        chunks = [(off, run[off:off + 2]) for off in range(0, n - (n % 2), 2)]
        if n % 2:
            chunks.append((n - 1, run[-1]))
    out = []
    for off, sym in chunks:
        left = run[off - 1] if off > 0 else prev_ch
        right = run[off + len(sym)] if off + len(sym) < n else next_ch
        out.append((off, sym, left, right))
    return out


def _delim_re():
    """匹配完整的同类定界符 run（**、***、****、~~… 一次取全）。

    以前用 ***|**|* 的定界符正则会被贪婪拆成 *** + *，
    于是 **** 永远配不对；现在先取整段 run，再交给 _split_run 切块。
    """
    return _DELIM_RUN_RE


_DELIM_RE_CACHE = None


def parse_emphasis(text):
    """强调解析：定界符 run 扫描 + 从右往左的最近配对。

    定界符：** __ * _ ~~（*** 切成 (** , *)；**** 切成 (** , **)）。
    规则（全部写死在这里，便于审阅）：
      1) flanking：左邻非空白则可开、右邻非空白则可闭；两侧都是 ASCII 字母数字
         则一律不成对（a*b / 2*3*4 保持原样）；_ 左侧是 ASCII 词字符则不可开。
         字符分类把 CJK 当标点，所以 中文*强调*中文 能成对。
      2) 配对：同字符 + 同长度（** 只配 **，* 只配 *）—— 于是 **a* 保持原样。
      3) 绑定顺序：从右往左，右侧 opener 先认领 closer，*** 的两块因此各自对外配对。
      4) 阻塞：closer 要先服务「同字符同长度、且自己另有 closer 在更前面」的未配对
         opener —— 这就是 **粗体 **内** 粗体** 里外层 ** 只包住前半句的原因。
    未配对的定界符一律原样输出，绝不吞文本。
    """
    # 三连定界符先降级成扫描器能稳定处理的等价写法：
    #   ***x***  ->  **_*x*_**   （** 在外、* 在里，正是 <strong><em>）
    #   ___x___  ->  __*_x___  同理（_ 在里）
    # 放在这里而不是塞进配对算法，是因为 2/1 混合定价的边界情况太多，
    # 降级后只剩「同字符同长度」一种配对，行为可预测且好测。
    text = _rewrite_triple(text)

    nodes = []          # (kind, sym, pos, run_id)
    pos = 0
    run_id = 0
    for m in _delim_re().finditer(text):
        if m.start() > pos:
            nodes.append(("text", text[pos:m.start()], pos, None, 0, 1))
        run = m.group(0)
        prev_ch = text[m.start() - 1] if m.start() > 0 else " "
        next_ch = text[m.end()] if m.end() < len(text) else " "
        # 被转义的定界符（形如 ESC_OPEN + 字符 + ESC_CLOSE）只作为字面量节点，
        # 不参与配对 —— 注意不能 continue 跳过：跳过会打乱文本切片，输出重复。
        escaped = (prev_ch == _ESC_OPEN or next_ch == _ESC_CLOSE)
        chunks = _split_run(run, prev_ch, next_ch)
        for cidx, (off, sym, left, right) in enumerate(chunks):
            s0 = m.start() + off
            can_open, can_close = _flanking(text, sym, s0, s0 + len(sym),
                                            prev=left, nxt=right)
            if escaped:
                kind = "text"
            else:
                kind = ("both" if can_open and can_close else
                        "open" if can_open else "close" if can_close else "text")
            nodes.append((kind, sym, s0, run_id, cidx, len(chunks)))
        run_id += 1
        pos = m.end()
    if pos < len(text):
        nodes.append(("text", text[pos:], pos, None, 0, 1))

    def can_match(opener, closer):
        """同字符 + 同长度。~ 要求双方都至少两个。"""
        if opener.startswith("~") or closer.startswith("~"):
            return (opener.startswith("~") and closer.startswith("~")
                    and len(opener) >= 2 and len(closer) >= 2)
        return opener[0] == closer[0] and len(opener) == len(closer)

    def same_slot(i, j):
        """当前不做块位次约束（只保留逐块 flanking）。

        曾经试过「同一次 run 的第 i 块只配第 i 块」，但会把普通 ** 与 **** 里的
        ** 也隔开，导致 **a****b** 退化成 <strong>a****b</strong>，得不偿失。
        """
        return True

    def nearest_closer(start, frm, sym, opener_idx):
        for j in range(max(start, frm), len(nodes)):
            kind, other = nodes[j][0], nodes[j][1]
            if kind in ("close", "both") and can_match(sym, other) \
                    and same_slot(opener_idx, j):
                return j
        return None

    closer = {}
    frames = {}

    def blocked_before(a, b, sym, my_run):
        """[a,b) 内是否有「同字符同长度、且自己另有 closer 在 b 之前」的未配对 opener。

        注意 a 必须是当前 opener 的下一个位置 —— 当前 opener 之前的未配对 opener
        不能阻塞它，否则 见 **粗体 **内** 粗体** 的外层 ** 会被自己前面的东西挡住。
        """
        for k in range(a, b):
            kind, other, _p, run = nodes[k][:4]
            if run is not None and run == my_run:
                continue
            if kind not in ("open", "both") or k in closer:
                continue
            if other[0] != sym[0] or not can_match(sym, other):
                continue
            for j in range(k + 1, b):
                if nodes[j][0] in ("close", "both") and can_match(other, nodes[j][1]) \
                        and same_slot(k, j):
                    return True
        return False

    for i in range(len(nodes) - 1, -1, -1):
        kind, sym, _p, run = nodes[i][:4]
        if kind not in ("open", "both") or i in closer:
            continue
        hit = None
        j = i + 1
        while True:
            j = nearest_closer(i + 1, j, sym, i)
            if j is None:
                break
            if j in closer.values():
                j += 1                     # 这个 closer 已被更靠右的 opener 认领
                continue
            if blocked_before(i + 1, j, sym, run):
                j += 1
                continue
            hit = j
            break
        if hit is not None:
            closer[i] = hit
            frames[i] = {"sym": sym, "close": hit, "rendered": None}

    def render_frame(fid):
        fr = frames[fid]
        if fr["rendered"] is not None:
            return fr["rendered"]
        parts = []
        i = fid + 1
        while i < fr["close"]:
            node = nodes[i]
            if node[0] == "text":
                parts.append(node[1])
                i += 1
                continue
            child = closer.get(i)
            if child is not None and child < fr["close"]:
                parts.append(render_frame(i))
                i = child + 1
            else:
                parts.append(node[1])
                i += 1
        fr["rendered"] = _wrap_tag(fr["sym"], "".join(parts))
        return fr["rendered"]

    out = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if node[0] != "text" and i in closer:
            out.append(render_frame(i))
            i = closer[i] + 1
            continue
        out.append(node[1])
        i += 1
    return "".join(out)


def _wrap_tag(sym, inner):
    if sym is None:
        return inner
    if sym.startswith("~"):
        return "<del>%s</del>" % inner
    if len(sym) >= 3:
        return "<strong><em>%s</em></strong>" % inner
    if len(sym) == 2:
        return "<strong>%s</strong>" % inner
    return "<em>%s</em>" % inner


def parse_emphasis_inner(text):
    """兼容旧调用：强调内部同样走扫描器。"""
    return parse_emphasis(text)


def _restore(s, tokens):
    return re.sub(r"\x00MK(\d+)\x00", lambda m: tokens[int(m.group(1))], s)


# ============================================================================
# SECTION 6  URL REWRITE
# ============================================================================

def quote_seg(seg):
    return urllib.parse.quote(seg, safe="")


def _split_target(href):
    frag = ""
    if "#" in href:
        href, frag = href.split("#", 1)
        frag = "#" + frag
    query = ""
    if "?" in href:
        href, query = href.split("?", 1)
        query = "?" + query
    return href, query, frag


def _resolve_target(href, base_dir):
    """文档内相对链接 -> 根相对路径，例如 /a/b.md。永远不越出根（../ 被夹紧）。"""
    if not href:
        return None
    if href.startswith("//"):
        return href
    trail = "/" if href.endswith("/") else ""
    body = href.rstrip("/")
    if href.startswith("/"):
        joined = posixpath.normpath(body).lstrip("/")
    elif base_dir:
        joined = posixpath.normpath(posixpath.join(base_dir, body))
    else:
        joined = posixpath.normpath(body)
    if joined in (".", "/"):
        return "/"
    if joined.startswith("../") or joined == "..":
        return None  # 越界：调用方保留原始文本，不做重写
    # 返回根相对路径（带前导 /）：页面 URL 形如 /docs/a.html，
    # 若返回 "docs/sub/b.html" 浏览器会拼成 /docs/docs/sub/b.html。
    return "/" + joined + trail


class RenderContext(object):
    """一次渲染所需的上下文：当前文档相对路径、引用式链接表、服务根（可空）。"""

    def __init__(self, rel_path, refs=None, root=None):
        self.rel_path = rel_path
        self.base = posixpath.dirname(rel_path)   # 文档所在目录，用于解析相对链接
        self.root = root                          # 服务根绝对路径，用于绝对路径兜底
        self.refs = refs or {}

    def _url_for(self, href):
        """返回 (URL, 是否重写成功)。越界链接不重写也不改扩展名。

        以 / 开头的路径按「服务根」解析（与站点语义一致，同一个 URL 永远指向
        同一个文件）。要让它命中文档库根目录，就用 `--root <文档库根>` 启动 ——
        main() 会在检测到根目录里没有 docs 之类子目录时给出提示。
        """
        resolved = _resolve_target(href, self.base)
        if resolved is None:
            return quote_seg_path(href), False
        return quote_seg_path(resolved), True

    def rewrite_link(self, href):
        """文档间链接保留 .md 后缀 —— URL 与磁盘一致。

        服务端对 /x.md 直接渲染 HTML、对 /x.md?raw=1 返回原文，
        所以刷新、收藏、分享链接都不会 404；不需要 .html 伪路径。
        """
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href):
            return href
        if href.startswith("#"):
            return href
        target, query, frag = _split_target(href)
        url, _rewritten = self._url_for(target)
        return url + query + frag

    def rewrite_image(self, href):
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href):
            return href
        target, query, frag = _split_target(href)
        url, _rewritten = self._url_for(target)
        return url + query + frag


def quote_seg_path(path):
    """按 / 分段做百分号编码，保留前导 /。"""
    if path.startswith("http://") or path.startswith("https://") or \
            re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
        return path
    return "/".join(quote_seg(seg) for seg in path.split("/"))


def slugify(text):
    """标题锚点：可复现的 slug（HTML 标签当分隔符，再去标点）。中文保留。

    标签处理成空格而不是直接删掉：否则「1.1 Python（`python`）」这类标题
    会把行内码内容直接粘成 pythonpython，锚点难读也不稳定。
    """
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).strip().lower()
    out = []
    for ch in text:
        if ch.isspace():
            out.append("-")
        elif ch == "-" or ch == "_" or unicodedata.category(ch)[0] in ("L", "N"):
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "section"


# ============================================================================
# SECTION 7  BLOCKS
# ============================================================================

RE_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*#*[ \t]*$")
RE_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*(.*)$")
RE_HR = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
RE_QUOTE = re.compile(r"^ {0,3}>[ \t]?(.*)$")
RE_ULIST = re.compile(r"^( {0,3})([-*+])[ \t]+(.*)$")
RE_OLIST = re.compile(r"^( {0,3})(\d{1,9})([.)])[ \t]+(.*)$")
RE_TABLE_SEP = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")
RE_SETEXT = re.compile(r"^ {0,3}(=+|-{1,})[ \t]*$")
RE_TASK = re.compile(r"^\[([ xX])\][ \t]+(.*)$", re.DOTALL)


def split_table_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells = []
    buf = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def _align_of(spec):
    spec = spec.strip()
    left, right = spec.startswith(":"), spec.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return ""


def _is_table_start(lines, i):
    if i + 1 >= len(lines):
        return False
    if "|" not in lines[i]:
        return False
    sep = lines[i + 1].strip().strip("|")
    if not sep:
        return False
    if not RE_TABLE_SEP.match(lines[i + 1]):
        return False
    return len(split_table_row(lines[i])) >= 1


def expand_tabs(s):
    return s.replace("\t", "    ")


def indent_of(s):
    return len(s) - len(s.lstrip(" "))


def render_markdown(text, rel_path=""):
    """入口：Markdown 文本 -> HTML 片段。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    refs, kept = {}, []
    for line in lines:
        m = _REF_DEF_RE.match(line)
        if m and "|" not in line and not RE_ULIST.match(line):
            refs.setdefault(m.group(1).strip().lower(),
                            (m.group(2), m.group(3) or m.group(4) or m.group(5) or ""))
            kept.append("")
        else:
            kept.append(line)
    ctx = RenderContext(rel_path, refs, CFG.root if CFG.root else None)
    ctx.slug_counts = {}
    return render_blocks(kept, ctx)


def render_blocks(lines, ctx):
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # --- 围栏代码块 -------------------------------------------------
        m = RE_FENCE.match(line)
        if m:
            fence = m.group(2)
            info = m.group(3)
            buf = []
            i += 1
            while i < n:
                close = re.match(r"^ {0,3}(%s{%d,})[ \t]*$" % (re.escape(fence[0]), len(fence)),
                                 lines[i])
                if close:
                    i += 1
                    break
                buf.append(lines[i])
                i += 1
            code = "\n".join(buf)
            lang = _lang_of(info)
            label = LANG_LABEL.get(lang, lang)
            cls = ' class="language-%s"' % html.escape(lang, quote=True) if lang else ""
            hdr = ('<div class="codehdr"><span class="meta">%s</span></div>'
                   % html.escape(label)) if label else ""
            out.append('<div class="codeblock">%s<pre><code%s>%s</code></pre></div>'
                       % (hdr, cls, highlight(code, info)))
            continue

        # --- ATX 标题 ---------------------------------------------------
        m = RE_ATX.match(line)
        if m:
            level = len(m.group(1))
            raw = (m.group(2) or "").strip()
            inner = parse_inline(raw, ctx)
            out.append(_heading(level, inner, ctx))
            i += 1
            continue

        # --- 分隔线 -----------------------------------------------------
        if RE_HR.match(line):
            out.append("<hr>")
            i += 1
            continue

        # --- 表格 -------------------------------------------------------
        if _is_table_start(lines, i):
            header = split_table_row(lines[i])
            aligns = [_align_of(c) for c in split_table_row(lines[i + 1])]
            rows = []
            j = i + 2
            while j < n and lines[j].strip() and "|" in lines[j] \
                    and not RE_FENCE.match(lines[j]):
                rows.append(split_table_row(lines[j]))
                j += 1
            out.append(_table(header, aligns, rows, ctx))
            i = j
            continue

        # --- 引用 -------------------------------------------------------
        if RE_QUOTE.match(line):
            buf = []
            while i < n:
                qm = RE_QUOTE.match(lines[i])
                if qm:
                    buf.append(qm.group(1))
                    i += 1
                elif not lines[i].strip():
                    # 引用内的空行：看下一行是否还是引用
                    if i + 1 < n and RE_QUOTE.match(lines[i + 1]):
                        buf.append("")
                        i += 1
                    else:
                        break
                else:
                    break
            out.append("<blockquote>\n%s\n</blockquote>" % render_blocks(buf, ctx))
            continue

        # --- 列表 -------------------------------------------------------
        if RE_ULIST.match(line) or RE_OLIST.match(line):
            html_list, i = _render_list(lines, i, ctx)
            out.append(html_list)
            continue

        # --- Setext 标题：只支持 === 形式 ---------------------------------
        # 有意不支持 "文字\n---"：那份 "---" 在真实文档里绝大多数是分隔线，
        # 当标题会让「段落 + 分隔线」这种最常见的写法整段出错。
        if i + 1 < n and line.strip() and "|" not in line \
                and RE_SETEXT.match(lines[i + 1]) \
                and lines[i + 1].lstrip().startswith("=") \
                and not RE_ULIST.match(lines[i + 1]) and not RE_OLIST.match(lines[i + 1]):
            sm = RE_SETEXT.match(lines[i + 1])
            level = 1 if sm.group(1).startswith("=") else 2
            out.append(_heading(level, parse_inline(line.strip(), ctx), ctx))
            i += 2
            continue

        # --- 段落 -------------------------------------------------------
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not _starts_block(lines, i):
            buf.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % parse_inline(" ".join(x.strip() for x in buf), ctx))

    return "\n".join(x for x in out if x)


def _starts_block(lines, i):
    """第 i 行是否能中断当前段落（可含 0-3 个前导空格）。

    必须用 lstrip 后的文本匹配：否则缩进的嵌套列表标记（"  - x"）会被
    当作普通续行吸进段落，嵌套结构整个丢掉。
    """
    line = lines[i]
    stripped = expand_tabs(line).lstrip(" ")
    if RE_ATX.match(stripped) or RE_FENCE.match(stripped) or RE_HR.match(stripped):
        return True
    if RE_QUOTE.match(line) or RE_ULIST.match(line) or RE_OLIST.match(line) \
            or RE_ULIST.match(stripped) or RE_OLIST.match(stripped):
        return True
    if _is_table_start(lines, i):
        return True
    nxt = lines[i + 1] if i + 1 < len(lines) else ""
    if RE_SETEXT.match(nxt) and nxt.lstrip().startswith("=") \
            and "|" not in line and not RE_ULIST.match(nxt):
        return True
    return False
def _heading(level, inner, ctx):
    slug = slugify(inner)
    counts = getattr(ctx, "slug_counts", None)
    if counts is None:
        counts = ctx.slug_counts = {}
    seen = counts.get(slug, 0)
    counts[slug] = seen + 1
    anchor = slug if seen == 0 else "%s-%d" % (slug, seen)
    return '<h%d id="%s">%s</h%d>' % (level, html.escape(anchor, quote=True), inner, level)


def _table(header, aligns, rows, ctx):
    def cell(tag, content, idx):
        align = aligns[idx] if idx < len(aligns) else ""
        style = ' style="text-align:%s"' % align if align else ""
        return "<%s%s>%s</%s>" % (tag, style, parse_inline(content, ctx), tag)
    head = "<tr>%s</tr>" % "".join(cell("th", c, k) for k, c in enumerate(header))
    body_rows = []
    for row in rows:
        row = row + [""] * max(0, len(header) - len(row))
        body_rows.append("<tr>%s</tr>" % "".join(
            cell("td", c, k) for k, c in enumerate(row[:len(header)])))
    return "<table>\n<thead>%s</thead>\n<tbody>%s</tbody>\n</table>" % (
        head, "\n".join(body_rows))


def _render_list(lines, start, ctx):
    """列表渲染：收集条目原始行，统一 dedent 后递归解析（天然支持嵌套）。

    dedent 取「条目内非首行的公共最小缩进」而不是固定值：
    固定剥一层会把更深的嵌套列表变成普通续行文本。
    松列表（条目之间有空行）时保留 <p> 外壳，紧凑列表剥掉。
    """
    ordered = bool(RE_OLIST.match(lines[start]))
    start_num = int(RE_OLIST.match(lines[start]).group(2)) if ordered else 1
    n = len(lines)
    items = []          # [(item_lines, blank_before)]
    i = start

    while i < n:
        um, om = RE_ULIST.match(lines[i]), RE_OLIST.match(lines[i])
        if ordered and om:
            indent, content = len(om.group(1)), om.group(4)
        elif not ordered and um:
            indent, content = len(um.group(1)), um.group(3)
        else:
            break

        blank_before = False
        item_lines = [content]
        i += 1
        while i < n:
            cur = lines[i]
            if not cur.strip():
                k = i
                while k < n and not lines[k].strip():
                    k += 1
                if k >= n:
                    i = k
                    break
                nxt = lines[k]
                nm_u, nm_o = RE_ULIST.match(nxt), RE_OLIST.match(nxt)
                nxt_indent = indent_of(expand_tabs(nxt))
                if (nm_u and len(nm_u.group(1)) <= indent) or \
                        (nm_o and len(nm_o.group(1)) <= indent) or nxt_indent <= indent:
                    blank_before = True
                    i = k
                    break
                item_lines.append("")
                i = k
                continue
            if indent_of(expand_tabs(cur)) <= indent:
                break
            item_lines.append(expand_tabs(cur))
            i += 1
        items.append((item_lines, blank_before, indent))

    is_loose = any(blank for _lines, blank, _ind in items)

    html_items = []
    for item_lines, _blank, indent in items:
        body_lines = _dedent_item(item_lines, indent)
        task = None
        if body_lines:
            tm = RE_TASK.match(body_lines[0].strip())
            if tm:
                task = tm.group(1).lower() == "x"
                body_lines[0] = tm.group(2)
        inner = render_blocks(body_lines, ctx)
        if not is_loose and inner.startswith("<p>") and inner.endswith("</p>") \
                and inner.count("<p>") == 1 and "<ul>" not in inner and "<ol>" not in inner:
            inner = inner[3:-4]
        if task is not None:
            box = '<input type="checkbox" disabled%s>' % (" checked" if task else "")
            if inner.startswith("<p>"):
                inner = "<p>" + box + inner[3:]
            else:
                inner = box + " " + inner
            cls = ' class="task"'
        else:
            cls = ""
        html_items.append("<li%s>%s</li>" % (cls, inner))

    if ordered:
        attrs = ' start="%d"' % start_num if start_num != 1 else ""
        return "<ol%s>\n%s\n</ol>" % (attrs, "\n".join(html_items)), i
    return "<ul>\n%s\n</ul>" % "\n".join(html_items), i


def _dedent_item(item_lines, parent_indent=0):
    """按「父条目内容起始列」剥缩进，保留相对层级。

    - a          首行无缩进
      - b        缩进 2 -> 剥 2 变成 0（还是子列表）
        - c      缩进 4 -> 剥 2 变成 2（保持孙层级）
    若按最小缩进统一剥，子列表会塌成同级，嵌套就丢了。
    """
    pad = parent_indent + 2
    if len(item_lines) <= 1:
        ln = item_lines[0] if item_lines else ""
        return [ln[pad:] if len(ln) > pad and ln[:pad].strip() == "" else ln]
    indents = [indent_of(ln) for ln in item_lines[1:] if ln.strip()]
    if indents:
        pad = min(pad, min(indents))
    out = [item_lines[0]]
    for ln in item_lines[1:]:
        out.append(ln[pad:] if ln.strip() else "")
    return out
def list_entries(abs_dir, rel_dir):
    """返回 [(is_dir, name, size, mtime)]，目录在前，名称大小写不敏感排序。"""
    entries = []
    try:
        names = os.listdir(abs_dir)
    except OSError:
        return entries
    for name in names:
        full = os.path.join(abs_dir, name)
        try:
            is_dir = os.path.isdir(full)
            st = os.stat(full)
        except OSError:
            continue
        entries.append((is_dir, name, 0 if is_dir else st.st_size, st.st_mtime))
    entries.sort(key=lambda e: (not e[0], e[1].lower()))
    return entries


def render_dir_listing(abs_dir, rel_dir):
    entries = list_entries(abs_dir, rel_dir)
    if not entries:
        return '<p class="note">这个目录是空的。</p>'
    rows = []
    for is_dir, name, size, mtime in entries:
        href = "/" + "/".join(quote_seg(x) for x in (rel_dir.split("/") if rel_dir else [])
                              + [name])
        if is_dir:
            href += "/"
            icon, cls, meta = "📁", "d", "目录"
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext == MD_EXT:
                icon, cls = "📝", ""
            elif ext in IMAGE_EXT:
                icon, cls = "🖼", ""
            else:
                icon, cls = "📄", ""
            meta = _fmt_size(size) + " · " + time.strftime("%Y-%m-%d %H:%M",
                                                           time.localtime(mtime))
        rows.append('<li class="%s"><span class="nm">%s <a href="%s">%s</a></span>'
                    '<span class="meta">%s</span></li>' % (
                        cls, icon, html.escape(href, quote=True), html.escape(name), meta))
    return '<ul class="dirlist">\n%s\n</ul>' % "\n".join(rows)


def render_tree(abs_dir, rel_dir, depth_left):
    entries = list_entries(abs_dir, rel_dir)
    if not entries:
        return ""
    out = ["<ul>"]
    for is_dir, name, size, mtime in entries:
        if is_dir and name in SKIP_DIRS:
            continue
        child_rel = (rel_dir + "/" + name) if rel_dir else name
        href = "/" + "/".join(quote_seg(x) for x in child_rel.split("/"))
        if is_dir:
            href += "/"
            out.append('<li>📁 <a href="%s">%s</a>%s</li>' % (
                html.escape(href, quote=True), html.escape(name),
                render_tree(os.path.join(abs_dir, name), child_rel, depth_left - 1)
                if depth_left > 1 else ""))
        else:
            ext = os.path.splitext(name)[1].lower()
            icon = "📝" if ext == MD_EXT else ("🖼" if ext in IMAGE_EXT else "📄")
            out.append('<li>%s <a href="%s">%s</a> <span class="meta">%s</span></li>' % (
                icon, html.escape(href, quote=True), html.escape(name), _fmt_size(size)))
    out.append("</ul>")
    return "\n".join(out)


def iter_markdown(abs_root):
    for dirpath, dirnames, filenames in os.walk(abs_root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.lower().endswith(MD_EXT):
                yield os.path.join(dirpath, fn)


def search_markdown(abs_root, query, cap=MD_SEARCH_CAP, context=SEARCH_CONTEXT):
    """返回 (results, scanned, truncated)。results: [(rel, lineno, [(n, line, hit)])]"""
    needle = query.lower()
    results = []
    scanned = 0
    truncated = False
    for path in iter_markdown(abs_root):
        if len(results) >= cap:
            truncated = True
            break
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().split("\n")
        except OSError:
            continue
        scanned += 1
        rel = os.path.relpath(path, abs_root).replace(os.sep, "/")
        for idx, line in enumerate(lines):
            if needle in line.lower():
                lo = max(0, idx - context)
                hi = min(len(lines), idx + context + 1)
                block = [(k + 1, lines[k], needle in lines[k].lower()) for k in range(lo, hi)]
                results.append((rel, idx + 1, block))
                if len(results) >= cap:
                    truncated = True
                    break
    return results, scanned, truncated


def render_search_page(query, results, scanned, truncated):
    if not query:
        body = ('<h1>搜索</h1>\n<p class="note">输入关键词后在全部 Markdown 文件里做'
                '大小写不敏感的子串匹配；文件名命中与正文命中分两块展示。</p>')
        return _page("搜索", body)

    name_hits = [r for r in results if query.lower() in posixpath.basename(r[0]).lower()]
    body_hits = [r for r in results if r not in name_hits]

    html_parts = ["<h1>搜索：%s</h1>" % html.escape(query)]
    html_parts.append('<p class="note">正文命中 %d 处，文件名命中 %d 处；扫描了 %d 个 '
                      'Markdown 文件。%s</p>' % (
                          len(body_hits), len(name_hits), scanned,
                          "结果已达上限，请细化关键词。" if truncated else ""))

    def block(rel, lineno, lines, show_ctx=True):
        href = "/" + "/".join(quote_seg(x) for x in rel.split("/"))
        rows = []
        if show_ctx:
            for lno, text, is_hit in lines:
                safe = html.escape(text)
                if is_hit:
                    safe = _mark(safe, query)
                rows.append('<span class="ln">%d</span>%s' % (lno, safe))
        return ('<div class="hit"><div class="where">📝 <a href="%s#L%d">%s</a> : 第 %d 行'
                '</div><pre>%s</pre></div>' % (
                    html.escape(href, quote=True), lineno, html.escape(rel), lineno,
                    "\n".join(rows)))

    if name_hits:
        html_parts.append("<h2>文件名命中</h2>")
        for rel, lineno, lines in name_hits[:60]:
            html_parts.append(block(rel, lineno, lines, show_ctx=False))
    if body_hits:
        html_parts.append("<h2>正文命中</h2>")
        for rel, lineno, lines in body_hits:
            html_parts.append(block(rel, lineno, lines))
    if not results:
        html_parts.append('<p class="note">没有命中。换一个关键词试试。</p>')
    return _page("搜索：%s" % query, "\n".join(html_parts), search_q=query)


def _mark(escaped_line, query):
    """在已转义的文本里高亮查询串（大小写不敏感，避开 HTML 实体边界）。"""
    if not query:
        return escaped_line
    out = []
    low_line, low_q = escaped_line.lower(), query.lower()
    pos = 0
    while True:
        k = low_line.find(low_q, pos)
        if k < 0:
            out.append(escaped_line[pos:])
            break
        out.append(escaped_line[pos:k])
        out.append("<mark>%s</mark>" % escaped_line[k:k + len(query)])
        pos = k + len(query)
    return "".join(out)


# ============================================================================
# SECTION 9  HANDLER
# ============================================================================

class Config(object):
    def __init__(self):
        self.root = os.getcwd()
        self.safe = False
        self.depth = 0
        self.search = True
        self.raw_ok = True


CFG = Config()
_RENDER_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _resolve(abs_root, url_path):
    """URL 路径 -> 绝对路径。../ 被夹紧在 root 内（不可能越出），只拒绝 NUL 等病态输入。"""
    rel = urllib.parse.unquote(url_path)
    if "\x00" in rel:
        return None, ""
    rel = rel.replace("\\", "/")
    rel = posixpath.normpath("/" + rel).lstrip("/")
    if rel in (".", "/"):
        rel = ""
    abs_path = os.path.normpath(os.path.join(abs_root, rel.replace("/", os.sep)))
    root = os.path.normpath(abs_root)
    if abs_path != root and not abs_path.startswith(root + os.sep):
        return None, rel
    return abs_path, rel


class Handler(BaseHTTPRequestHandler):
    server_version = "mdview/" + __version__
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # --- 响应工具 -------------------------------------------------------
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        ctype = MIME.get(ext)
        if ctype is None:
            ctype = "application/octet-stream"
        try:
            size = os.path.getsize(path)
            fh = open(path, "rb")
        except OSError:
            self._send(HTTPStatus.NOT_FOUND, _error_page("404", "文件不存在"))
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command == "HEAD":
            fh.close()
            return
        with fh:
            while True:
                chunk = fh.read(64 * 1024)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return

    # --- 路由 -----------------------------------------------------------
    def do_GET(self):
        try:
            self._route()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:  # 任何意外都返回 500 而不是断开连接
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR,
                       _error_page("500", "服务端内部错误", repr(exc)))

    do_HEAD = do_GET

    def _route(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        abs_path, rel = _resolve(CFG.root, path)
        if abs_path is None:
            self._send(HTTPStatus.FORBIDDEN,
                       _error_page("403", "路径越界：解析结果不在服务根目录内"))
            return

        if path == "/search" or path == "/search/":
            if not CFG.search:
                self._send(HTTPStatus.NOT_FOUND, _error_page("404", "搜索已关闭（--no-search）"))
                return
            query = (qs.get("q") or [""])[0].strip()
            if not query:
                self._send(HTTPStatus.OK, render_search_page("", [], 0, False))
                return
            results, scanned, truncated = search_markdown(CFG.root, query)
            self._send(HTTPStatus.OK,
                       render_search_page(query, results, scanned, truncated))
            return

        if os.path.isdir(abs_path):
            if not path.endswith("/") and rel:
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                self.send_header("Location", quote_seg_path(path) + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._send(HTTPStatus.OK, self._dir_page(abs_path, rel, qs))
            return

        if not os.path.exists(abs_path):
            self._send(HTTPStatus.NOT_FOUND, _error_page("404", "文件不存在", rel))
            return

        raw = (qs.get("raw") or ["0"])[0] not in ("0", "", "false", "no")
        if CFG.safe and os.path.splitext(abs_path)[1].lower() not in SAFE_EXT:
            self._send(HTTPStatus.NOT_FOUND,
                       _error_page("404", "safe 模式下只服务 .md 与图片", rel))
            return

        ext = os.path.splitext(abs_path)[1].lower()
        if ext == MD_EXT and not raw:
            self._send(HTTPStatus.OK, self._markdown_page(abs_path, rel))
            return
        self._send_file(abs_path)

    def _dir_page(self, abs_dir, rel, qs):
        depth = CFG.depth
        try:
            if "depth" in qs:
                depth = max(0, int((qs.get("depth") or ["0"])[0]))
        except ValueError:
            depth = CFG.depth
        title = "索引 " + ("/" + rel if rel else "/")
        parts = [_crumbs(rel)] if rel else []
        if rel:
            parts.append('<p><a href="%s">../ 上级目录</a></p>' %
                         ("/" + "/".join(quote_seg(x) for x in rel.split("/")[:-1]) + "/"
                          if "/" in rel else "/"))
        if depth > 0:
            parts.append('<p class="note">已展开 %d 层目录树。'
                         '去掉 URL 里的 <code>?depth=</code> 可回到分层浏览。</p>' % depth)
            tree = render_tree(abs_dir, rel, depth)
            body = "\n".join(parts) + '<div class="tree">%s</div>' % (tree or "<p>空目录。</p>")
        else:
            tree_nav = '<a class="btn" href="?depth=3">展开 3 层树</a>'
            body = "\n".join(parts) + render_dir_listing(abs_dir, rel)
            return _page(title, body, nav_right=tree_nav, show_search=CFG.search,
                         depth_nav=('<span class="brand">%s</span>' % html.escape(rel))
                         if rel else "")
        return _page(title, body, show_search=CFG.search,
                     depth_nav=('<span class="brand">%s</span>' % html.escape(rel))
                     if rel else "")

    def _markdown_page(self, abs_path, rel):
        st = os.stat(abs_path)
        key = (abs_path, st.st_mtime_ns, st.st_size)
        with _CACHE_LOCK:
            cached = _RENDER_CACHE.get(key)
        if cached is None:
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                self._send(HTTPStatus.NOT_FOUND, _error_page("404", "无法读取文件", rel))
                return
            cached = render_markdown(text, rel)
            with _CACHE_LOCK:
                if len(_RENDER_CACHE) > 512:
                    _RENDER_CACHE.clear()
                _RENDER_CACHE[key] = cached
        title = posixpath.basename(rel)
        raw_link = ('<a class="btn" href="%s?raw=1" title="查看原始 Markdown">源</a>'
                    % html.escape(quote_seg_path(self.path.split("?")[0]), quote=True))
        body = _crumbs(rel) + "\n" + cached
        return _page(title, body, nav_right=raw_link, show_search=CFG.search,
                     depth_nav='<span class="brand">%s</span>' % html.escape(rel))


# ============================================================================
# SECTION 10  CLI
# ============================================================================

def local_ip_hint():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def bind_server(host, port, tries=10):
    last = None
    for offset in range(tries):
        p = port + offset
        try:
            httpd = ThreadingHTTPServer((host, p), Handler)
            httpd.daemon_threads = True
            return httpd, p
        except OSError as exc:
            last = exc
            print("端口 %d 不可用（%s），尝试 %d…" % (p, exc.strerror or exc, p + 1))
    raise SystemExit("连续 %d 个端口都被占用，最后错误：%s" % (tries, last))


def build_parser():
    p = argparse.ArgumentParser(
        prog="mdview.py",
        description="零依赖离线 Markdown 预览服务器（只用 Python 标准库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python3 mdview.py                          # 0.0.0.0:8000，服务当前目录
  python3 mdview.py --port 9000 --root ~/notes
  python3 mdview.py --depth 3                # 首页直接展开 3 层目录树
  python3 mdview.py --safe                   # 只服务 .md + 图片，其余 404
  python3 mdview.py --no-search              # 关闭全文搜索

注意: 默认绑定 0.0.0.0 且任意文件可读，等同于把 --root 下的全部内容
      暴露给局域网（含隐藏文件）。启动 banner 会打印真实范围；需要收紧
      请加 --safe 并把 --host 改成 127.0.0.1。""")
    p.add_argument("--host", default="0.0.0.0",
                   help="监听地址（默认 0.0.0.0，局域网可访问；本机专用填 127.0.0.1）")
    p.add_argument("--port", type=int, default=8000,
                   help="监听端口（默认 8000，被占用时自动 +1 重试）")
    p.add_argument("--root", default=None,
                   help="服务根目录（默认：启动时的当前工作目录）")
    p.add_argument("--depth", type=int, default=0,
                   help="目录索引首页展开层数（默认 0=分层浏览，3 左右比较合适）")
    p.add_argument("--safe", action="store_true",
                   help="只服务 .md 与图片（png/jpg/gif/svg/webp/bmp/ico/avif），其余 404")
    p.add_argument("--no-search", action="store_true", help="关闭全文搜索页")
    p.add_argument("--no-wait", action="store_true",
                   help="启动时不打印 3 秒暂停（保留兼容，本版本默认不停顿）")
    p.add_argument("--version", action="version", version="mdview " + __version__)
    return p


def banner(host, port, cfg):
    root = os.path.abspath(cfg.root)
    shown = host if host not in ("0.0.0.0", "::") else "<所有网卡>"
    shown += ":" + str(port)
    exposure = ("任意文件可读（等同静态文件服务器）" if not cfg.safe
                else "仅 .md 与图片")
    print("=" * 68)
    print(" mdview %s  零依赖离线 Markdown 预览" % __version__)
    print("-" * 68)
    print(" 本机访问   : http://127.0.0.1:%d/" % port)
    if host in ("0.0.0.0", "::", ""):
        print(" 局域网访问 : http://%s:%d/" % (local_ip_hint(), port))
    print(" 监听       : %s" % shown)
    print(" 服务根目录 : %s" % root)
    print(" 可读范围   : %s" % exposure)
    print(" 搜索       : %s" % ("开启" if cfg.search else "关闭"))
    print(" 索引深度   : %s" % (("%d 层（首页展开树）" % cfg.depth) if cfg.depth
                                else "分层浏览（首页只列当前层）"))
    if not cfg.safe and host in ("0.0.0.0", "::", ""):
        print("-" * 68)
        print(" ⚠ 局域网内任何人都能读取上述目录下的全部文件（含隐藏文件）。")
        print("   只想自己看:  --host 127.0.0.1      只想给 .md: --safe")
    if not _has_md(root, 0):
        cands = _docs_root_candidates(root)
        if cands:
            print("-" * 68)
            print(" 提示：当前根目录下没有 .md，但 %s 里有文档。" % cands[0])
            print("       文档里的 /xxx 站内路径按【服务根】解析，")
            print("       要让 /media/... 这类引用生效，请改用：")
            print("         python3 %s --root %s" % (
                os.path.basename(sys.argv[0] or "mdview.py"), cands[0]))
    print("=" * 68)
    sys.stdout.flush()


_ASSET_DIRS = {"media", "images", "image", "img", "assets", "static", "attachments"}


def _find_md_root(root, max_depth=3):
    """在根目录下找一个「文档库根」，用于给出 --root 建议（相对路径或 None）。

    同时含 .md 与资源目录（media/images/assets…）的目录最像文档库根 ——
    文档里的 /media/xxx 正是在那一层才成立，所以优先选它。
    """
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    for name in sorted(os.listdir(root) if os.path.isdir(root) else []):
        if name.startswith(".") or name in skip:
            continue
        full = os.path.join(root, name)
        if os.path.isdir(full) and _has_md(full, max_depth):
            return name
    return None


def _docs_root_candidates(root):
    """返回候选的文档库根（相对路径），按「像文档库」的程度排序。"""
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
    scored = []

    def walk(rel, depth):
        if depth < 0:
            return
        full = os.path.join(root, rel) if rel else root
        try:
            names = os.listdir(full)
        except OSError:
            return
        has_md = any(n.lower().endswith(MD_EXT) for n in names)
        has_asset = any(n.lower() in _ASSET_DIRS and
                        os.path.isdir(os.path.join(full, n)) for n in names)
        if has_md and has_asset:
            scored.append((0, rel))          # 最像文档库根
        elif has_md:
            scored.append((1, rel))
        for n in sorted(names):
            if n.startswith(".") or n in skip:
                continue
            sub = os.path.join(full, n)
            if os.path.isdir(sub):
                walk((rel + "/" + n) if rel else n, depth - 1)

    walk("", 3)
    scored.sort(key=lambda x: (x[0], x[1].count("/")))
    return [rel for _score, rel in scored]


def _has_md(path, depth):
    if depth < 0:
        return False
    try:
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isfile(full) and name.lower().endswith(MD_EXT):
                return True
            if os.path.isdir(full) and not name.startswith(".") and _has_md(full, depth - 1):
                return True
    except OSError:
        pass
    return False


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root or os.getcwd())
    if not os.path.isdir(root):
        raise SystemExit("--root 不是目录: %s" % root)
    CFG.root = root
    CFG.safe = args.safe
    CFG.depth = max(0, args.depth)
    CFG.search = not args.no_search

    httpd, port = bind_server(args.host, args.port)
    banner(args.host, port, CFG)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n收到 Ctrl-C，正在关闭…")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
