#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mdview.py — 零依赖离线 Markdown 预览服务器（只用 Python 标准库）。

用法:
    python3 mdview.py                       # 默认 0.0.0.0:8000，根=当前目录
    python3 mdview.py --port 9000 --root ~/notes
    python3 mdview.py --safe                # 只服务 .md + 图片，其余 404
    python3 mdview.py --no-search           # 关闭全文搜索

设计约束（来自需求评审）:
    * 严格零第三方依赖：只用 stdlib（http.server / socketserver / re / html / urllib.parse / argparse）。
    * 服务端渲染：Markdown -> HTML 在 Python 侧完成，**禁用 JS 也能正常阅读**。
      唯一的 JS 是代码块的复制按钮，由脚本注入（无 JS 时不会出现死按钮）。
    * 默认 0.0.0.0 + 任意文件可读：等同于一个好看一点的静态文件服务器；启动 banner 会
      显式打印真实暴露范围。需要收紧时用 --safe。
    * 路径穿越防护：解决后的路径必须仍在 root 内，否则 403。
    * 虚拟主机名不参与路由；所有 .md 一律渲染成网页。
      `?raw=1` 返回的是**带行锚点的源码视图页（仍是 HTML）**，供搜索跳转到具体行；
      想要磁盘上的原始字节用 `?download=1`（Content-Type: text/markdown）。

SECTION 导航（本文件按功能分块；每块的标题就是唯一标识，可直接搜索）:
    搜 "SECTION 1"   -> 常量与配置        CONSTANTS
    搜 "SECTION 2"   -> 内联 CSS          CSS
    搜 "SECTION 3"   -> HTML 模板         TEMPLATES
    搜 "SECTION 4"   -> 语法高亮器        HIGHLIGHTER
    搜 "SECTION 5"   -> 内联解析          INLINE
    搜 "SECTION 6"   -> 链接/图片重写      URL REWRITE
    搜 "SECTION 7"   -> 块级解析          BLOCKS
    搜 "SECTION 8"   -> 目录索引/搜索页     DIRECTORY & SEARCH
    搜 "SECTION 9"   -> HTTP 处理器       HANDLER
    搜 "SECTION 10"  -> CLI 与启动        CLI

已知行为（写在代码里而不是靠口头约定）:
    * 裸 HTML 全部转义，不透传；链接/图片目标再过一道协议白名单
      （javascript:/data: 一律不产出属性）—— 这两条合起来才封住 .md 的 XSS。
      早期版本只做了前一条，自动链接与 javascript: 仍可注入（已修）。
    * 列表/引用可嵌套；只有带语言标识的围栏代码块才高亮。
    * 单层目录不限制条目数，大目录索引可能较慢。
    * 超过 --max-preview（默认 20 MiB）的文件不再预览，改为下载（对 .md、
      图片、PDF 等一切类型生效）；未超限的文本非 UTF-8 用 errors="replace" 解码。
    * 文件类型三层判定：白名单（源码/配置，不读文件）-> 内置 MIME 表（图片/PDF…）
      -> 内容嗅探兜底（照搬 VS Code 的 oze()：扫前 512 字节的 NUL 字节**对齐**）。
      所以**没登记过的文本文件也能预览**。代价是前 512 字节无 NUL 的二进制
      （纯 ASCII 头的 tar、改名的 PNG）会显示乱码而不是下载。
      真实 Office/ODF 文件不受影响 —— 它们的 ZIP 头在偏移 4-5 就有 NUL。
    * 强制下载时用 filename + filename* 双写给出文件名（RFC 6266/5987）。
    * 隐藏目录（.git / .svn / node_modules 等）不进索引与搜索，但仍可直接按 URL 访问。
    * 只有 .md 被特殊处理；源码/配置类文本按 text/plain; charset=utf-8 发送，
      其余文件按内置 MIME 表处理（表外回落 octet-stream）。
"""

import argparse
import decimal
import html
import os
import posixpath
import re
import socket
import stat
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
# `(?<!\])`：不把「完整式/折叠式引用的后半截」再当简写匹配一遍
# （否则 `![x][r]` 在协议被拒时会渲染成 `![x]` + 一个诡异的空链接）。
_REF_SHORT_RE = re.compile(r"(?<!\])(!?)\[([^\[\]]+)\](?![\(\[(])")
SAFE_EXT = {MD_EXT} | IMAGE_EXT
# 索引与搜索时跳过的目录（一处定义，所有遍历/探测都引用它）
SKIP_DIRS = {".git", ".svn", ".hg", ".idea", ".vscode", "node_modules", "__pycache__",
             ".venv", "venv", ".tox", "dist", "build"}
# 目录下出现这些名字时，该目录更像「文档库根」（用于 --root 建议打分）
ASSET_DIRS = {"media", "images", "image", "img", "assets", "static", "attachments"}
# 渲染结果缓存上限（条）；端口占用时的重试次数
RENDER_CACHE_MAX = 512
PORT_TRIES = 10
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
    # 注意：Chrome 对 `text/csv` 一律下载、不内联显示，且 Content-Disposition: inline
    # 也拦不住（实测：9311 无 disposition -> 下载；9312 inline -> 仍下载；
    # 9313 改 text/plain -> 内联）。所以这里刻意声明为 text/plain —— 内容与字节
    # 完全不变，只是让浏览器老老实实把它显示出来。
    ".csv": "text/plain; charset=utf-8",
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

# 源码与配置类扩展名：一律按 UTF-8 文本发送。
#
# 为什么需要这张表（而不是把一切交给标准库 mimetypes）：
#   * `.py` 等被推断成 `text/x-python`，**不带 charset** -> 浏览器猜编码 -> 中文乱码；
#   * `.ts` 在 mimetypes 里是 `video/mp2t`（MPEG 传输流）-> TypeScript 被当视频；
#   * `.go`/`.rs`/`.ini`/`.log`/`.lua` 等干脆未收录 -> 回落 octet-stream -> 点开就下载。
# 所以这里的判定优先于 mimetypes：命中即按文本发（`.ts` 当 TypeScript 是刻意的）。
TEXT_MIME_DEFAULT = "text/plain; charset=utf-8"
BINARY_MIME = "application/octet-stream"

# 超过这个大小就不再预览，改为下载（0 = 不限制）。
# 20 MiB 与 VS Code 的 LARGE_FILE_SIZE_THRESHOLD 同值：那边超过它就关掉词法高亮，
# 这边超过它就不再把整个文件塞进浏览器。
DEFAULT_MAX_PREVIEW = 20 * 1024 * 1024

# 无扩展名文件的「是否二进制」判定只看开头这么多字节。
# 512 字节来自 VS Code 的实测实现（它也是只看前 512 字节里有没有 NUL）。
# 只看开头必然会漏判（前 512 字节干净、后面藏二进制的文件会被当文本），
# 这是刻意承担的代价——换来的是几乎零成本的判定。
BINARY_SNIFF_BYTES = 512

# 强调配对的定界符上限。配对算法是"每个 opener 向右找最近 closer"，
# 最坏情况平方级：`"***a" * 8000`（31 KB）要 9.4 秒，一个请求就能占满线程。
# 正常文档的定界符远小于这个数，所以超出部分直接当字面量，把最坏情况封顶。
MAX_DELIM_RUNS = 2000

# 块级嵌套（引用/列表）的深度上限。递归下降遇到极深嵌套会打穿 Python 递归栈，
# 表现为 HTTP 500；封顶后超深部分退化为等宽文本块。
MAX_BLOCK_DEPTH = 100
TEXT_EXT = {
    # 脚本与源码
    ".py", ".pyw", ".pyi", ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".cs", ".java", ".kt", ".scala",
    ".go", ".rs", ".ts", ".tsx", ".jsx", ".rb", ".php", ".pl", ".pm", ".lua", ".r",
    ".swift", ".m", ".mm", ".dart", ".ex", ".exs", ".erl", ".hs", ".clj", ".groovy",
    # 配置与数据
    ".ini", ".cfg", ".conf", ".properties", ".env", ".toml", ".yaml", ".yml",
    ".sql", ".graphql", ".proto", ".mk", ".cmake", ".gradle", ".sbt",
    # 包管理与锁文件（前端 / Java / 其他生态）
    #   注意**不要**收 ".lockb" —— bun.lockb 是二进制格式；bun.lock（文本）由 .lock 覆盖
    ".lock", ".sum", ".kts", ".am", ".mf", ".cjs", ".hcl", ".config",
    # autotools / Xcode / Swift / 现代 JS
    #   .in 覆盖 Makefile.in 与 Makefile.am.in；.mod 覆盖 go.mod（有意的取舍：
    #   音频领域的 .mod 会被当文本，但本工具面向代码与文档，go.mod 出现频率高得多）
    ".in", ".ac", ".mod", ".mjs", ".pbxproj", ".resolved", ".user", ".csproj.user",
    # .NET / NuGet 工程文件（都是 XML 文本）
    ".csproj", ".vbproj", ".fsproj", ".vcxproj", ".vcproj", ".xproj",
    ".sln", ".props", ".targets", ".resx", ".nuspec", ".ruleset",
    # 文本类文档与其他
    ".log", ".diff", ".patch", ".rst", ".tex", ".tsv", ".vue", ".svelte", ".txt",
}

# 没有扩展名但明显是文本的常见文件名（比对时去掉前导点、转小写）
TEXT_FILENAMES = {
    "makefile", "gnumakefile", "dockerfile", "containerfile", "vagrantfile",
    "gemfile", "rakefile", "procfile", "jenkinsfile", "readme", "license",
    "licence", "notice", "authors", "changelog", "contributing", "todo",
    "gitignore", "gitattributes", "gitmodules", "dockerignore", "editorconfig",
    "env", "npmrc", "yarnrc", "babelrc", "eslintrc", "prettierrc", "flake8",
    # 无扩展名的 Java 构建文件（Gradle/Maven 生态里很常见）
    "manifest", "maven.config", "jvm.config", "gradlew", "mvnw",
    "settings.gradle", "build.gradle", "gradle.properties",
    # 前端生态里无扩展名的 rc 文件
    "browserslistrc", "stylelintrc", "lintstagedrc", "nvmrc", "huskyrc",
    "swcrc", "commitlintrc", "markdownlintrc", "npmignore", "yarnclean",
    # 其他常见无扩展名文本
    "pipfile", "pipfile.lock", "cmakelists.txt", "meson.build",
    "codeowners", "mailmap", "golangci.yml", "procfile.windows",
}


def _is_textual(path):
    """扩展名或文件名是否属于「源码/配置类文本」。"""
    ext = os.path.splitext(path)[1].lower()
    if ext:
        return ext in TEXT_EXT
    return os.path.basename(path).lstrip(".").lower() in TEXT_FILENAMES


def _is_binary(path, nbytes=BINARY_SNIFF_BYTES):
    """判断是否二进制：看开头 nbytes 字节里的 NUL 字节**对齐方式**。

    规则照搬 VS Code 的 `oze()`（1.141 实测反编译）：
      * 只扫前 512 字节；
      * NUL 只出现在**奇数**偏移 -> UTF-16LE（文本）；
      * NUL 只出现在**偶数**偏移 -> UTF-16BE（文本）；
      * NUL 出现但对不齐 -> 二进制。

    "只看有没有 NUL"太粗：ASCII 为主的 UTF-16 文本（如 `h\x00e\x00l\x00l\x00o`）
    每个字符后都有 NUL，会被误判成二进制。加上对齐判断就能认出这类文本。

    注意它的能力边界（实测）：**CJK 开头的 UTF-16 认不出来** ——
    `中` 是 `2d 4e`、高位不是 NUL，对齐立刻被破坏，VS Code 同样如此。
    所以这条只对"ASCII 为主的 UTF-16"有效。

    另外两个有意的宽松处：
      * GBK 等非 UTF-8 文本不含 NUL，仍判文本（可能显示乱码但不下载）；
      * 前 512 字节无 NUL 的二进制（纯 ASCII 头的 tar、改名的 PNG）判成文本。
    """
    if not _is_regular_file(path):
        # 不能被 open 的东西（FIFO 会永久阻塞）一律当作二进制 -> 走下载分支
        return True
    try:
        with open(path, "rb") as fh:
            head = fh.read(nbytes)
    except OSError:
        return False
    has_zero = False
    utf16le = utf16be = True
    for i, byte in enumerate(head):
        odd = (i % 2 == 1)
        is_zero = (byte == 0)
        if is_zero:
            has_zero = True
        # 奇数位非 NUL 或偶数位是 NUL -> 不符合 UTF-16LE 的排布
        if utf16le and ((odd and not is_zero) or (not odd and is_zero)):
            utf16le = False
        # 奇数位是 NUL 或偶数位非 NUL -> 不符合 UTF-16BE 的排布
        if utf16be and ((odd and is_zero) or (not odd and not is_zero)):
            utf16be = False
        if is_zero and not utf16le and not utf16be:
            break                                    # 两种对齐都破了 -> 二进制
    if not has_zero:
        return False                                 # 一个 NUL 都没有 -> 文本
    return not (utf16le or utf16be)


def resolve_ctype(path, force_download=False):
    """决定响应的 Content-Type。返回 (类型, 是否附加强制下载头)。

    三层，各自管一段（缺一不可）：

      1. **白名单**（`_is_textual`）：源码/配置类扩展名与文件名 -> text/plain。
         它不读文件、零开销，且给出比嗅探更准的类型（`text/plain` 而不是
         猜出来的二进制判定），所以**继续维护它是有价值的**。
      2. **内置 MIME 表**：已知格式的准确类型（图片/PDF/JSON/XML…）。
         它是 PDF 能被内联显示的**唯一**原因 —— PDF 前 512 字节几乎是
         纯 ASCII、没有 NUL，嗅探会把它判成文本。
      3. **内容嗅探**（`_is_binary`，只看开头 512 字节有无 NUL）：
         前两层都没意见时兜底。于是 `weird.random`、`.plist`、任何没列进
         白名单的文本文件都能预览，不必逐个登记。

    已知代价（有意的）：**前 512 字节里没有 NUL 的二进制文件**会被判成文本，
    例如纯 ASCII 头的 `.tar`、改名成 `.bak` 的 PNG、`.docx`/`.xlsx`
    （它们本质是 ZIP，头 512 字节可能全是 ASCII）。这类会显示乱码而不是下载。
    这是"让未知文本自动可预览"必须付的代价，已在测试里显式记录。

    force_download=True 时（超过预览上限，或用户点了下载按钮）**保留上面算出的
    准确类型**，只额外要求强制下载 —— 不把类型退化成 octet-stream。
    """
    ext = os.path.splitext(path)[1].lower()
    if _is_textual(path):
        ctype = MIME.get(ext, TEXT_MIME_DEFAULT)       # 第 1 层：白名单
    elif ext in MIME:
        ctype = MIME[ext]                              # 第 2 层：MIME 表
    elif not _is_binary(path):
        ctype = TEXT_MIME_DEFAULT                      # 第 3 层：嗅探判为文本
    else:
        ctype = BINARY_MIME
    # 需要强制下载时仍保留上面算出的准确类型（不退化成 octet-stream）
    return ctype, bool(force_download)


def _content_disposition(filename):
    """返回可安全写进 HTTP 头的 Content-Disposition 值。

    必须显式给文件名，否则浏览器会自己从 URL 推导，而推导规则会改名字：
    实测 Chrome 把裸 attachment 的 `.gitignore` 存成 `gitignore.txt`
    （点被当成隐藏文件标记去掉，又按类型硬加了 .txt）。

    两个参数都给（RFC 6266 推荐的双写）：
      filename   只能是 latin-1（HTTP 头的限制），非 ASCII 会被替换成下划线；
      filename*  用 RFC 5987 的 UTF-8'' 百分号编码，非 ASCII 名字靠它还原。
    注意**绝不能**把中文直接写进 filename —— 头按 latin-1 编码会抛
    UnicodeEncodeError，整个响应直接挂掉（实测 HTTP 000）。
    """
    # ASCII 回退名：只留字母数字与 . _ -，其余替换成 _
    fallback = []
    for ch in filename:
        if ch.isascii() and (ch.isalnum() or ch in "._-"):
            fallback.append(ch)
        else:
            fallback.append("_")
    fallback = "".join(fallback).strip() or "download"
    # 百分号编码（quote 默认 safe="/"，这里不需要保留斜杠）
    encoded = urllib.parse.quote(filename, safe="")
    return 'attachment; filename="%s"; filename*=UTF-8\'\'%s' % (fallback, encoded)


def _parse_size(text, what="--max-preview"):
    """把 20M / 512K / 2G / 20971520 / 0 解析成字节数；非法则抛 ValueError。"""
    raw = text.strip().lower().replace("_", "")
    if not raw:
        raise ValueError("%s 需要一个大小" % what)
    # 一次匹配「数字 + 可选单位」，单位接受 b/k/kb/kib/m/mb/mib/g/gb/gib
    match = re.match(r"^([0-9]*\.?[0-9]+)\s*(b|k|kb|kib|m|mb|mib|g|gb|gib)?$", raw)
    if not match:
        raise ValueError("%s 无法解析: %s" % (what, text))
    number, unit = match.group(1), match.group(2) or ""
    mult = {"": 1, "b": 1,
            "k": 1024, "kb": 1024, "kib": 1024,
            "m": 1024 ** 2, "mb": 1024 ** 2, "mib": 1024 ** 2,
            "g": 1024 ** 3, "gb": 1024 ** 3, "gib": 1024 ** 3}[unit]
    # 用 Decimal 而不是 float：float 既会把 2**53 以上的整数弄丢精度
    # （9007199254740993 -> ...992），又会对超大输入抛 OverflowError。
    try:
        value = int(decimal.Decimal(number) * mult)
    except (decimal.InvalidOperation, OverflowError, ValueError):
        raise ValueError("%s 无法解析: %s" % (what, text))
    if value < 0:
        raise ValueError("%s 不能为负数: %s" % (what, text))
    if value > (1 << 63):
        # 309 位数字这类输入能算出天文数字，作为"预览上限"没有意义；
        # 明确拒绝比接受一个荒谬值好（早期版本会在这里抛 OverflowError）。
        raise ValueError("%s 数值过大: %s" % (what, text[:32]))
    return value


CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --soft:#f6f8fa;
  --accent:#0969da; --mark:#fff3bf; --markfg:#1f2328;
  --t-kw:#cf222e; --t-str:#0a3069; --t-com:#6e7781; --t-num:#0550ae;
  --t-fn:#8250df; --t-op:#cf222e; --banner:#eaeef2;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --soft:#151b23;
    --accent:#4493f8; --mark:#5c4b00; --markfg:#f0f6fc;
    --t-kw:#ff7b72; --t-str:#a5d6ff; --t-com:#8b949e; --t-num:#79c0ff;
    --t-fn:#d2a8ff; --t-op:#ff7b72; --banner:#1c2128;
  }
}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC",
  "PingFang SC","Microsoft YaHei",Helvetica,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:28px 20px 72px}
a{color:var(--accent);text-decoration:none;overflow-wrap:anywhere}
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
/* 图片放大（服务端把正文图片包成 <a class="zoom">，见 wrap_zoom_images）。
   无 JS 时这层链接就是降级路径：点一下直接打开原图。可点击性必须自己提示，
   否则没人知道图能点 —— 光标变放大镜 + 悬停描边，且描边不参与布局（box-shadow
   而不是 border，否则悬停时整段文字会抖一下）。 */
a.zoom{display:inline-block;cursor:zoom-in;border-radius:6px;text-decoration:none}
a.zoom:hover{text-decoration:none}
a.zoom img{border-radius:6px;transition:box-shadow .15s ease}
a.zoom:hover img{box-shadow:0 0 0 2px var(--accent)}
/* 放大视图：单例 <dialog>，由 JS 创建、showModal() 打开。top layer、::backdrop、
   Esc、背景 inert、隐式 aria-modal 全是浏览器白送的，这里只补视觉。
   modal 的定位显式写出来（不靠 UA 表）：关闭按钮用 position:absolute，它的
   包含块就是这个 dialog 盒 —— 按钮因此永远贴在**图片的右上角**。
   早期版本把按钮写成 position:fixed，它就钉在**视口**右上角：既盖在页面内容
   （裂图时是浏览器画出来的 alt 文字，也就是文件名）上面，又把"点空白处关闭"
   的点击抢走（SELFTEST §27）。
   定位与排版写在**基础规则**里、[open] 只切 display：几何不随可见性开关变化。
   只做入场动画（见下）时这层分离不是必需的，但它是**结构保险** —— 将来谁把出场
   做成过渡，摘掉 [open] 后盒子还会多显示约半程，留在 [open] 里的属性会退回初始值，
   三个子元素按 row + stretch 重排，× 飞到视口右缘、图片名（caption）挤成右侧一列
   （SELFTEST §28）。 */
dialog.zoomdlg{max-width:none;max-height:none;padding:0;border:0;
  position:fixed;inset:0;margin:auto;
  flex-direction:column;align-items:center;gap:10px;
  background:transparent;color:var(--fg);overflow:visible}
dialog.zoomdlg[open]{display:flex}
dialog.zoomdlg::backdrop{background:rgb(0 0 0 / .78)}
/* 图片按视口缩放居中：dvh 处理移动端地址栏，vh 作为不支持 dvh 时的回退 */
dialog.zoomdlg img{display:block;width:auto;height:auto;border-radius:6px;
  max-width:calc(100vw - 2.5rem);max-height:calc(100vh - 5rem);
  max-height:calc(100dvh - 5rem)}
dialog.zoomdlg .zoomcap{margin:0;max-width:70ch;text-align:center;font-size:14px;
  line-height:1.5;color:#fff;text-shadow:0 1px 3px rgb(0 0 0 / .7)}
dialog.zoomdlg .zoomcap:empty{display:none}
/* 关闭按钮贴在 dialog（也就是图片）的右上角。图标是 COPY_JS 里现画的内联 SVG，
   按钮只负责把它摆到正中间（flex 居中）—— 与字体度量彻底脱钩。
   早期这里放的是字体里的 U+00D7：那个字形在 em 盒里**并不居中**，而且各字体偏得
   还不一样（canvas 实测 22px 下 macOS 系统字体要抬 ~2.3px，Arial / Hiragino 几乎
   不用动），写死任何 px 校正值都会在别的平台翻车（SELFTEST §30）。 */
dialog.zoomdlg .zoomclose{position:absolute;top:8px;right:8px;width:34px;height:34px;
  padding:0;border:1px solid rgb(255 255 255 / .35);border-radius:50%;
  background:rgb(0 0 0 / .55);color:#fff;cursor:pointer;
  display:flex;align-items:center;justify-content:center}
dialog.zoomdlg .zoomclose svg{display:block;width:24px;height:24px}
dialog.zoomdlg .zoomclose:hover{background:rgb(0 0 0 / .8)}
dialog.zoomdlg .zoomclose:focus-visible{outline:2px solid #fff;outline-offset:2px}
/* 遮罩自己是 tabindex="-1" 的**焦点落脚点**（打开时把初始焦点从 × 收回来，见 COPY_JS）。
   它是容器不是控件，不该画环 —— 否则 Esc 关过之后再打开，整块遮罩会套一圈焦点框。
   真正的操作对象是 ×，那圈白环在上一条里。 */
dialog.zoomdlg:focus{outline:none}
/* 锁滚动：hidden 负责锁，scrollbar-gutter 负责别让滚动条槽位消失（否则整页右移） */
html.zoomlock{overflow:hidden;scrollbar-gutter:stable}
@media print{dialog.zoomdlg{display:none}}
@media (prefers-reduced-motion: no-preference){
  /* 只做**入场**动画：@starting-style 给首帧起始值，图片与遮罩从透明缩放到原位
     （2024 起 Baseline）。
     **刻意不给出场过渡**：一旦给 dialog 写上 `transition:display … allow-discrete`，
     退场那 150ms 里图片与遮罩在淡出，而 × 与 caption 没有 opacity 过渡，会**原地
     原样亮着**直到 display:none —— 用户看到的就是"关掉之后关闭按钮还停留一下"
     （SELFTEST §29）。退场必须瞬时：摘掉 [open] 就立刻 display:none。 */
  dialog.zoomdlg img{opacity:0;transform:scale(.97);
    transition:opacity .15s ease,transform .15s ease}
  dialog.zoomdlg[open] img{opacity:1;transform:none}
  @starting-style{dialog.zoomdlg[open] img{opacity:0;transform:scale(.97)}}
  dialog.zoomdlg::backdrop{opacity:0;transition:opacity .15s ease}
  dialog.zoomdlg[open]::backdrop{opacity:1}
  @starting-style{dialog.zoomdlg[open]::backdrop{opacity:0}}
}
hr{border:0;border-top:1px solid var(--line);margin:26px 0}
mark{background:var(--mark);color:var(--markfg);border-radius:3px;padding:0 2px}
/* 代码块：顶部条 + 代码区「两段叠放」，顶部条自带上方圆角（对齐 DSH 的 code block） */
.codeblock{position:relative;margin:0 0 16px;background:var(--soft);
  border:1px solid var(--line);border-radius:10px;overflow:hidden}
.codeblock .codebanner{display:flex;align-items:center;justify-content:space-between;
  gap:12px;padding:9px 14px;background:var(--banner,var(--bg2,var(--soft)));
  border-bottom:1px solid var(--line);
  font:11px/18px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.codeblock .codebanner .lang{color:var(--muted)}
.codeblock pre{margin:0;border:0;border-radius:0;background:var(--soft)}
.codeblock pre code{background:none;border:0;padding:0;font-size:.86em}
/* 复制按钮：由 JS 注入到顶部条里，一直显示（点击后短暂变色反馈）。
   无 JS 时顶部条只剩语言名，不会出现点了没反应的死按钮。 */
.copybtn{flex:none;background:none;border:0;padding:2px 4px;margin:0;cursor:pointer;
  color:var(--muted);font:11px/18px inherit}
.copybtn:hover{color:var(--accent)}
.copybtn.done{color:#1a7f37}
.copybtn.bad{color:var(--t-kw)}
@media print{.copybtn{display:none}}
.kw{color:var(--t-kw)} .str{color:var(--t-str)} .com{color:var(--t-com);font-style:italic}
.num{color:var(--t-num)} .fn{color:var(--t-fn)} .op{color:var(--t-op)}
.dirlist{list-style:none;padding:0;margin:0}
.dirlist li{border-bottom:1px solid var(--line);padding:7px 2px;display:flex;
  align-items:baseline;gap:10px}
.dirlist li .nm{flex:1 1 auto;min-width:0;overflow-wrap:anywhere}
.dirlist li .meta{color:var(--muted);font-size:13px;white-space:nowrap}
/* 下载按钮：一直可见但低调，悬停变强调色 */
.dirlist li a.dl{color:var(--muted);font-size:12px;white-space:nowrap;
  border:1px solid var(--line);border-radius:5px;padding:1px 7px;text-decoration:none}
.dirlist li a.dl:hover{color:var(--accent);border-color:var(--accent);text-decoration:none}
.dirlist li.d a{font-weight:600}
.note{background:var(--soft);border:1px solid var(--line);border-radius:8px;
  padding:12px 15px;color:var(--muted);font-size:14px;margin:0 0 18px}
.hit{background:var(--soft);border:1px solid var(--line);border-radius:8px;
  padding:12px 15px;margin:0 0 14px}
.hit .where{font-size:13px;color:var(--muted);margin-bottom:8px}
.hit pre{margin:0;background:transparent;border:none;padding:0;font-size:13px;
  white-space:pre-wrap;overflow-wrap:anywhere}
.hit .ln{color:var(--muted);user-select:none;display:inline-block;min-width:3.4em;text-align:right;margin-right:.9em}
.esc{border-bottom:1px dashed var(--line);padding-bottom:1px}
pre.rawsrc{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.55}
pre.rawsrc .srcline{display:block}
pre.rawsrc .srcline:target{background:var(--mark);color:var(--markfg);
  outline:2px solid var(--accent);border-radius:3px}
/* 搜索跳转的落点不要贴着视口最上沿。没有 JS 时靠这个偏移落地，
   有 JS 时由 scrollIntoView({block:"center"}) 接管为真正居中。 */
pre.rawsrc .srcline{scroll-margin-top:20vh;scroll-margin-bottom:70vh}
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

COPY_JS = """
(function () {
  // 1) 搜索跳转：把目标行滚到视口竖向居中（浏览器默认只把它贴到视口最上沿）
  //    自己算坐标而不用 scrollIntoView：后者在"带 hash 首次加载"时会被浏览器的
  //    原生锚点滚动盖掉，实测仍停在视口上方。
  function centreOnHash() {
    var h = location.hash;
    if (!h || h.length < 2 || h.charAt(1) !== "L") return false;
    var el = document.getElementById(h.slice(1));
    if (!el) return false;
    var rect = el.getBoundingClientRect();
    var y = window.pageYOffset + rect.top + rect.height / 2 - window.innerHeight / 2;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    if (y < 0) y = 0;
    if (y > max) y = max;
    window.scrollTo(0, y);
    history.replaceState(null, "", location.href);       // 标记已居中，避免重复滚
    return true;
  }
  if (centreOnHash()) {
    // 浏览器的锚点滚动可能发生在脚本之后，补滚一次
    setTimeout(centreOnHash, 0);
    window.addEventListener("load", centreOnHash);
  }

  var LABEL = "\u590d\u5236", DONE = "\u5df2\u590d\u5236", FAIL = "\u5931\u8d25";
  function flash(btn, text, cls) {
    btn.textContent = text; btn.classList.remove("done", "bad");
    if (cls) btn.classList.add(cls);
    setTimeout(function () {
      btn.textContent = LABEL; btn.classList.remove("done", "bad");
    }, 1500);
  }
  function fallback(text) {                 // http 下没有 navigator.clipboard
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest ? ev.target.closest(".copybtn") : null;
    if (!btn) return;
    var block = btn.closest(".codeblock");
    var code = block && block.querySelector("pre > code");
    if (!code) return;
    var text = code.innerText;              // 取渲染后的文本，不含按钮自身
    function ok(flag) { flash(btn, flag ? DONE : FAIL, flag ? "done" : "bad"); }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { ok(true); },
        function () { ok(fallback(text)); });
    } else {
      ok(fallback(text));
    }
  });
  document.querySelectorAll(".codeblock").forEach(function (block) {
    var banner = block.querySelector(".codebanner");
    if (!banner) {                        // 兜底：没有顶部条就补一个
      banner = document.createElement("div");
      banner.className = "codebanner";
      block.insertBefore(banner, block.firstChild);
    }
    var btn = document.createElement("button");
    btn.type = "button"; btn.className = "copybtn";
    btn.textContent = LABEL;
    btn.setAttribute("aria-label", "\u590d\u5236\u4ee3\u7801");
    banner.appendChild(btn);              // 放在语言名右侧，与 DSH 一致
  });

  // 2) 图片放大：服务端把正文图片包成了 <a class="zoom" href="原图">（见
  //    wrap_zoom_images），这里接管点击弹一个单例 <dialog>。Esc 关闭、背景
  //    inert、top layer、隐式 aria-modal 都是 showModal() 白送的；焦点归还
  //    浏览器不给，得自己记着还。没有这层脚本时链接照旧打开原图 —— 所以
  //    这里不写死任何 DOM，全部运行时创建。
  var zoom = null, zoomOpener = null;
  function buildZoom() {
    var d = document.createElement("dialog"), big = document.createElement("img");
    var cap = document.createElement("p"), btn = document.createElement("button");
    d.className = "zoomdlg";
    // 遮罩自己是打开时的**焦点落脚点**（见 showModal() 之后那次 focus()）：
    // tabindex="-1" 让它可以被脚本聚焦、又不进 Tab 顺序。
    d.tabIndex = -1;
    big.alt = "";
    cap.className = "zoomcap"; cap.id = "zoomcap";
    btn.type = "button"; btn.className = "zoomclose";
    // 图标用**现画的内联 SVG**，不用字体里的 U+00D7：那个字形在 em 盒里并不居中，
    // 各字体的偏移还不一样（22px 下 macOS 系统字体低 ~2.3px，Arial 几乎为零），
    // 任何写死的校正值都会在别的平台偏。SVG 的墨迹本来就对称于 viewBox 中心，
    // 按钮再用 flex 居中即可；stroke 走 currentColor，强制色彩模式下也不会消失。
    // 两条对角线在 24 格里的墨迹范围 ≈ 10.4px × 10.4px，与原字形（10.1 × 10.5）相仿。
    var NS = "http://www.w3.org/2000/svg";
    var icon = document.createElementNS(NS, "svg");
    var line = document.createElementNS(NS, "path");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-hidden", "true");     // 可访问名由按钮的 aria-label 给
    line.setAttribute("d", "M7.5 7.5 16.5 16.5M16.5 7.5 7.5 16.5");
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "currentColor");
    line.setAttribute("stroke-width", "2");
    icon.appendChild(line);
    btn.appendChild(icon);
    btn.setAttribute("aria-label", "\u5173\u95ed\u653e\u5927\u89c6\u56fe");
    // 不写 autofocus：showModal() 本来就会聚焦 dialog 里第一个可聚焦元素。但打开后的
    // 初始焦点会被下面那次 zoom.focus() 收回遮罩本身 —— 所以"打开"这个动作不画焦点环，
    // CSS 里那圈白色 outline 只服务于**用 Tab 走过来的**键盘用户（SELFTEST §31）。
    d.appendChild(big); d.appendChild(cap); d.appendChild(btn);
    btn.addEventListener("click", function () { d.close(); });
    // 点遮罩空白处关闭：::backdrop 上的点击 target 就是 dialog 自身。
    // 不能用 closest，否则点在图片上也会关掉。
    d.addEventListener("click", function (ev) { if (ev.target === d) d.close(); });
    d.addEventListener("close", function () {          // 清理一律放 close，不放 cancel
      document.documentElement.classList.remove("zoomlock");
      // 焦点要还给**包裹链接**而不是里面的 <img>：img 默认不可聚焦，
      // img.focus() 是空操作（Chrome 实测：activeElement 停在 body）。
      if (zoomOpener && zoomOpener.focus) zoomOpener.focus();
      zoomOpener = null;
    });
    document.body.appendChild(d);
    return d;
  }
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest ? ev.target.closest("a.zoom") : null;
    if (!a) return;
    // 带修饰键或中键的点击是「新标签打开 / 另存为」的用户意图，不许抢
    if (ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var small = a.querySelector("img");
    if (!small) return;
    if (!zoom) zoom = buildZoom();
    if (zoom.open || !zoom.showModal) return;   // 老浏览器：不接管，链接照旧可用
    ev.preventDefault();
    var big = zoom.querySelector("img"), cap = zoom.querySelector(".zoomcap");
    big.src = a.getAttribute("href");           // 与 img 的 src 逐字节同源
    big.alt = small.alt || "";
    cap.textContent = small.alt || "";
    if (cap.textContent) {                      // 有 alt 就用它当遮罩的可访问名
      zoom.setAttribute("aria-labelledby", "zoomcap");
      zoom.removeAttribute("aria-label");
    } else {                                    // 装饰图：退回一个固定名
      zoom.removeAttribute("aria-labelledby");
      zoom.setAttribute("aria-label", "\u56fe\u7247\u653e\u5927");
    }
    zoomOpener = a;                             // 归还焦点要还给链接，见 close
    document.documentElement.classList.add("zoomlock");
    zoom.showModal();
    // showModal() 会把焦点送给 dialog 里第一个可聚焦元素 —— 也就是 ×。上一轮交互
    // 若是键盘（比如刚用 Esc 关过一次），这次**程序化**聚焦就会命中 :focus-visible：
    // 再打开时那颗按钮带着一圈白边，看起来像被"选中"了（SELFTEST §31）。
    // 把初始焦点收回到遮罩自己（buildZoom 里写了 tabindex="-1"）即可：焦点仍在 modal
    // 内、Tab 第一步照样落到 × 上并显示焦点环，但"打开"这个动作本身不再画任何环。
    zoom.focus();
  });
})();
"""



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
        "%s\n</div>\n<script>%s</script>\n</body>\n</html>\n"
    ) % (html.escape(title), CSS, depth_nav, search, nav_right, body, COPY_JS)


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
            href = url_for_rel("/".join(upto), trailing_slash=True)
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

# 声明为「纯文本」的语言：整块素色输出，不做任何 token 着色
PLAIN_LANGS = {"text", "plaintext", "txt", "none", "raw"}

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

# 允许出现在 href/src 里的协议。凡是没列进来的（javascript: / data: / vbscript: …）
# 一律不产生属性 —— 光靠转义挡不住 javascript: 链接（点了就执行）。
SAFE_SCHEMES = frozenset((
    "http", "https", "mailto", "ftp", "ftps", "sftp", "tel", "sms", "news",
    "irc", "ircs", "xmpp", "magnet", "gemini", "gopher",
))
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")


def safe_href(url):
    """把 URL 变成可安全放进 href/src 属性的字符串。

    两层防护：
      1. 协议白名单：javascript:/data:/vbscript: 等一律拒绝（返回 ""）；
      2. 属性转义：引号、尖括号、& 都转义，杜绝属性注入。
    返回空串表示"不要输出这个属性"。
    """
    if url is None:
        return ""
    text = str(url).strip()
    # 去掉控制字符（制表/换行/回车/DEL 等）—— 它们躲过正则后仍会被浏览器当作协议的一部分
    text = "".join(ch for ch in text if ord(ch) >= 0x20 and ch != "\x7f")
    match = _SCHEME_RE.match(text)
    if match:
        if match.group(1).lower() not in SAFE_SCHEMES:
            return ""
    elif text.startswith("//"):
        # 协议相对链接 -> 交给浏览器按当前协议解析，允许
        pass
    return html.escape(text, quote=True)


_AUTOLINK_RE = re.compile(r"<((?:https?|ftp|mailto)://[^\s<>]+|[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>")
_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_ENTITY_RE = re.compile(r"&(#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;|\s+\"([^\"]*)\")?\)")
_LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;|\s+\"([^\"]*)\")?\)")
# 引用式链接与图片共用一张引用表：`![x][ref]` 的 `!` 由第一组捕获。
_REF_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\[([^\]]*)\]")
# 定义里的目标有两种写法：普通 `\S+`，或 CommonMark 的 `<...>`（内部允许空格
# 与括号，按规范不允许换行与裸 `<`）。后者的编码统一交给 _encode_angle_inner。
_REF_DEF_RE = re.compile(
    r"^ {0,3}\[([^\]]+)\]:\s*(<[^<>\n]*>|\S+)"
    r"(?:\s+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?\s*$")
# 尖括号目标内部保留原样的字符：markdown-it（mdurl.encode 的 defaultChars）再加
# `%` —— 既有的 %xx 不能重新编码（keepEscaped），否则又变成双重编码。
# 圆括号**不**保留：区间扫描器靠括号配对找目标结尾，`<>` 里的括号必须先变成
# %28/%29，否则 `](<a)b.md>)` 会在中间那个 ) 处提前收尾。
_ANGLE_SAFE = ";/?:@&=+$,-_.!~*'#%"
_ANGLE_DEST_RE = re.compile(
    r"\]\(<([^<>\x00-\x1f]*)>\s*(\"[^\"]*\"|'[^']*'|\([^)]*\))?\s*\)")


def _encode_angle_inner(inner):
    """`<...>` 目标内部的编码：与 markdown-it 的 mdurl.encode 收敛到同一结果。"""
    return urllib.parse.quote(inner, safe=_ANGLE_SAFE)


def _normalize_angle_dest(text):
    """`<a b.png>` -> `a%20b.png`；不是尖括号形式就原样返回（引用式定义用）。"""
    if len(text) >= 2 and text.startswith("<") and text.endswith(">"):
        return _encode_angle_inner(text[1:-1])
    return text


def _angle_dest_sub(m):
    """把 `](<a b.png> "t")` 规约成 `](a%20b.png "t")`。

    `[^<>\x00-\x1f]` 排除 token 占位符：`<>` 内部出现反斜杠转义的 `<` / `>`
    时（`](<a\\<b.png>)`）这一趟不认，原样交给后面的管线 —— 已知限制，见
    README §9。
    """
    inner, title = m.group(1), m.group(2)
    return "](" + _encode_angle_inner(inner) + (" " + title if title else "") + ")"
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
    """自动链接 <...>。两个分支都必须转义：target 里可以含引号。

    之前 mailto 分支既没转义 href 也没转义文本，http 分支只转义了 href，
    于是 `<a@b.com"onmouseover="x>` 能凭空注入一个事件处理器（已实测触发）。
    """
    target = m.group(1)
    text = html.escape(target, quote=False)
    # `@` 判定之前必须先看有没有 scheme：旧写法无条件补 mailto:，于是
    # `<mailto:a@b.com>` 产出 href="mailto:mailto:a@b.com"（死链）。
    if "@" in target and "://" not in target and not _SCHEME_RE.match(target):
        return '<a href="%s">%s</a>' % (safe_href("mailto:" + target), text)
    return '<a href="%s" rel="noreferrer noopener">%s</a>' % (
        safe_href(target), text)


# 裸 URL（GFM autolink literal）：正文里手写的 http(s):// 直接可点。
# 只认 http/https —— www.example.com 需要猜协议、裸邮件误报率高，都不做。
# 字符类里排除 NUL 与反引号：此刻 token 占位符、行内码占位符、实体占位符
# 都在文本里，URL 绝不允许跨过它们（否则会把占位符吃进 href）。
_BARE_URL_RE = re.compile(r"https?://[^\s<>\x00`]+", re.I)
# GFM 规定：URL 尾部的这些字符归句子，不属于 URL。
_TAIL_PUNCT = ".,:;!?"
# 全角句末标点 —— 这是**刻意偏离 GFM** 的一处：GFM 只认半角标点，于是
# `见 https://e.com/a。结束` 会把「。结束」整段吃进链接（浏览器地址栏里看着像
# 一条超长 URL），而中文技术文档里 URL 后面跟全角句号是常态。
# 只收句末标点，**不收 CJK 汉字**：`https://zh.wikipedia.org/wiki/中文条目`
# 这类 URL 里的汉字不是标点，照旧完整保留。
_TAIL_PUNCT_CJK = "。，、；：！？"
# 结尾的 CJK 汉字串（用于识别「URL 后面还跟着一句中文」）。
_CJK_TAIL_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+$")
# 全角句末标点（判断上面那串汉字左边是不是句子边界）。
_CJK_PUNCT_RE = re.compile(r"[%s]" % re.escape(_TAIL_PUNCT_CJK))
# 尾部的成对引号与右括号同样归句子（括号需配平判定）。
_TAIL_QUOTES = "\"'\u201c\u201d"
# 结尾的 `&name` / `&#38`：它是 HTML 实体的前半段，不能当成普通文本处理。
_AMP_AT_END_RE = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31})?$")
# 引用式定义 `[r]: 目标` 的竖标志（同一行前缀里出现它就说明这个 URL 是定义目标）。
_REF_DEF_MARK_RE = re.compile(r"^\s{0,3}\[[^\]\n]*\]:\s", re.M)


def _trim_bare_url(text, start, end):
    """按 GFM 规则剥掉 URL 尾部的句子标点，返回真正的结束下标。

    括号判定用的是 GFM 的原话："去掉那个尾部 `)`/`]` 之后，剩下的部分里
    配成对的括号仍平衡、且没有多余的 `)`/`]`"。所以 `A_(b)` 保留，`A_(b))`
    去掉一个，`(见 …/a)` 把那个收尾的 `)` 归还给句子。
    顺序有意如此：**先**判实体/括号（它们是"实质内容"），**再**剥标点。
    反例说明为什么不能只剥标点：`https://e.com/a&copy;` 的 `;` 若被当标点剥掉，
    文本就漏出半截实体 `&copy`，页面上显示成 "&copy"。
    """
    while end > start:
        ch = text[end - 1]
        # 全角句末标点如果**不在最末尾**（`https://e.com/a。结束`），下面的标点分支
        # 永远够不到它 —— URL 的字符类是允许 CJK 的，整句都被吃进来了。
        # 所以先做一次"CJK 句末"规约：末尾的汉字只有在它左边紧跟全角句末标点时
        # 才算句子尾巴；`wiki/中文条目` 左边是 `/`，不在其列，照旧保留。
        m = _CJK_TAIL_RE.search(text, start, end)
        if m:
            if m.start() == start:
                # 整段都是汉字且没有左边标点 -> 不是"标点+中文句子"形态，交给下面
                pass
            elif _CJK_PUNCT_RE.match(text, m.start() - 1):
                end = m.start()
                continue
        if ch in ")]":
            n = 0
            for i in range(start, end - 1):
                c = text[i]
                if c == "(":
                    n += 1
                elif c == ")":
                    n -= 1
            # 前面还有没配对的 `(` -> 这个收尾括号是 URL 的一部分（`A_(b)`）；
            # 否则它属于句子（`(见 …/a)`、`A_(b))` 的最后一个）。
            if n <= 0:
                end -= 1
                continue
            break
        # 结尾是 `&name;` 这类完整实体的收尾 `;` -> 前面那个 `&` 是实体开头，
        # 这个分号属于它，停手。
        if ch == ";" and _AMP_AT_END_RE.search(text, start, end - 1):
            break
        # 结尾是 `&` 或 `&amp`（没有分号）-> 也是实体开头，`;` 属于它；
        # 若这里是句末标点 `;`，上面的 `)`/`]` 分支已处理，这里只管停手。
        if "&" in text[start:end] and _AMP_AT_END_RE.search(text, start, end):
            break
        if ch in _TAIL_PUNCT or ch in _TAIL_PUNCT_CJK or ch in _TAIL_QUOTES:
            end -= 1
            continue
        break
    return end


def _link_dest_spans(text):
    """行内链接与图片的**目标区间** [(起点, 终点)]，用于排除自动链接。

    目标里本来就是个 URL（`[t](https://…)`），它是链接目标、不是正文裸 URL。
    这里只做区间计算，不渲染 —— 渲染仍由 scan_inline 统一负责。
    """
    out = []
    if "](" not in text:
        return out                       # 快路径：没有行内链接目标，不必配对扫描
    for _, _, _, dest_end in _scan_link_spans(text):
        # `](` 的 `(` 在标签终点 +1 处，故目标起点是 dest_end - 2；
        # 目标止于 dest_end - 1（最后的 `)`），这里多含一位无妨。
        out.append((dest_end - 2, dest_end))
    return out


def _bare_url_sub(text, protected=None):
    """把正文里的裸 http(s) URL 变成 <a>，返回 [(片段, 是否已渲染), ...]。

    protected 是若干 (start, end) 区间：方括号标签与链接目标。跨进去的 URL
    一律不动 —— 标签里的 URL 若也变成链接会产出 <a> 嵌 <a>，目标里的 URL 本来
    就是链接目标。
    """
    # 只有真的含 `://` 才值得做方括号配对与目标扫描（两者都是整段线性扫描）。
    if "://" not in text:
        return None
    out = []
    pos = 0
    line_start = 0

    def covered(s, e):
        if not protected:
            return False
        for ps, pe in protected:
            if s < pe and e > ps:
                return True
        return False

    for m in _BARE_URL_RE.finditer(text):
        start = m.start()
        end = _trim_bare_url(text, start, m.end())
        if end <= start or covered(start, end):
            continue
        # 引用式定义行里的 URL（`[r]: https://…`）是定义目标。定义通常已在块级
        # 阶段被摘掉，这里是没被摘掉时的兜底。
        # 行首用**前进式**指针维护：若改成每次匹配都 rfind 回退，一行 2 万个 URL
        # 会退化成平方级（实测 1.39s，改后 0.21s，与 S17 的旧链接正则是同一类坑）。
        nl = text.find("\n", line_start, start)
        if nl >= 0:
            line_start = nl + 1
        m2 = _REF_DEF_MARK_RE.match(text, line_start, start)
        if m2:
            continue
        url = text[start:end]
        href = safe_href(url)
        if not href:
            continue                    # 协议被拒：当普通文本，交给外层转义
        out.append((text[pos:start], False))
        out.append(('<a href="%s" rel="noreferrer noopener">%s</a>'
                    % (href, html.escape(url, quote=False)), True))
        pos = end
    if not out:
        return None
    out.append((text[pos:], False))
    return out


def _bracket_pairs(text):
    """单趟 O(n) 用栈配对 [ ]，返回 {开括号下标: 闭括号下标}。

    绝不为每个 `[` 向后扫描找 `]` —— 那是平方级的根源：`"[x](" * 20000`
    （78 KB）在旧的正则实现里要 59 秒，一个请求就能把一个线程打满。
    """
    pairs = {}
    stack = []
    for i, ch in enumerate(text):
        if ch == "[":
            stack.append(i)
        elif ch == "]" and stack:
            pairs[stack.pop()] = i
    return pairs


def _scan_link_spans(text):
    """单趟找出所有「标签](目标)」区间，返回 [(起点, 标签起, 标签止, 目标止)]。

    只认后面紧跟 `(` 的 `]`，因此天然跳过绝大多数方括号噪声；
    目标允许括号配对（`Foo_(bar)` 这类维基链接不会被截断）。
    """
    pairs = _bracket_pairs(text)
    spans = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "[":
            i += 1
            continue
        close = pairs.get(i, -1)
        if close < 0 or close + 1 >= n or text[close + 1] != "(":
            i += 1
            continue
        k, depth = close + 2, 1
        while k < n and depth:
            ch = text[k]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            k += 1
        if depth:
            # 关键：这里必须跳到刚才扫到的位置，不能只 i += 1。
            # 否则同一个"扫到结尾也找不到 )"的失败会对后面每个 `[`
            # 重做一遍，整体仍然是平方级（实测 31 KB 要 8 秒）。
            i = k
            continue
        spans.append((i, i + 1, close, k))
        i = k
    return spans


# title 的四种定界（含实体转义过的引号）。解析与「尾部是否合法」共用同一张表，
# 免得两处判断漂移。
_TITLE_QUOTES = (("\"", "\""), ("'", "'"), ("(", ")"), ("&quot;", "&quot;"))


def _split_link_tail(tail):
    """把「目标 ) 与 ) 之间」的尾巴拆成 (目标, title, 尾部是否合法)。

    目标里允许括号配对；其后可跟 ` "标题" ` / ` '标题' ` / ` (标题)`。

    第三个返回值是 CommonMark 的合法性判定：目标之后只允许空白或一个 title。
    裸空格会把目标截断（`[x](a b.md)` 的目标是 `a`，残留 `b.md)`），VS Code 与
    CommonMark 都会让**整条链接不成立**、按字面文本输出；早期实现把它截成一条
    指向 `/a` 的链接 —— 若恰好存在名为 a 的文件，就是静默链错文件。
    """
    if tail.startswith("<"):
        # 正常路径下 `<...>` 已在 parse_inline 的预处理里被规约掉，这里只是
        # 兜底（例如经引用式定义进来的目标）。
        j = tail.find(">", 1)
        if j > 0 and "\n" not in tail[:j]:
            rest = tail[j + 1:]
            return tail[1:j], _parse_link_title(rest), _tail_is_blank_or_title(rest)
    i, n, depth = 0, len(tail), 0
    while i < n:
        ch = tail[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                break
            depth -= 1
        elif ch.isspace() and depth == 0:
            break
        i += 1
    rest = tail[i:]
    return tail[:i], _parse_link_title(rest), _tail_is_blank_or_title(rest)


def _parse_link_title(tail):
    """从链接尾部解析 title（"…" / '…' / (…)）；解析不出返回空串。"""
    t = tail.strip()
    if len(t) < 2:
        return ""
    for open_q, close_q in _TITLE_QUOTES:
        if t.startswith(open_q) and t.endswith(close_q) and len(t) >= 2 * len(open_q):
            return t[len(open_q):-len(close_q)]
    return ""


def _tail_is_blank_or_title(rest):
    """目标之后的残留是否只是空白或一个合法 title（否则整条链接不成立）。"""
    t = rest.strip()
    if not t:
        return True
    for open_q, close_q in _TITLE_QUOTES:
        if t.startswith(open_q) and t.endswith(close_q) and len(t) >= 2 * len(open_q):
            return True
    return False


_IMG_ALT_ATTR_RE = re.compile(r'<img\b[^>]*?\balt="([^"]*)"[^>]*>')
_ANY_TAG_RE = re.compile(r"<[^>]*>")
# 我们自己生成的三种标记（源文本里的尖括号早已转义成 &lt;，属性值里的
# `<`/`>`/`"` 也都被 quote=True 转义或逐段百分号编码，所以这个模式只可能
# 命中我们自己的输出）
_OWN_TAG_SCAN_RE = re.compile(r"<a\b[^>]*>|</a>|<img\b[^>]*>")
_IMG_SRC_ATTR_RE = re.compile(r'\bsrc="([^"]*)"')


def wrap_zoom_images(html_text):
    """给「不在链接里」的正文图片包一层可放大链接 `<a class="zoom" href="…">`。

    为什么放在 parse_inline 的出口：此刻源文本已全部转义，输出里任何
    `<a` / `</a>` / `<img` 都只可能是我们自己生成的 —— 于是可以线性地数锚点
    深度，只包深度为 0 的图片。行内式与引用式两条路径、以及标题/表格/列表
    等所有上下文自动覆盖；`[![i](p.png)](u)` 这种徽章写法自动跳过，因为
    `<a>` 不能套 `<a>`（浏览器会把外层链接撕成两半，徽章就点不动了）。

    `href` 逐字节复用 `<img>` 自己那个**已完成编码**的 `src`：那条「只解码
    一次、只编码一次」的管线不许被走第二遍，href 与 src 必须永远指向同一个
    字节串（tests_render 的 TestTargetEncoding 钉着这条）。

    这层链接同时是禁用 JS 时的降级路径：点击直接打开原图（同标签）。
    """
    if "<img" not in html_text:
        return html_text
    out, pos, depth = [], 0, 0
    for m in _OWN_TAG_SCAN_RE.finditer(html_text):
        tag = m.group(0)
        if tag.startswith("</a"):
            if depth:
                depth -= 1
        elif tag.startswith("<a"):
            depth += 1
        elif depth == 0:
            src = _IMG_SRC_ATTR_RE.search(tag)
            if src:
                out.append(html_text[pos:m.start()])
                out.append('<a class="zoom" href="%s">' % src.group(1))
                out.append(tag)
                out.append("</a>")
                pos = m.end()
    if not out:
        return html_text
    out.append(html_text[pos:])
    return "".join(out)


def _alt_text(html_label):
    """把标签的**渲染结果**拍成纯文本，用作 `alt` 属性值。

    `alt` 是属性值，而 `render_label()` 返回的是标签内容 —— 可能含
    `<strong>` / `<code>`，嵌套图片时还含我们自己生成的 `<img>`。旧实现把它
    整个塞进 `alt="…"`，而 `html.escape(..., quote=False)` 不转义引号，于是
    `![a" onerror="alert(1)](p.png)` 真的产出可执行的 `onerror` 属性
    （SELFTEST §25）。CommonMark / markdown-it 的 alt 本来就是标签的纯文本
    （`![**粗**](p.png)` -> `alt="粗"`），这里照做。

    剥标签对本函数的输入是安全的：输入只可能是「已转义的源文本 + 我们自己
    生成的标签」——源文本里的 `<` 早已是 `&lt;`，属性值里的 `<`/`>`/`"`/`&`
    要么被 `safe_href` 的 `quote=True` 转义、要么被逐段百分号编码。
    """
    # 嵌套图片按 CommonMark 的规则贡献它自己的 alt 文本
    text = _IMG_ALT_ATTR_RE.sub(r"\1", html_label)
    return html.unescape(_ANY_TAG_RE.sub("", text))


def parse_inline(text, ctx):
    """行内解析：受保护区间（转义/行内码/标签/自动链接/实体）先抽成 token，最后还原。

    顺序至关重要：
      1) 反斜杠转义必须最先 —— 否则 \\` 会被行内码正则当成定界符；
      2) 裸 HTML 标签与自动链接在文本转义之前摘除，避免正则跨标签匹配；
      3) 裸 URL 自动链接放在文本转义之后、强调之前 —— 见附近注释；
      4) 强调解析放在最后，且只吃已转义文本，不会碰到 token。
    """
    tokens = []

    def stash(s):
        tokens.append(s)
        return TOKEN_FMT % (len(tokens) - 1)

    def read_tokens(s):
        """把文本里已 stash 的 token 就地在本地解码出来，返回**纯文本**。

        token 表里混着两类值：
          * 已渲染的 HTML（`<img …>`、`<a …>`，来自嵌套解析）—— 原样返回；
          * 文本（转义后的字符、实体、行内码内容）—— 反转义还原成原始字符。
        这样调用方可以放心地"取出来 -> 自己转义一次"，不会出现 &amp;amp;。

        链接/图片的 URL 与 alt 必须走这里：实体保护发生在链接解析之前，
        直接读 m.group() 会拿到占位符，经 URL 编码后变成 %00MK0%00 写进 href。
        """
        def one(mm):
            idx = int(mm.group(1))
            if not (0 <= idx < len(tokens)):
                return mm.group(0)
            val = tokens[idx]
            if val.startswith("<"):
                return val                      # 已渲染的 HTML
            return html.unescape(val)           # 文本：还原成原始字符
        # 此刻 token 的定界符可能已被换成 _TOKEN_SHIELD（行内码屏蔽阶段），
        # 所以匹配要把两种形式都算上。
        return re.sub(_TOKEN_SHIELD + r"MK(\d+)" + _TOKEN_SHIELD, one,
                      _TOKEN_RE.sub(one, s))

    def read_tokens_markup(s):
        """token 的第二种读法：**原样**取出，不反转义文本 token。

        同一个 token 表有两个消费方向，必须分开读：
          * 属性 / 纯文本（URL、title、alt、说明文字）—— 走 read_tokens 反转义，
            随后由调用方自己转义一次（`safe_href` / `html.escape`）；
          * **标记内容**（链接标签）—— 走这里。文本 token 存的就是已转义形态
            （`_TAG_RE` 存的是 `&lt;script&gt;`），再 `html.unescape` 一遍就等于
            把源文本里的裸 HTML 放回页面：`[<script>alert(1)</script>](u.md)`
            曾经真的产出可执行的 script 标签（SELFTEST §25）。
        两个方向不能合并成一个函数 —— 合并的那一版就是上面这个洞。
        """
        def one(mm):
            idx = int(mm.group(1))
            if not (0 <= idx < len(tokens)):
                return mm.group(0)
            return tokens[idx]
        return re.sub(_TOKEN_SHIELD + r"MK(\d+)" + _TOKEN_SHIELD, one,
                      _TOKEN_RE.sub(one, s))

    # 转义字符：整段做成 token（含已转义的字符）。
    # 早期实现用私有区标记承载、最后用"标记夹一个字符"的正则还原，但
    # html.escape 会把 `>` 变成 `&gt;`（4 个字符），那个正则永远匹配不上，
    # 于是页面上漏出 ⟦EO⟧&gt;⟦EC⟧。做成 token 就绕开了这个前提。
    text = _ESC_RE.sub(
        lambda m: stash('<span class="esc">%s</span>'
                        % html.escape(m.group(1), quote=False)), text)
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
        # 行内码内容可能夹着 token（紧邻的转义 `\`` 就是 token）与本轮的
        # _BT_SHIELD，两者都要在这里就地还原：它们已经离开主文本，
        # 后面那轮"逐个 replace"再也扫不到，否则页面会漏出 MK0 / ⟦BT⟧。
        inner = m.group(2).strip().replace(_BT_SHIELD, "`")
        # 行内码里的转义 token 要变回**字面字符**（不是 <span class="esc">）：
        # 行内码内容是纯文本，塞 HTML 进去会被当成文本显示出来。
        def literal(mm):
            i = int(mm.group(1))
            if not (0 <= i < len(tokens)):
                return mm.group(0)
            val = tokens[i]
            m2 = re.match(r'<span class="esc">(.*?)</span>$', val, re.S)
            return html.unescape(m2.group(1)) if m2 else val
        inner = re.sub(_TOKEN_SHIELD + r"MK(\d+)" + _TOKEN_SHIELD, literal,
                       _TOKEN_RE.sub(literal, inner))
        code_spans.append(html.escape(inner, quote=False))
        return _CODE_OPEN + str(len(code_spans) - 1) + _CODE_CLOSE

    shielded = _CODE_SPAN_RE.sub(stash_code, shielded)
    for _ in range(shield_count["\x00"]):
        shielded = shielded.replace(_TOKEN_SHIELD, "\x00", 1)
    for _ in range(shield_count["`"]):
        shielded = shielded.replace(_BT_SHIELD, "`", 1)
    text = shielded
    # 尖括号目标 `](<a b.png>)`：CommonMark 允许用它包住含空格的路径，而 VS Code
    # 拖拽/粘贴插入的正是这种写法（它把裸空格写进 <>，全程不做百分号编码）。
    # 必须在这一步做：行内码与反斜杠转义此刻已成 token（不会被误改），而裸 HTML
    # 标签还没被 _TAG_RE 摘走 —— `<a b.md>` 恰好长得像一个 <a> 标签，晚一步就只
    # 剩一个占位符（这正是它一直没被支持的原因）。
    text = _ANGLE_DEST_RE.sub(_angle_dest_sub, text)
    text = _TAG_RE.sub(lambda m: stash(html.escape(m.group(0), quote=False)), text)
    text = _AUTOLINK_RE.sub(lambda m: stash(_autolink_sub(m)), text)

    # 裸 URL 自动链接（GFM autolink literal）。位置必须卡在这里，两个方向都不能挪：
    #   * 在 _ENTITY_RE **之前** —— `&` 还是字面 `&`，URL 是"源文本形态"：带查询串的
    #     `?a=1&b=2` 能整段命中（若在实体之后，`&` 已成 token，URL 会被截断）；
    #     随后 html.escape 统一转义成 href="?a=1&amp;b=2"，不会 double-escape。
    #   * 在引用式链接展开（下面的 _REF_DEF_LINK）**之前** —— 那一展开会把
    #     `![a][r]` 变成 `<img src="…">` 写进同一段文本；晚一步的话目标已在属性值
    #     内部，替换会在里面嵌一个 <a>，产出 src="<a href=…>" 这种坏标记。
    # 已渲染的 <a>/<img>、行内码、HTML 标签、尖括号自动链接此刻都是 token 占位符
    # （字符类是 NUL / 反引号），正则碰不到；标签与链接目标区间是禁区。
    if "://" in text:
        protected = list(_bracket_pairs(text).items()) + _link_dest_spans(text)
        batches = _bare_url_sub(text, protected)
        if batches is not None:
            text = "".join(stash(chunk) if rendered else chunk
                           for chunk, rendered in batches)

    text = _ENTITY_RE.sub(lambda m: stash(_entity_sub(m)), text)

    text = html.escape(text, quote=False)

    def render_link(label_raw, dest_raw, title_raw):
        """构造 <a>。转义与协议过滤统一在这里做（B1 的修复点）。"""
        # 先解 token，再解 HTML 实体：写成 &amp; 的 URL 要还原成 &，
        # 之后交给 URL 编码统一处理，否则 &amp; 会被烘成字面量进 href。
        dest = html.unescape(read_tokens(dest_raw))
        # 解出来的 href 只用于协议判定；真正的重写交给 rewrite_target，
        # 它自己决定在哪里解码（先切 ?/#，再解 path 段）。
        try:
            href = urllib.parse.unquote(dest)
        except Exception:
            href = dest
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href):
            target = safe_href(dest)
            extra = ' rel="noreferrer noopener"' if target else ""
        else:
            target = safe_href(ctx.rewrite_target(dest))
            extra = ""
        attr = ' href="%s"' % target if target else ""
        title = html.unescape(read_tokens(title_raw)) if title_raw else ""
        tattr = ' title="%s"' % html.escape(title, quote=True) if title else ""
        return '<a%s%s%s>%s</a>' % (attr, tattr, extra, render_label(label_raw))

    def render_label(plain):
        """标签内的行内解析：先递归处理嵌套的图片/链接，再跑强调。

        必须递归：`[![i](p.png)](u)` 这种徽章写法里，外层链接扫描会一口气
        吃掉整个区间，内层图片的 token 是在**外层**扫描时产生的；
        只对剩下的字面量再扫一遍，图片才能被渲染成 <img> 而不是文本。

        返回值是**标记内容**，所以用 read_tokens_markup 而非 read_tokens：
        标签里写的裸 HTML 必须保持转义形态（它是内容，不是标记）。
        """
        inner = scan_inline(plain)          # 嵌套图片/链接 -> token
        return read_tokens_markup(parse_emphasis(inner))

    def render_image(alt_raw, dest_raw, title_raw):
        """构造 <img>；协议被拒时退化成转义后的字面量。"""
        dest = html.unescape(read_tokens(dest_raw))
        src = safe_href(ctx.rewrite_target(dest))
        if not src:
            return None
        tattr = (' title="%s"' % html.escape(title_raw, quote=True)
                 if title_raw else "")
        # alt 必须是**纯文本**并整段转义：属性值里不允许出现裸引号或标签
        # （标签内容里的 <strong>/<img> 直接塞进来就是属性注入，见 _alt_text）
        return '<img src="%s" alt="%s"%s>' % (
            src, html.escape(_alt_text(render_label(alt_raw)), quote=True), tattr)

    def scan_inline(text):
        """单趟扫描 ![alt](src) 与 [label](dest)，就地替换成 token。

        用 _bracket_pairs/_scan_link_spans 的栈配对代替正则：旧正则在
        一串不匹配的 `[` 上会退化成平方级（78 KB 要 59 秒，一个请求就能
        打满一个线程）。图片与链接一起处理，所以 `[![i](p.png)](u)`
        这种徽章写法里的 <img> 会被正确保留，而不是被转义成文本。
        """
        spans = _scan_link_spans(text)
        if not spans:
            return text
        out = []
        pos = 0
        for start, lab_start, lab_end, dest_end in spans:
            is_img = start > 0 and text[start - 1] == "!"
            cut = start - 1 if is_img else start
            if cut < pos:
                continue
            dest_and_tail = text[lab_end + 2:dest_end - 1]
            dest_raw, title_raw, tail_ok = _split_link_tail(dest_and_tail)
            if not tail_ok:
                # 目标被裸空格截断，或后面跟着解析不出的残留 —— 整条链接不成立，
                # 按字面文本输出（CommonMark 与 VS Code 是同一判定）。
                continue
            label_raw = text[lab_start:lab_end]
            if is_img:
                html_img = render_image(label_raw, dest_raw, title_raw)
                if html_img is None:
                    continue                       # 协议被拒：留给后面的转义
                out.append(text[pos:cut])
                out.append(stash(html_img))
            else:
                out.append(text[pos:cut])
                out.append(stash(render_link(label_raw, dest_raw, title_raw)))
            pos = dest_end
        out.append(text[pos:])
        return "".join(out)

    # 引用式链接：完整式 [t][r] -> 折叠式 [r][] -> 简写 [r]。
    # 位置：必须在 scan_inline **之前**（行内扫描要能看见展开后的标记），
    # 也必须在 render_label / scan_inline 定义**之后** —— 展开时要用它们渲染
    # 标签内容（旧实现把字面 HTML 写回文本，靠外层 parse_emphasis 顺手解析标签，
    # 属性也顺带被解析，见 _REF_DEF_LINK 的注释）。
    text = _REF_DEF_LINK(text, ctx, render_label, stash)
    text = _REF_SHORT_RE.sub(lambda m: _shortcut_ref(m, ctx, render_label, stash),
                             text)

    text = scan_inline(text)

    text = parse_emphasis(text)
    # 先还原 token，再还原行内码与转义（行内码内容不含 token，顺序无关但更直观）
    def resolve_token(mm):
        # 文档里字面写了 \x00MK0\x00 时下标会越界 —— 当普通文本处理，不要 500
        idx = int(mm.group(1))
        if 0 <= idx < len(tokens):
            return tokens[idx]
        return mm.group(0)

    text = _TOKEN_RE.sub(resolve_token, text)
    text = re.sub(re.escape(_CODE_OPEN) + r"(\d+)" + re.escape(_CODE_CLOSE),
                  lambda m: "<code>%s</code>" % code_spans[int(m.group(1))], text)
    # 图片放大的服务端一半：给不在链接里的 <img> 包上 <a class="zoom">。
    # 必须在 token 还原**之后**：引用式与行内式生成的 <a>/<img> 此刻才成为
    # 字面标记，锚点深度才数得准（放在前面只能看到占位符）。
    return wrap_zoom_images(text)


def _ref_link_html(ctx, url, title, label_html):
    """引用式链接的统一渲染：协议白名单 + 属性转义。

    `label_html` 是**已渲染的标签内容**（调用方用行内解析器产出），这里只拼装。
    """
    decoded = urllib.parse.unquote(url)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", decoded):
        href, extra = safe_href(decoded), ' rel="noreferrer noopener"'
    else:
        href, extra = safe_href(ctx.rewrite_target(url)), ""
    attr = ' href="%s"' % href if href else ""
    return '<a%s%s%s>%s</a>' % (
        attr, ' title="%s"' % html.escape(title, quote=True) if title else "",
        extra, label_html)


def _ref_image_html(ctx, url, title, alt_text):
    """引用式图片 `![alt][ref]`（含简写 `![ref]`）。

    协议被拒时返回 None，调用方按原文输出 —— 与行内图片的退化方式一致。
    `alt_text` 是**纯文本**（调用方对行内解析结果再跑一次 _alt_text），与行内式
    同一条口径：`![**粗**][r]` -> `alt="粗"`，与 VS Code 一致。alt 是属性值，
    所以必须 `quote=True` 转义 —— 标签里手写的一个 `"` 否则就能闭合属性、
    注入新属性（SELFTEST §25）。
    """
    decoded = urllib.parse.unquote(url)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", decoded):
        src = safe_href(decoded)
    else:
        src = safe_href(ctx.rewrite_target(url))
    if not src:
        return None
    tattr = ' title="%s"' % html.escape(title, quote=True) if title else ""
    return '<img src="%s" alt="%s"%s>' % (
        src, html.escape(alt_text, quote=True), tattr)


def _REF_DEF_LINK(text, ctx, render_label, stash):
    """[text][ref] 与折叠式 [ref][]；图片形式 ![text][ref] 走同一条路。

    两个参数都是必需的，且都是这条路的**修复点**：
      * `render_label` —— 标签内容走与行内式同一个行内解析器；
      * `stash`        —— 产出的 HTML 立刻变成 token。

    旧实现把 `<a>`/`<img>` **字面**写回文本，于是后面的 parse_emphasis 把它当
    markdown 又解析了一遍：`[r]: _x_.png` 的 href 被插入 `<em>` 变成坏链接，
    `![**粗**][r]` 的 alt 里长出 `<strong>`（SELFTEST §25）。行内式从来没有这个
    问题 —— 它的 <a>/<img> 一直是 token。两条路现在收敛到同一形态。
    """
    def sub(m):
        bang, label, ref = m.group(1), m.group(2), m.group(3)
        key = (ref or label).strip().lower()
        target = ctx.refs.get(key)
        if target is None:
            return m.group(0)
        url, title = target
        if bang:
            img = _ref_image_html(ctx, url, title,
                                  _alt_text(render_label(label)))
            return stash(img) if img is not None else m.group(0)
        return stash(_ref_link_html(ctx, url, title, render_label(label or key)))
    return _REF_LINK_RE.sub(sub, text)


def _shortcut_ref(m, ctx, render_label, stash):
    """简写式引用 [ref] 与图片 ![ref]：只有 refs 里确实定义了才替换。"""
    bang, label = m.group(1), m.group(2)
    target = ctx.refs.get(label.strip().lower())
    if target is None:
        return m.group(0)
    url, title = target
    if bang:
        img = _ref_image_html(ctx, url, title, _alt_text(render_label(label)))
        return stash(img) if img is not None else m.group(0)
    return stash(_ref_link_html(ctx, url, title, render_label(label)))


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

    # 定界符数量封顶：超过就只把前 MAX_DELIM_RUNS 个当定界符，其余留作字面量。
    # 这是为了给平方级的配对算法一个上界（见 MAX_DELIM_RUNS 注释）。
    delims = list(_delim_re().finditer(text))
    if len(delims) > MAX_DELIM_RUNS:
        delims = delims[:MAX_DELIM_RUNS]

    nodes = []          # (kind, sym, pos, run_id)
    pos = 0
    run_id = 0
    for m in delims:
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

    def nearest_closer(start, frm, sym):
        """从 frm 起找最近的、能关闭 sym 的定界符。"""
        for j in range(max(start, frm), len(nodes)):
            kind, other = nodes[j][0], nodes[j][1]
            if kind in ("close", "both") and can_match(sym, other):
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
                if nodes[j][0] in ("close", "both") and can_match(other, nodes[j][1]):
                    return True
        return False

    for i in range(len(nodes) - 1, -1, -1):
        kind, sym, _p, run = nodes[i][:4]
        if kind not in ("open", "both") or i in closer:
            continue
        hit = None
        j = i + 1
        while True:
            j = nearest_closer(i + 1, j, sym)
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


# ============================================================================
# SECTION 6  URL REWRITE
# ============================================================================

def quote_seg(seg):
    return urllib.parse.quote(seg, safe="")


def url_for_rel(rel, trailing_slash=False):
    """站内相对路径 -> 根相对 URL（逐段百分号编码）。全库唯一一处拼装逻辑。"""
    parts = [quote_seg(x) for x in rel.split("/") if x]
    url = "/" + "/".join(parts)
    if not trailing_slash:
        return url
    # 根目录本身就是 "/"，不能再补斜杠 —— 否则拼出 "//"，
    # 而浏览器把 "//" 当作**协议相对 URL**（//host/），会拦成
    # about:blank#blocked。实测：/lvl1/ 页面的"上级目录"链接会变成 //。
    return url if url.endswith("/") else url + "/"


def depth_nav_html(rel):
    """顶栏的当前路径标签；根目录返回空串。"""
    if not rel:
        return ""
    return '<span class="brand">%s</span>' % html.escape(rel)


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

    def rewrite_target(self, href):
        """markdown 目标（括号里的原始文本）-> 根相对 URL。链接与图片共用这一条路。

        三步的顺序不能换，每一步都有具体理由：

        * **先切 `?`/`#`**：文件名里字面的这两个字符，作者按 URL 规矩写成
          `%23`/`%3F`，必须留在 path 里。若先解码再切，`a%23b.md` 会被劈成
          「路径 a + 片段 #b.md」，含这两个字符的文件永远链不到。
          VS Code 1.141 的预览同序：`Uri.parse` 先按 `[^?#]*` 切分，再对每段
          percent-decode。
        * **只解 path 段一次**：作者写的 `%xx` 解成它代表的那个字符。
        * **只编码一次**：`_url_for` 里的 `quote_seg_path` 把结果重新编码。
          解一次 + 编一次是稳定往返（`%20` 仍是 `%20`）；多编一次会把 `%`
          变成 `%25`（`%20` -> `%2520`，指向不存在的路径）—— 这正是本节要
          杜绝的双重编码，与 B3（`Location` 头不许双重编码）是同一条规矩。

        于是链接与图片语义相同：`%20` 表示空格（`a%20b.png` 命中磁盘上的
        `a b.png`）；文件名里字面的 `%` 要写 `%25`（`a%2520b.png` 命中
        `a%20b.png`）。query 与 fragment 原样拼回，不参与编码。

        链接保留 `.md` 后缀（URL 与磁盘一致）：服务端对 `/x.md` 渲染 HTML、
        对 `/x.md?raw=1` 返回原文，所以刷新、收藏、分享链接都不会 404。
        """
        # 协议判定必须用**解码后**的串，否则 `%6a%61vascript:` 这类变体会绕过
        # B1 的 scheme 检查（`safe_href` 另有一层白名单兜底）。
        try:
            decoded = urllib.parse.unquote(href)
        except Exception:
            decoded = href
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", decoded):
            return href
        if decoded.startswith("#"):
            return href
        target, query, frag = _split_target(href)
        try:
            target = urllib.parse.unquote(target)
        except Exception:
            pass
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
    # 分隔行必须自带竖线。否则「文字 | 文字」+「---」会被当成表格，而
    # README/advanced.md 都写明 `---` 一律是分隔线。单列写法的 `|---|`
    # 仍然有竖线，不受影响。
    if "|" not in lines[i + 1]:
        return False
    return len(split_table_row(lines[i])) >= 1


def expand_tabs(s):
    return s.replace("\t", "    ")


def indent_of(s):
    return len(s) - len(s.lstrip(" "))


def render_markdown(text, rel_path=""):
    """入口：Markdown 文本 -> HTML 片段。"""
    # NUL 在 HTML 里是非法字符，且是内部 token 的定界符 —— 先清掉
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    refs, kept = {}, []
    in_fence = None
    for line in lines:
        # 围栏代码块里的内容一律不解析（README 明确承诺），包括 [r]: url 这种
        # 看起来像引用定义的行 —— 否则它既从代码块里消失，又变成全局引用。
        fm = RE_FENCE.match(line)
        if fm:
            marker = fm.group(2)[0]
            if in_fence is None:
                in_fence = marker
            elif marker == in_fence:
                in_fence = None
            kept.append(line)
            continue
        if in_fence is not None:
            kept.append(line)
            continue
        m = _REF_DEF_RE.match(line)
        if m and "|" not in line and not RE_ULIST.match(line):
            refs.setdefault(m.group(1).strip().lower(),
                            (_normalize_angle_dest(m.group(2)),
                             m.group(3) or m.group(4) or m.group(5) or ""))
            kept.append("")
        else:
            kept.append(line)
    ctx = RenderContext(rel_path, refs, CFG.root if CFG.root else None)
    ctx.slug_counts = {}
    try:
        return render_blocks(kept, ctx)
    except RecursionError:
        # 双保险：即使深度上限失效（比如将来的新递归路径），也不要 500
        return ('<p class="note">这篇文档的嵌套层数超出渲染器上限，'
                '已按纯文本显示。</p>\n<pre>%s</pre>'
                % html.escape(text[:200000], quote=False))


def render_blocks(lines, ctx, depth=0):
    """块级解析。depth 用于限制嵌套深度。

    引用与列表是递归下降的，`">" * 1000` 这种输入会直接把 Python 递归栈打穿
    （实测 800 层 OK、1000 层 RecursionError -> HTTP 500）。超过上限就
    原样输出剩余内容，保证任何输入都能得到一个页面。
    """
    if depth > MAX_BLOCK_DEPTH:
        return "<pre>%s</pre>" % html.escape("\n".join(lines)[:200000], quote=False)
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
            # 语法高亮只给「带语言标识」的围栏（决定 5）：
            # 不写语言、或写成 text/plaintext，都输出素色代码块。
            if lang and lang not in PLAIN_LANGS:
                body = highlight(code, info)
            else:
                body = html.escape(code, quote=False)
            # 顶部条只在有语言标识时渲染（视觉上语言条与代码区「两段叠放」）。
            # 无语言的块不渲染空条，避免禁用 JS 时多出一条空白带；
            # 需要复制按钮时由 JS 自行补一条（见 COPY_JS 的兜底分支）。
            banner = ('<div class="codebanner"><span class="lang">%s</span></div>'
                      % html.escape(label)) if label else ''
            out.append('<div class="codeblock">%s<pre><code%s>%s</code></pre></div>'
                       % (banner, cls, body))
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
            out.append("<blockquote>\n%s\n</blockquote>"
                           % render_blocks(buf, ctx, depth + 1))
            continue

        # --- 列表 -------------------------------------------------------
        if RE_ULIST.match(line) or RE_OLIST.match(line):
            html_list, i = _render_list(lines, i, ctx, depth)
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
    # 用"已用 id 集合"判重，后缀从 1 开始试最小可用值。
    # 只数当前 slug 的出现次数会撞车：`## a` / `## a-1` / `## a` 会生成
    # a、a-1、a-1；而把计数带过去又会跳过 -1。
    if not hasattr(ctx, "slug_used"):
        ctx.slug_used = set()
    anchor = slug
    n = 1
    while anchor in ctx.slug_used:
        anchor = "%s-%d" % (slug, n)
        n += 1
    ctx.slug_used.add(anchor)
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


def _render_list(lines, start, ctx, depth=0):
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
        inner = render_blocks(body_lines, ctx, depth + 1)
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
# ============================================================================
# SECTION 8  DIRECTORY & SEARCH
# ============================================================================


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
        href = url_for_rel("/".join(([rel_dir] if rel_dir else []) + [name]))
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
        # 文件行额外给一个下载按钮：?download=1 由服务端强制发附件头，
        # 所以对任何类型都有效（不依赖 HTML5 download 属性的浏览器差异）。
        dl = ("" if is_dir else
              '<a class="dl" href="%s?download=1" title="下载 %s" '
              'aria-label="下载 %s">\u2b07 下载</a>' % (
                  html.escape(href, quote=True),
                  html.escape(name, quote=True), html.escape(name, quote=True)))
        rows.append('<li class="%s"><span class="nm">%s <a href="%s">%s</a></span>'
                    '<span class="meta">%s</span>%s</li>' % (
                        cls, icon, html.escape(href, quote=True),
                        html.escape(name), meta, dl))
    return '<ul class="dirlist">\n%s\n</ul>' % "\n".join(rows)


def iter_markdown(abs_root):
    for dirpath, dirnames, filenames in os.walk(abs_root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.lower().endswith(MD_EXT):
                yield os.path.join(dirpath, fn)


def search_markdown(abs_root, query, cap=MD_SEARCH_CAP, context=SEARCH_CONTEXT):
    """全文搜索。

    返回 (body_hits, name_hits, scanned, truncated)：
      body_hits: [(rel, lineno, [(行号, 文本, 是否命中)])]  —— 正文逐行命中
      name_hits: [rel]                                     —— 仅文件名命中

    两栏是**并集**关系：名字里含关键词但正文一次都没出现的文件也会列出来
    （早先的实现只从正文命中里筛文件名，这类文件会整个消失）。
    """
    needle = query.lower()
    body_hits, name_hits = [], []
    scanned = 0
    truncated = False
    for path in iter_markdown(abs_root):
        if len(body_hits) >= cap:
            truncated = True
            break
        # 与预览上限一致：超大文件不进搜索（否则一个小请求就能把整个大文件
        # 读进内存，内存放大到"最大的那个 .md"）。非常规文件同样跳过。
        if not _is_regular_file(path):
            continue
        if CFG.max_preview:
            try:
                if os.path.getsize(path) > CFG.max_preview:
                    continue
            except OSError:
                continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().split("\n")
        except OSError:
            continue
        scanned += 1
        rel = os.path.relpath(path, abs_root).replace(os.sep, "/")
        if needle in posixpath.basename(rel).lower():
            name_hits.append(rel)
        for idx, line in enumerate(lines):
            if needle in line.lower():
                lo = max(0, idx - context)
                hi = min(len(lines), idx + context + 1)
                block = [(k + 1, lines[k], needle in lines[k].lower()) for k in range(lo, hi)]
                body_hits.append((rel, idx + 1, block))
                if len(body_hits) >= cap:
                    truncated = True
                    break
    return body_hits, name_hits, scanned, truncated


def render_search_page(query, body_hits, name_hits, scanned, truncated):
    if not query:
        body = ('<h1>搜索</h1>\n<p class="note">输入关键词后在全部 Markdown 文件里做'
                '大小写不敏感的子串匹配；文件名命中与正文命中分两块展示（取并集，'
                '只命中文件名的文件也会列出）。</p>')
        return _page("搜索", body)

    html_parts = ["<h1>搜索：%s</h1>" % html.escape(query)]
    html_parts.append('<p class="note">正文命中 %d 处，文件名命中 %d 个；扫描了 %d 个 '
                      'Markdown 文件。%s</p>' % (
                          len(body_hits), len(name_hits), scanned,
                          "结果已达上限，请细化关键词。" if truncated else ""))

    def hit_block(rel, lineno, lines, show_ctx=True):
        # 行号锚点在源码视图里；?raw=1 的每一行都有 id="L<n>"
        href = url_for_rel(rel) + "?raw=1"
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

    def name_block(rel):
        return ('<div class="hit"><div class="where">📝 <a href="%s">%s</a>'
                '（仅文件名命中）</div></div>'
                % (html.escape(url_for_rel(rel), quote=True), html.escape(rel)))

    if name_hits:
        html_parts.append("<h2>文件名命中（%d）</h2>" % len(name_hits))
        for rel in name_hits[:60]:
            html_parts.append(name_block(rel))
    if body_hits:
        html_parts.append("<h2>正文命中（%d）</h2>" % len(body_hits))
        for rel, lineno, lines in body_hits:
            html_parts.append(hit_block(rel, lineno, lines))
    if not body_hits and not name_hits:
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
        self.search = True
        self.max_preview = DEFAULT_MAX_PREVIEW   # 0 = 不限制


CFG = Config()
_RENDER_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _is_regular_file(path):
    """只接受常规文件。

    FIFO / 字符设备 / 块设备 / 套接字一律拒绝：
      * 对 FIFO 执行 open(path, "rb") 会**阻塞到有写者为止** —— 每个请求
        永久吃掉一个线程（ThreadingHTTPServer 每连接一线程），实测确认；
      * /dev/zero 这类设备 os.path.getsize() 返回 0，却会无限吐数据，
        Content-Length 与实际字节数不符（协议破坏）。
    """
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False


def _inside(root, path):
    """path 是否就是 root 或位于 root 之内（两者都应为已 normpath 的绝对路径）。"""
    if path == root:
        return True
    return path.startswith(root.rstrip(os.sep) + os.sep)


def _resolve(abs_root, url_path):
    """URL 路径 -> 绝对路径。

    两层夹紧：
      1. 字符串层：posixpath.normpath 消掉 ../ 与 //，结果必须落在 root 内；
      2. **真实路径层**：对已存在的路径做 realpath，解析符号链接后仍必须在
         root 内 —— 否则 root 内一个指向 /etc/passwd 的符号链接就能把整个
         文件系统读出去（实测确认过）。realpath 对不存在的路径也安全（返回
         其父目录解析后的路径），所以 404 分支不受影响。
    """
    rel = urllib.parse.unquote(url_path)
    if "\x00" in rel:
        return None, ""
    rel = rel.replace("\\", "/")
    rel = posixpath.normpath("/" + rel).lstrip("/")
    if rel in (".", "/"):
        rel = ""
    root = os.path.normpath(abs_root)
    abs_path = os.path.normpath(os.path.join(root, rel.replace("/", os.sep)))
    if not _inside(root, abs_path):
        return None, rel
    # 真实路径校验（符号链接）
    try:
        real_root = os.path.realpath(root)
        real_path = os.path.realpath(abs_path)
    except OSError:
        return None, rel
    if not _inside(real_root, real_path):
        return None, rel
    return abs_path, rel


class Handler(BaseHTTPRequestHandler):
    server_version = "mdview/" + __version__
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def handle_one_request(self):
        """包一层：客户端中途断开时不要再往 stderr 刷整段回溯。

        标准库只捕 TimeoutError，**keep-alive 期间的下一次 readline** 遇到
        ECONNRESET / EPIPE 会直接冒泡给 socketserver.handle_error，打印一大段
        traceback。实测三种断开方式（下载中途 abort、写响应时 RST、响应后
        空闲时 RST）各 3/3 次都会刷屏。正常路径原样交回父类，不复制它的逻辑。
        """
        try:
            BaseHTTPRequestHandler.handle_one_request(self)
        except (ConnectionResetError, BrokenPipeError):
            self.close_connection = True

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

    @staticmethod
    def _too_big(path):
        """超过 --max-preview 上限则不再预览（默认 20M；0 = 不限制）。"""
        if not CFG.max_preview:
            return False
        try:
            return os.path.getsize(path) > CFG.max_preview
        except OSError:
            return False

    def _send_file(self, path, force_download=False):
        # 先判类型：FIFO/设备文件绝不能用 open() 碰（会永久阻塞）
        if not _is_regular_file(path):
            self._send(HTTPStatus.NOT_FOUND,
                       _error_page("404", "不是常规文件（FIFO/设备/目录）"))
            return
        try:
            size = os.path.getsize(path)
            fh = open(path, "rb")
        except OSError:
            self._send(HTTPStatus.NOT_FOUND, _error_page("404", "文件不存在"))
            return
        # 超过预览上限 -> 一律改为下载（对 .md、图片、PDF 同样生效）
        download = force_download or self._too_big(path)
        ctype, download = resolve_ctype(path, force_download=download)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        if download:
            self.send_header("Content-Disposition",
                             _content_disposition(os.path.basename(path)))
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
                self._send(HTTPStatus.OK, render_search_page("", [], [], 0, False))
                return
            body_hits, name_hits, scanned, truncated = search_markdown(CFG.root, query)
            self._send(HTTPStatus.OK,
                       render_search_page(query, body_hits, name_hits, scanned, truncated))
            return

        if os.path.isdir(abs_path):
            if not path.endswith("/") and rel:
                # 必须用已解码的 rel 重新编码：path 来自 urlsplit，本身已是
                # 百分号编码，再 quote 一次会把 % 编成 %25（双重编码 ->
                # Location 指向不存在的路径 -> 跟随后 404）。
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                self.send_header("Location", url_for_rel(rel, trailing_slash=True))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._send(HTTPStatus.OK, self._dir_page(abs_path, rel))
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
        # ?download=1：用户显式要求下载。.md 也直接发原始字节，不渲染成页面。
        want_download = (qs.get("download") or ["0"])[0] not in ("0", "", "false", "no")
        if want_download:
            self._send_file(abs_path, force_download=True)
            return
        # 超过预览上限：渲染视图与源码视图**都**改为下载，不留绕过的口子
        if self._too_big(abs_path):
            self._send_file(abs_path)
            return
        if ext == MD_EXT and not raw:
            status, body = self._markdown_page(abs_path, rel)
            self._send(status, body)
            return
        if ext == MD_EXT and raw:
            status, body = self._raw_page(abs_path, rel)
            self._send(status, body)
            return
        self._send_file(abs_path)

    def _dir_page(self, abs_dir, rel):
        """目录页：分层浏览 —— 列出当前层的目录与文件。"""
        return self._list_view(abs_dir, rel)

    @staticmethod
    def _parent_link(rel):
        """『../ 上级目录』链接；已在根目录时返回空串。"""
        if not rel:
            return ""
        parent = "/".join(rel.split("/")[:-1])
        return '<p><a href="%s">../ 上级目录</a></p>' % url_for_rel(parent, trailing_slash=True)

    def _list_view(self, abs_dir, rel):
        head = [x for x in (_crumbs(rel) if rel else "", self._parent_link(rel)) if x]
        body = "\n".join(head) + render_dir_listing(abs_dir, rel)
        return _page(self._index_title(rel), body,
                     show_search=CFG.search, depth_nav=depth_nav_html(rel))

    @staticmethod
    def _index_title(rel):
        return "索引 " + ("/" + rel if rel else "/")

    def _raw_page(self, abs_path, rel):
        """?raw=1：源码视图，**每一行都带 id="L<n>"**。

        搜索结果是 ...?raw=1#L51 形式，点击能精确落到那一行；渲染视图只有
        标题锚点，没法给任意行挂号，所以把「按行跳转」交给源码视图。
        """
        text = self._read_text(abs_path)
        if text is None:
            # 返回而不是自己发：调用方统一发响应，避免"一次请求写多个响应"
            return HTTPStatus.NOT_FOUND, _error_page("404", "无法读取文件", rel)
        raw_url = url_for_rel(rel) + "?raw=1"
        rows = []
        for n, line in enumerate(text.split("\n"), 1):
            safe = html.escape(line, quote=False)
            rows.append('<span class="srcline" id="L%d">%s</span>' % (n, safe))
        body = (_crumbs(rel) + '\n<p class="note">源码视图（每行带锚点，可从搜索直接跳转）。'
                '<a href="%s">看渲染结果</a></p>\n<pre class="rawsrc">%s</pre>'
                % (html.escape(url_for_rel(rel), quote=True), "\n".join(rows)))
        return HTTPStatus.OK, _page(
            posixpath.basename(rel) + "（源码）", body,
            nav_right='<a class="btn" href="%s">渲染</a>'
            % html.escape(url_for_rel(rel), quote=True),
            show_search=CFG.search, depth_nav=depth_nav_html(rel))

    @staticmethod
    def _read_text(abs_path):
        """读文本；解码失败与非 UTF-8 都退化为 errors=replace，绝不 500。"""
        if not _is_regular_file(abs_path):
            return None
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None

    def _markdown_page(self, abs_path, rel):
        st = os.stat(abs_path)
        key = (abs_path, st.st_mtime_ns, st.st_size)
        with _CACHE_LOCK:
            cached = _RENDER_CACHE.get(key)
        if cached is None:
            text = self._read_text(abs_path)
            if text is None:
                return HTTPStatus.NOT_FOUND, _error_page("404", "无法读取文件", rel)
            cached = render_markdown(text, rel)
            with _CACHE_LOCK:
                if len(_RENDER_CACHE) > RENDER_CACHE_MAX:
                    _RENDER_CACHE.clear()
                _RENDER_CACHE[key] = cached
        title = posixpath.basename(rel)
        # 用已解码的 rel 重新编码（不能拿 self.path 再 quote 一次 —— 那是双重编码）
        raw_link = ('<a class="btn" href="%s?raw=1" title="查看原始 Markdown">源</a>'
                    % html.escape(url_for_rel(rel), quote=True))
        body = _crumbs(rel) + "\n" + cached
        return HTTPStatus.OK, _page(title, body, nav_right=raw_link,
                                    show_search=CFG.search,
                                    depth_nav=depth_nav_html(rel))


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


def bind_server(host, port, tries=PORT_TRIES):
    last = None
    for offset in range(tries):
        p = port + offset
        try:
            httpd = ThreadingHTTPServer((host, p), Handler)
            httpd.daemon_threads = True
            # socketserver 默认 backlog 只有 5：浏览器一个页面就会并发 6 个连接，
            # 实测 30 并发里有 9 个被内核直接拒连（ECONNREFUSED）。
            httpd.request_queue_size = 128
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
    p.add_argument("--port-tries", type=int, default=PORT_TRIES, metavar="N",
                   help="端口占用时向后尝试几个（默认 %d）" % PORT_TRIES)
    p.add_argument("--safe", action="store_true",
                   help="只服务 .md 与图片（png/jpg/gif/svg/webp/bmp/ico/avif），其余 404")
    p.add_argument("--max-preview", metavar="SIZE", default=None,
                   help="超过该大小的文件不再预览、改为下载（默认 20M；支持 512K/20M/2G；0=不限制）")
    p.add_argument("--no-search", action="store_true", help="关闭全文搜索页")
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
    print(" 目录索引   : 分层浏览（首页只列当前层）")
    print(" 预览上限   : %s" % ("不限制" if not cfg.max_preview
                                else "%s（超过则改为下载）" % _fmt_size(cfg.max_preview)))
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


def _docs_root_candidates(root):
    """返回候选的文档库根（相对路径），按「像文档库」的程度排序。"""
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
        has_asset = any(n.lower() in ASSET_DIRS and
                        os.path.isdir(os.path.join(full, n)) for n in names)
        if has_md and has_asset:
            scored.append((0, rel))          # 最像文档库根
        elif has_md:
            scored.append((1, rel))
        for n in sorted(names):
            if n.startswith(".") or n in SKIP_DIRS:
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
    if args.max_preview is not None:
        try:
            CFG.max_preview = _parse_size(args.max_preview)
        except ValueError as exc:
            raise SystemExit("参数错误: %s" % exc)
    CFG.root = root
    CFG.safe = args.safe
    CFG.search = not args.no_search

    httpd, port = bind_server(args.host, args.port, max(1, args.port_tries))
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
