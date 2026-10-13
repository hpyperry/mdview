import argparse
import bisect
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
MD_EXT = ".md"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".avif"}
_REF_SHORT_RE = re.compile(r"(?<!\])(!?)\[([^\[\]]+)\](?![\(\[(])")
SAFE_EXT = {MD_EXT} | IMAGE_EXT
SKIP_DIRS = {".git", ".svn", ".hg", ".idea", ".vscode", "node_modules", "__pycache__",
             ".venv", "venv", ".tox", "dist", "build"}
ASSET_DIRS = {"media", "images", "image", "img", "assets", "static", "attachments"}
RENDER_CACHE_MAX = 512
PORT_TRIES = 10
MD_SEARCH_CAP = 400
SEARCH_CONTEXT = 2
MIME = {
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
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
TEXT_MIME_DEFAULT = "text/plain; charset=utf-8"
BINARY_MIME = "application/octet-stream"
DEFAULT_MAX_PREVIEW = 20 * 1024 * 1024
BINARY_SNIFF_BYTES = 512
MAX_DELIM_RUNS = 2000
MAX_BLOCK_DEPTH = 100
TEXT_EXT = {
    ".py", ".pyw", ".pyi", ".sh", ".bash", ".zsh", ".fish", ".bat", ".cmd", ".ps1",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".cs", ".java", ".kt", ".scala",
    ".go", ".rs", ".ts", ".tsx", ".jsx", ".rb", ".php", ".pl", ".pm", ".lua", ".r",
    ".swift", ".m", ".mm", ".dart", ".ex", ".exs", ".erl", ".hs", ".clj", ".groovy",
    ".ini", ".cfg", ".conf", ".properties", ".env", ".toml", ".yaml", ".yml",
    ".sql", ".graphql", ".proto", ".mk", ".cmake", ".gradle", ".sbt",
    ".lock", ".sum", ".kts", ".am", ".mf", ".cjs", ".hcl", ".config",
    ".in", ".ac", ".mod", ".mjs", ".pbxproj", ".resolved", ".user", ".csproj.user",
    ".csproj", ".vbproj", ".fsproj", ".vcxproj", ".vcproj", ".xproj",
    ".sln", ".props", ".targets", ".resx", ".nuspec", ".ruleset",
    ".log", ".diff", ".patch", ".rst", ".tex", ".tsv", ".vue", ".svelte", ".txt",
}
TEXT_FILENAMES = {
    "makefile", "gnumakefile", "dockerfile", "containerfile", "vagrantfile",
    "gemfile", "rakefile", "procfile", "jenkinsfile", "readme", "license",
    "licence", "notice", "authors", "changelog", "contributing", "todo",
    "gitignore", "gitattributes", "gitmodules", "dockerignore", "editorconfig",
    "env", "npmrc", "yarnrc", "babelrc", "eslintrc", "prettierrc", "flake8",
    "manifest", "maven.config", "jvm.config", "gradlew", "mvnw",
    "settings.gradle", "build.gradle", "gradle.properties",
    "browserslistrc", "stylelintrc", "lintstagedrc", "nvmrc", "huskyrc",
    "swcrc", "commitlintrc", "markdownlintrc", "npmignore", "yarnclean",
    "pipfile", "pipfile.lock", "cmakelists.txt", "meson.build",
    "codeowners", "mailmap", "golangci.yml", "procfile.windows",
}
def _is_textual(path):
    ext = os.path.splitext(path)[1].lower()
    if ext:
        return ext in TEXT_EXT
    return os.path.basename(path).lstrip(".").lower() in TEXT_FILENAMES
def _is_binary(path, nbytes=BINARY_SNIFF_BYTES):
    if not _is_regular_file(path):
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
        if utf16le and ((odd and not is_zero) or (not odd and is_zero)):
            utf16le = False
        if utf16be and ((odd and is_zero) or (not odd and not is_zero)):
            utf16be = False
        if is_zero and not utf16le and not utf16be:
            break
    if not has_zero:
        return False
    return not (utf16le or utf16be)
def resolve_ctype(path, force_download=False):
    ext = os.path.splitext(path)[1].lower()
    if _is_textual(path):
        ctype = MIME.get(ext, TEXT_MIME_DEFAULT)
    elif ext in MIME:
        ctype = MIME[ext]
    elif not _is_binary(path):
        ctype = TEXT_MIME_DEFAULT
    else:
        ctype = BINARY_MIME
    return ctype, bool(force_download)
def _content_disposition(filename):
    fallback = []
    for ch in filename:
        if ch.isascii() and (ch.isalnum() or ch in "._-"):
            fallback.append(ch)
        else:
            fallback.append("_")
    fallback = "".join(fallback).strip() or "download"
    encoded = urllib.parse.quote(filename, safe="")
    return 'attachment; filename="%s"; filename*=UTF-8\'\'%s' % (fallback, encoded)
def _parse_size(text, what="--max-preview"):
    raw = text.strip().lower().replace("_", "")
    if not raw:
        raise ValueError("%s 需要一个大小" % what)
    match = re.match(r"^([0-9]*\.?[0-9]+)\s*(b|k|kb|kib|m|mb|mib|g|gb|gib)?$", raw)
    if not match:
        raise ValueError("%s 无法解析: %s" % (what, text))
    number, unit = match.group(1), match.group(2) or ""
    mult = {"": 1, "b": 1,
            "k": 1024, "kb": 1024, "kib": 1024,
            "m": 1024 ** 2, "mb": 1024 ** 2, "mib": 1024 ** 2,
            "g": 1024 ** 3, "gb": 1024 ** 3, "gib": 1024 ** 3}[unit]
    try:
        value = int(decimal.Decimal(number) * mult)
    except (decimal.InvalidOperation, OverflowError, ValueError):
        raise ValueError("%s 无法解析: %s" % (what, text))
    if value < 0:
        raise ValueError("%s 不能为负数: %s" % (what, text))
    if value > (1 << 63):
        raise ValueError("%s 数值过大: %s" % (what, text[:32]))
    return value
CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#ffffff; --fg:#1f2328; --muted:#59636e; --line:#d1d9e0; --soft:#f6f8fa;
  --accent:#0969da; --mark:#fff3bf; --markfg:#1f2328;
  --t-kw:#cf222e; --t-str:#0a3069; --t-com:#6e7781; --t-num:#0550ae;
  --t-fn:#8250df; --banner:#eaeef2;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#3d444d; --soft:#151b23;
    --accent:#4493f8; --mark:#5c4b00; --markfg:#f0f6fc;
    --t-kw:#ff7b72; --t-str:#a5d6ff; --t-com:#8b949e; --t-num:#79c0ff;
    --t-fn:#d2a8ff; --banner:#1c2128;
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
  gap:12px;padding:9px 14px;background:var(--banner,var(--soft));
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
.kw{color:var(--t-kw)} .str{color:var(--t-str)} .com{color:var(--t-com);font-style:italic}
.num{color:var(--t-num)} .fn{color:var(--t-fn)}
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
/* 回到顶部：**目录页、Markdown 预览页、源码视图**都有（服务端给 <body> 打 data-totop，
   见 _page()；搜索页与错误页不装），由脚本运行时创建 —— 与复制按钮、放大遮罩同一哲学：
   禁用 JS 的基线里没有点不动的死按钮。
   定位用 position:fixed 钉在视口右下角；图标是现画的内联 SVG（不引图标字体）。 */
.totop{position:fixed;right:20px;bottom:20px;z-index:5;
  width:40px;height:40px;padding:0;border:1px solid var(--line);border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  background:var(--soft);color:var(--fg);cursor:pointer;
  box-shadow:0 2px 8px rgb(0 0 0 / .18)}
.totop:hover{background:var(--line);color:var(--accent)}
.totop:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.totop svg{display:block;width:20px;height:20px}
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
/* 打印：页面装饰（顶栏/面包屑/提示条）与三件 JS 注入物（放大遮罩、复制按钮、
   回到顶部）都不上纸。集中成一处，别再散回各自的规则旁边。 */
@media print{
  header.bar,.crumbs,.note{display:none}
  body{background:#fff;color:#000}
  .wrap{max-width:none;padding:0}
  pre,table,blockquote,code{border-color:#999;background:#f7f7f7}
  dialog.zoomdlg[open],.copybtn,.totop{display:none}   /* [open] 才压得住 display:flex */
}
"""
COPY_JS = """
(function () {
  var SVG_NS = "http://www.w3.org/2000/svg";

  // 全站图标都由这里现画（不引图标字体、也不用字体字形 —— 字形的墨迹在 em 盒里
  // 不居中且各字体偏得不一样，见 SELFTEST §30）。关闭 × 与回到顶部 ↑ 只差 path
  // 与线帽，其余那一串 setAttribute 不必抄两遍。
  function svgIcon(d, roundCaps) {
    var svg = document.createElementNS(SVG_NS, "svg");
    var path = document.createElementNS(SVG_NS, "path");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");   // 可访问名一律由宿主按钮的 aria-label 给
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "currentColor");   // 强制色彩模式下也不会被压没
    path.setAttribute("stroke-width", "2");
    if (roundCaps) {
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
    }
    svg.appendChild(path);
    return svg;
  }
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
    // 两条对角线在 24 格里的墨迹范围 ≈ 10.4px × 10.4px，与原字形（10.1 × 10.5）相仿
    btn.appendChild(svgIcon("M7.5 7.5 16.5 16.5M16.5 7.5 7.5 16.5", false));
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

  // 3) 回到顶部：目录页 / Markdown 预览页 / 源码视图才注入（服务端在这些页面的 <body>
  //    上打了 data-totop，见 _page()）。按钮由脚本创建，所以禁用 JS 的基线里没有点不动
  //    的死按钮 —— 与复制按钮、放大遮罩同一哲学。图标是一根轴加一个箭头。
  if (document.body.hasAttribute("data-totop")) {
    var toTop = document.createElement("button");
    toTop.type = "button"; toTop.className = "totop";
    toTop.setAttribute("aria-label", "\u56de\u5230\u9876\u90e8");
    toTop.appendChild(svgIcon("M12 19 12 6M6 12 12 6 18 12", true));
    toTop.addEventListener("click", function () {
      // 动效听系统的：prefers-reduced-motion 时直接跳，不做平滑滚动
      var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (window.scrollTo && !calm) window.scrollTo({ top: 0, behavior: "smooth" });
      else window.scrollTo(0, 0);
    });
    document.body.appendChild(toTop);
  }
})();
"""
def _page(title, body, nav_right="", show_search=None, search_q="", depth_nav="",
          to_top=False):
    if show_search is None:
        show_search = CFG.search
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
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body%s>\n<div class=\"wrap\">\n"
        "<header class=\"bar\"><a class=\"brand\" href=\"/\">mdview</a>"
        "%s<div class=\"spacer\"></div>%s%s</header>\n"
        "%s\n</div>\n<script>%s</script>\n</body>\n</html>\n"
    ) % (html.escape(title), CSS, ' data-totop="1"' if to_top else "",
         depth_nav, search, nav_right, body, COPY_JS)
def _crumbs(rel_path):
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
COMMON_KEYWORDS = {
    "if", "else", "elif", "for", "while", "do", "switch", "case", "default", "break",
    "continue", "return", "goto", "sizeof", "struct", "union", "enum", "typedef",
    "static", "const", "volatile", "extern", "inline", "register", "unsigned", "signed",
    "void", "char", "short", "int", "long", "float", "double", "class", "public",
    "private", "protected", "virtual", "override", "final", "new", "delete", "this",
    "super", "extends", "implements", "interface", "package", "import", "export",
    "from", "namespace", "using", "template", "typename", "try", "catch", "finally",
    "throw", "throws", "instanceof", "typeof", "in", "of", "with", "as", "is",
    "function", "var", "let", "async", "await", "yield", "lambda", "match", "when",
    "true", "false", "null", "nil", "None", "True", "False", "undefined", "NaN",
    "def", "pass", "raise", "except", "global", "nonlocal", "assert", "del", "and",
    "or", "not", "print",
    "func", "defer", "chan", "select", "go", "range", "map", "impl", "trait", "mut",
    "pub", "crate", "mod", "fn", "where", "unsafe", "dyn", "ref", "loop", "move",
    "String", "Vec", "Option", "Result", "Some", "Ok", "Err", "println", "printf",
    "echo", "cd", "ls", "export", "local", "source", "then", "fi", "esac", "done",
    "until", "sudo", "set", "unset", "readonly", "alias",
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "GROUP", "ORDER", "BY", "HAVING",
    "LIMIT", "OFFSET", "CREATE", "TABLE", "INDEX", "DROP", "ALTER", "AND", "OR",
    "NOT", "NULL", "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "DISTINCT", "AS",
}
LANG_KEYWORDS = {
    "python": set("""and as assert async await break class continue def del elif else except
        finally for from global if import in is lambda nonlocal not or pass raise return
        try while with yield None True False self match case""".split()),
    "py": None,
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
PLAIN_LANGS = {"text", "plaintext", "txt", "none", "raw"}
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
    "compose": "Docker Compose", "makefile": "Makefile",
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
    if not info:
        return ""
    return info.strip().split()[0].strip().lower().lstrip("{.").rstrip("}")
def highlight(code, info=""):
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
ALIASES = {
    "nbsp": "\u00a0", "copy": "©", "reg": "®", "trade": "™", "hellip": "…",
    "mdash": "—", "ndash": "–", "laquo": "«", "raquo": "»", "times": "×",
    "divide": "÷", "plusmn": "±", "deg": "°", "middot": "·", "bull": "•",
    "larr": "←", "rarr": "→", "uarr": "↑", "darr": "↓", "harr": "↔",
    "check": "✓", "cross": "✗", "star": "★", "hearts": "♥", "euro": "€",
    "pound": "£", "yen": "¥", "sect": "§", "para": "¶", "dagger": "†",
    "ldquo": "“", "rdquo": "”", "lsquo": "‘", "rsquo": "’",
}
SAFE_SCHEMES = frozenset((
    "http", "https", "mailto", "ftp", "ftps", "sftp", "tel", "sms", "news",
    "irc", "ircs", "xmpp", "magnet", "gemini", "gopher",
))
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")
def _has_scheme(text):
    return _SCHEME_RE.match(text) is not None
def safe_href(url):
    if url is None:
        return ""
    text = str(url).strip()
    text = "".join(ch for ch in text if ord(ch) >= 0x20 and ch != "\x7f")
    match = _SCHEME_RE.match(text)
    if match:
        if match.group(1).lower() not in SAFE_SCHEMES:
            return ""
    elif text.startswith("//"):
        pass
    return html.escape(text, quote=True)
def _target_attrs(ctx, dest):
    try:
        decoded = urllib.parse.unquote(dest)
    except Exception:
        decoded = dest
    if _has_scheme(decoded):
        href = safe_href(dest)
        return href, (' rel="noreferrer noopener"' if href else "")
    return safe_href(ctx.rewrite_target(dest)), ""
def _title_attr(title):
    return ' title="%s"' % html.escape(title, quote=True) if title else ""
_AUTOLINK_RE = re.compile(r"<((?:https?|ftp|mailto)://[^\s<>]+|[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>")
_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_ENTITY_RE = re.compile(r"&(#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
_REF_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\[([^\]]*)\]")
_REF_DEF_RE = re.compile(
    r"^ {0,3}\[([^\]]+)\]:\s*(<[^<>\n]*>|\S+)"
    r"(?:\s+(?:\"([^\"]*)\"|'([^']*)'|\(([^)]*)\)))?\s*$")
_ANGLE_SAFE = ";/?:@&=+$,-_.!~*'#%"
_ANGLE_DEST_RE = re.compile(
    r"\]\(<([^<>\x00-\x1f]*)>\s*(\"[^\"]*\"|'[^']*'|\([^)]*\))?\s*\)")
def _encode_angle_inner(inner):
    return urllib.parse.quote(inner, safe=_ANGLE_SAFE)
def _normalize_angle_dest(text):
    if len(text) >= 2 and text.startswith("<") and text.endswith(">"):
        return _encode_angle_inner(text[1:-1])
    return text
def _angle_dest_sub(m):
    inner, title = m.group(1), m.group(2)
    return "](" + _encode_angle_inner(inner) + (" " + title if title else "") + ")"
_DELIM_RUN_RE = re.compile(r"\*+|_+|~+")
_ESC_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!>~|$])")
_TOKEN_RE = re.compile(r"\x00MK(\d+)\x00")
TOKEN_FMT = "\x00MK%d\x00"
_ESC_OPEN, _ESC_CLOSE = "\ue000", "\ue001"
_CODE_OPEN, _CODE_CLOSE = "\ue002", "\ue003"
_TOKEN_SHIELD = "\ue010"
_LT_SHIELD, _GT_SHIELD = "\ue014", "\ue015"
_BT_SHIELD = "\ue013"
def _entity_sub(m):
    body = m.group(1)
    if body.startswith("#"):
        return m.group(0)
    return ALIASES.get(body.lower(), m.group(0))
def _autolink_sub(m):
    target = m.group(1)
    text = html.escape(target, quote=False)
    if "@" in target and "://" not in target and not _SCHEME_RE.match(target):
        return '<a href="%s">%s</a>' % (safe_href("mailto:" + target), text)
    return '<a href="%s" rel="noreferrer noopener">%s</a>' % (
        safe_href(target), text)
_BARE_URL_RE = re.compile(r"https?://[^\s<>\x00`]+", re.I)
_TAIL_PUNCT = ".,:;!?"
_TAIL_PUNCT_CJK = "。，、；：！？"
_CJK_TAIL_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+$")
_CJK_PUNCT_RE = re.compile(r"[%s]" % re.escape(_TAIL_PUNCT_CJK))
_TAIL_QUOTES = "\"'\u201c\u201d"
_AMP_AT_END_RE = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9a-fA-F]{1,6}|[A-Za-z][A-Za-z0-9]{1,31})?$")
_REF_DEF_MARK_RE = re.compile(r"^\s{0,3}\[[^\]\n]*\]:\s", re.M)
def _trim_bare_url(text, start, end):
    while end > start:
        ch = text[end - 1]
        m = _CJK_TAIL_RE.search(text, start, end)
        if m:
            if m.start() == start:
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
            if n <= 0:
                end -= 1
                continue
            break
        if ch == ";" and _AMP_AT_END_RE.search(text, start, end - 1):
            break
        if "&" in text[start:end] and _AMP_AT_END_RE.search(text, start, end):
            break
        if ch in _TAIL_PUNCT or ch in _TAIL_PUNCT_CJK or ch in _TAIL_QUOTES:
            end -= 1
            continue
        break
    return end
def _link_dest_spans(text):
    out = []
    if "](" not in text:
        return out
    for _, _, _, dest_end in _scan_link_spans(text):
        out.append((dest_end - 2, dest_end))
    return out
def _bare_url_sub(text, protected=None):
    if "://" not in text:
        return None
    out = []
    pos = 0
    line_start = 0
    merged = []
    for ps, pe in sorted(protected or ()):
        if merged and ps <= merged[-1][1]:
            if pe > merged[-1][1]:
                merged[-1][1] = pe
        else:
            merged.append([ps, pe])
    starts = [iv[0] for iv in merged]
    def covered(s, e):
        k = bisect.bisect_right(starts, s) - 1
        if k >= 0 and merged[k][1] > s:
            return True
        k += 1
        return k < len(merged) and merged[k][0] < e
    for m in _BARE_URL_RE.finditer(text):
        start = m.start()
        end = _trim_bare_url(text, start, m.end())
        if end <= start or covered(start, end):
            continue
        nl = text.find("\n", line_start, start)
        if nl >= 0:
            line_start = nl + 1
        m2 = _REF_DEF_MARK_RE.match(text, line_start, start)
        if m2:
            continue
        url = text[start:end]
        href = safe_href(url)
        if not href:
            continue
        out.append((text[pos:start], False))
        out.append(('<a href="%s" rel="noreferrer noopener">%s</a>'
                    % (href, html.escape(url, quote=False)), True))
        pos = end
    if not out:
        return None
    out.append((text[pos:], False))
    return out
def _bracket_pairs(text):
    pairs = {}
    stack = []
    for i, ch in enumerate(text):
        if ch == "[":
            stack.append(i)
        elif ch == "]" and stack:
            pairs[stack.pop()] = i
    return pairs
def _scan_link_spans(text):
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
            i = k
            continue
        spans.append((i, i + 1, close, k))
        i = k
    return spans
_TITLE_QUOTES = (("\"", "\""), ("'", "'"), ("(", ")"), ("&quot;", "&quot;"))
def _split_link_tail(tail):
    if tail.startswith("<"):
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
def _quoted_inner(t):
    for open_q, close_q in _TITLE_QUOTES:
        if t.startswith(open_q) and t.endswith(close_q) and len(t) >= 2 * len(open_q):
            return t[len(open_q):-len(close_q)]
    return None
def _parse_link_title(tail):
    return _quoted_inner(tail.strip()) or ""
def _tail_is_blank_or_title(rest):
    t = rest.strip()
    return not t or _quoted_inner(t) is not None
_IMG_ALT_ATTR_RE = re.compile(r'<img\b[^>]*?\balt="([^"]*)"[^>]*>')
_ANY_TAG_RE = re.compile(r"<[^>]*>")
_OWN_TAG_SCAN_RE = re.compile(r"<a\b[^>]*>|</a>|<img\b[^>]*>")
_IMG_SRC_ATTR_RE = re.compile(r'\bsrc="([^"]*)"')
def wrap_zoom_images(html_text):
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
    text = _IMG_ALT_ATTR_RE.sub(r"\1", html_label)
    return html.unescape(_ANY_TAG_RE.sub("", text))
def parse_inline(text, ctx):
    tokens = []
    def stash(s):
        tokens.append(s)
        return TOKEN_FMT % (len(tokens) - 1)
    def read_tokens(s):
        def one(mm):
            idx = int(mm.group(1))
            if not (0 <= idx < len(tokens)):
                return mm.group(0)
            val = tokens[idx]
            if val.startswith("<"):
                return val
            return html.unescape(val)
        return re.sub(_TOKEN_SHIELD + r"MK(\d+)" + _TOKEN_SHIELD, one,
                      _TOKEN_RE.sub(one, s))
    def read_tokens_markup(s):
        def one(mm):
            idx = int(mm.group(1))
            if not (0 <= idx < len(tokens)):
                return mm.group(0)
            return tokens[idx]
        return re.sub(_TOKEN_SHIELD + r"MK(\d+)" + _TOKEN_SHIELD, one,
                      _TOKEN_RE.sub(one, s))
    text = _ESC_RE.sub(
        lambda m: stash('<span class="esc">%s</span>'
                        % html.escape(m.group(1), quote=False)), text)
    shield_count = {"\x00": text.count("\x00"), "`": 0}
    shielded = text.replace("\x00", _TOKEN_SHIELD)
    bt_open = re.escape(_ESC_OPEN) + "`"
    bt_close = "`" + re.escape(_ESC_CLOSE)
    shield_count["`"] = len(re.findall(bt_open, shielded)) + len(re.findall(bt_close, shielded))
    shielded = re.sub(bt_open, _ESC_OPEN + _BT_SHIELD, shielded)
    shielded = re.sub(bt_close, _BT_SHIELD + _ESC_CLOSE, shielded)
    code_spans = []
    def stash_code(m):
        inner = m.group(2).strip().replace(_BT_SHIELD, "`")
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
    text = _ANGLE_DEST_RE.sub(_angle_dest_sub, text)
    text = _TAG_RE.sub(lambda m: stash(html.escape(m.group(0), quote=False)), text)
    text = _AUTOLINK_RE.sub(lambda m: stash(_autolink_sub(m)), text)
    if "://" in text:
        protected = list(_bracket_pairs(text).items()) + _link_dest_spans(text)
        batches = _bare_url_sub(text, protected)
        if batches is not None:
            text = "".join(stash(chunk) if rendered else chunk
                           for chunk, rendered in batches)
    text = _ENTITY_RE.sub(lambda m: stash(_entity_sub(m)), text)
    text = html.escape(text, quote=False)
    def attr_text(raw):
        text = re.sub(re.escape(_CODE_OPEN) + r"(\d+)" + re.escape(_CODE_CLOSE),
                      lambda m: "<code>%s</code>" % code_spans[int(m.group(1))], raw)
        return _alt_text(read_tokens_markup(text))
    def render_link(label_raw, dest_raw, title_raw):
        dest = html.unescape(read_tokens(dest_raw))
        target, extra = _target_attrs(ctx, dest)
        attr = ' href="%s"' % target if target else ""
        title = attr_text(title_raw) if title_raw else ""
        return '<a%s%s%s>%s</a>' % (attr, _title_attr(title), extra,
                                    render_label(label_raw))
    def render_label(plain):
        inner = scan_inline(plain)
        return read_tokens_markup(parse_emphasis(inner))
    def render_image(alt_raw, dest_raw, title_raw):
        dest = html.unescape(read_tokens(dest_raw))
        src, _rel = _target_attrs(ctx, dest)
        if not src:
            return None
        title = attr_text(title_raw) if title_raw else ""
        return '<img src="%s" alt="%s"%s>' % (
            src, html.escape(_alt_text(render_label(alt_raw)), quote=True),
            _title_attr(title))
    def scan_inline(text):
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
                continue
            label_raw = text[lab_start:lab_end]
            if is_img:
                html_img = render_image(label_raw, dest_raw, title_raw)
                if html_img is None:
                    continue
                out.append(text[pos:cut])
                out.append(stash(html_img))
            else:
                out.append(text[pos:cut])
                out.append(stash(render_link(label_raw, dest_raw, title_raw)))
            pos = dest_end
        out.append(text[pos:])
        return "".join(out)
    text = _REF_DEF_LINK(text, ctx, render_label, stash)
    text = _REF_SHORT_RE.sub(lambda m: _shortcut_ref(m, ctx, render_label, stash),
                             text)
    text = scan_inline(text)
    text = parse_emphasis(text)
    def resolve_token(mm):
        idx = int(mm.group(1))
        if 0 <= idx < len(tokens):
            return tokens[idx]
        return mm.group(0)
    text = _TOKEN_RE.sub(resolve_token, text)
    text = re.sub(re.escape(_CODE_OPEN) + r"(\d+)" + re.escape(_CODE_CLOSE),
                  lambda m: "<code>%s</code>" % code_spans[int(m.group(1))], text)
    return wrap_zoom_images(text)
def _ref_link_html(ctx, url, title, label_html):
    href, extra = _target_attrs(ctx, url)
    attr = ' href="%s"' % href if href else ""
    return '<a%s%s%s>%s</a>' % (attr, _title_attr(title), extra, label_html)
def _ref_image_html(ctx, url, title, alt_text):
    src, _rel = _target_attrs(ctx, url)
    if not src:
        return None
    return '<img src="%s" alt="%s"%s>' % (
        src, html.escape(alt_text, quote=True), _title_attr(title))
def _REF_DEF_LINK(text, ctx, render_label, stash):
    if "][" not in text:
        return text
    def sub(m):
        bang, label, ref = m.group(1), m.group(2), m.group(3)
        return _render_ref(ctx, bang, label, (ref or label).strip().lower(),
                           render_label, stash, m.group(0))
    return _REF_LINK_RE.sub(sub, text)
def _shortcut_ref(m, ctx, render_label, stash):
    bang, label = m.group(1), m.group(2)
    return _render_ref(ctx, bang, label, label.strip().lower(),
                       render_label, stash, m.group(0))
def _render_ref(ctx, bang, label, key, render_label, stash, fallback):
    target = ctx.refs.get(key)
    if target is None:
        return fallback
    url, title = target
    if bang:
        img = _ref_image_html(ctx, url, title, _alt_text(render_label(label)))
        return stash(img) if img is not None else fallback
    return stash(_ref_link_html(ctx, url, title, render_label(label or key)))
def _ascii_word(ch):
    return ch.isascii() and ch.isalnum()
def _flanking(text, sym, start, end, prev=None, nxt=None):
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
        can_open = can_close = False
    if sym[0] == "_" and _ascii_word(prev):
        can_open = False
    if sym[0] == "_" and _ascii_word(nxt):
        can_close = False
    return can_open, can_close
def _rewrite_triple(text):
    rx = re.compile(r"(?<![A-Za-z0-9_*])\*{3}(?=\S)((?:(?!\*{3}).)+?)(?<!\s)\*{3}",
                    re.DOTALL)
    rxu = re.compile(r"(?<![A-Za-z0-9_])_{3}(?=\S)((?:(?!_{3}).)+?)(?<!\s)_{3}",
                     re.DOTALL)
    for _ in range(4):
        new_text = rx.sub(lambda m: "<strong><em>%s</em></strong>" % m.group(1), text)
        new_text = rxu.sub(lambda m: "<strong><em>%s</em></strong>" % m.group(1), new_text)
        if new_text == text:
            break
        text = new_text
    return text
def _split_run(run, prev_ch, next_ch):
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
def parse_emphasis(text):
    text = _rewrite_triple(text)
    delims = list(_DELIM_RUN_RE.finditer(text))
    if len(delims) > MAX_DELIM_RUNS:
        delims = delims[:MAX_DELIM_RUNS]
    nodes = []
    pos = 0
    run_id = 0
    for m in delims:
        if m.start() > pos:
            nodes.append(("text", text[pos:m.start()], pos, None, 0, 1))
        run = m.group(0)
        prev_ch = text[m.start() - 1] if m.start() > 0 else " "
        next_ch = text[m.end()] if m.end() < len(text) else " "
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
        if opener.startswith("~") or closer.startswith("~"):
            return (opener.startswith("~") and closer.startswith("~")
                    and len(opener) >= 2 and len(closer) >= 2)
        return opener[0] == closer[0] and len(opener) == len(closer)
    def nearest_closer(start, frm, sym):
        for j in range(max(start, frm), len(nodes)):
            kind, other = nodes[j][0], nodes[j][1]
            if kind in ("close", "both") and can_match(sym, other):
                return j
        return None
    closer = {}
    claimed = set()
    frames = {}
    def blocked_before(a, b, sym, my_run):
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
            if j in claimed:
                j += 1
                continue
            if blocked_before(i + 1, j, sym, run):
                j += 1
                continue
            hit = j
            break
        if hit is not None:
            closer[i] = hit
            claimed.add(hit)
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
def quote_seg(seg):
    return urllib.parse.quote(seg, safe="")
def url_for_rel(rel, trailing_slash=False):
    parts = [quote_seg(x) for x in rel.split("/") if x]
    url = "/" + "/".join(parts)
    if not trailing_slash:
        return url
    return url if url.endswith("/") else url + "/"
def depth_nav_html(rel):
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
        return None
    return "/" + joined + trail
class RenderContext(object):
    def __init__(self, rel_path, refs=None, root=None):
        self.rel_path = rel_path
        self.base = posixpath.dirname(rel_path)
        self.root = root
        self.refs = refs or {}
    def _url_for(self, href):
        resolved = _resolve_target(href, self.base)
        if resolved is None:
            return quote_seg_path(href), False
        return quote_seg_path(resolved), True
    def rewrite_target(self, href):
        try:
            decoded = urllib.parse.unquote(href)
        except Exception:
            decoded = href
        if _has_scheme(decoded):
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
    if path.startswith("http://") or path.startswith("https://") or \
            _has_scheme(path):
        return path
    return "/".join(quote_seg(seg) for seg in path.split("/"))
def slugify(text):
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
    if "|" not in lines[i + 1]:
        return False
    return len(split_table_row(lines[i])) >= 1
def expand_tabs(s):
    return s.replace("\t", "    ")
def indent_of(s):
    return len(s) - len(s.lstrip(" "))
def render_markdown(text, rel_path=""):
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    refs, kept = {}, []
    in_fence = None
    for line in lines:
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
        return ('<p class="note">这篇文档的嵌套层数超出渲染器上限，'
                '已按纯文本显示。</p>\n<pre>%s</pre>'
                % html.escape(text[:200000], quote=False))
def render_blocks(lines, ctx, depth=0):
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
            if lang and lang not in PLAIN_LANGS:
                body = highlight(code, info)
            else:
                body = html.escape(code, quote=False)
            banner = ('<div class="codebanner"><span class="lang">%s</span></div>'
                      % html.escape(label)) if label else ''
            out.append('<div class="codeblock">%s<pre><code%s>%s</code></pre></div>'
                       % (banner, cls, body))
            continue
        m = RE_ATX.match(line)
        if m:
            level = len(m.group(1))
            raw = (m.group(2) or "").strip()
            inner = parse_inline(raw, ctx)
            out.append(_heading(level, inner, ctx))
            i += 1
            continue
        if RE_HR.match(line):
            out.append("<hr>")
            i += 1
            continue
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
        if RE_QUOTE.match(line):
            buf = []
            while i < n:
                qm = RE_QUOTE.match(lines[i])
                if qm:
                    buf.append(qm.group(1))
                    i += 1
                elif not lines[i].strip():
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
        if RE_ULIST.match(line) or RE_OLIST.match(line):
            html_list, i = _render_list(lines, i, ctx, depth)
            out.append(html_list)
            continue
        if i + 1 < n and line.strip() and "|" not in line \
                and RE_SETEXT.match(lines[i + 1]) \
                and lines[i + 1].lstrip().startswith("=") \
                and not RE_ULIST.match(lines[i + 1]) and not RE_OLIST.match(lines[i + 1]):
            sm = RE_SETEXT.match(lines[i + 1])
            level = 1 if sm.group(1).startswith("=") else 2
            out.append(_heading(level, parse_inline(line.strip(), ctx), ctx))
            i += 2
            continue
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not _starts_block(lines, i):
            buf.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % parse_inline(" ".join(x.strip() for x in buf), ctx))
    return "\n".join(x for x in out if x)
def _starts_block(lines, i):
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
    ordered = bool(RE_OLIST.match(lines[start]))
    start_num = int(RE_OLIST.match(lines[start]).group(2)) if ordered else 1
    n = len(lines)
    items = []
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
        cls = "d" if is_dir else ""
        if is_dir:
            href += "/"
            icon, meta = "📁", "目录"
        else:
            ext = os.path.splitext(name)[1].lower()
            icon = ("📝" if ext == MD_EXT else
                    "🖼" if ext in IMAGE_EXT else "📄")
            meta = _fmt_size(size) + " · " + time.strftime("%Y-%m-%d %H:%M",
                                                           time.localtime(mtime))
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
    needle = query.lower()
    body_hits, name_hits = [], []
    scanned = 0
    truncated = False
    for path in iter_markdown(abs_root):
        if len(body_hits) >= cap:
            truncated = True
            break
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
class Config(object):
    def __init__(self):
        self.root = os.getcwd()
        self.safe = False
        self.search = True
        self.max_preview = DEFAULT_MAX_PREVIEW
CFG = Config()
_RENDER_CACHE = {}
_CACHE_LOCK = threading.Lock()
def _is_regular_file(path):
    try:
        return stat.S_ISREG(os.stat(path).st_mode)
    except OSError:
        return False
def _inside(root, path):
    if path == root:
        return True
    return path.startswith(root.rstrip(os.sep) + os.sep)
def _resolve(abs_root, url_path):
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
        try:
            BaseHTTPRequestHandler.handle_one_request(self)
        except (ConnectionResetError, BrokenPipeError):
            self.close_connection = True
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
        if not CFG.max_preview:
            return False
        try:
            return os.path.getsize(path) > CFG.max_preview
        except OSError:
            return False
    def _send_file(self, path, force_download=False):
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
    def do_GET(self):
        try:
            self._route()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
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
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                self.send_header("Location", url_for_rel(rel, trailing_slash=True))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._send(HTTPStatus.OK, self._list_view(abs_path, rel))
            return
        if not os.path.exists(abs_path):
            self._send(HTTPStatus.NOT_FOUND, _error_page("404", "文件不存在", rel))
            return
        raw = self._flag(qs, "raw")
        ext = os.path.splitext(abs_path)[1].lower()
        if CFG.safe and ext not in SAFE_EXT:
            self._send(HTTPStatus.NOT_FOUND,
                       _error_page("404", "safe 模式下只服务 .md 与图片", rel))
            return
        want_download = self._flag(qs, "download")
        if want_download:
            self._send_file(abs_path, force_download=True)
            return
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
    @staticmethod
    def _flag(qs, name):
        return (qs.get(name) or ["0"])[0] not in ("0", "", "false", "no")
    @staticmethod
    def _parent_link(rel):
        if not rel:
            return ""
        parent = "/".join(rel.split("/")[:-1])
        return '<p><a href="%s">../ 上级目录</a></p>' % url_for_rel(parent, trailing_slash=True)
    @staticmethod
    def _render_page(rel, title, body, nav_right=""):
        return _page(title, body, nav_right=nav_right,
                     depth_nav=depth_nav_html(rel), to_top=True)
    def _list_view(self, abs_dir, rel):
        head = [x for x in (_crumbs(rel) if rel else "", self._parent_link(rel)) if x]
        body = "\n".join(head) + render_dir_listing(abs_dir, rel)
        return self._render_page(rel, self._index_title(rel), body)
    @staticmethod
    def _index_title(rel):
        return "索引 " + ("/" + rel if rel else "/")
    def _raw_page(self, abs_path, rel):
        text = self._read_text(abs_path)
        if text is None:
            return HTTPStatus.NOT_FOUND, _error_page("404", "无法读取文件", rel)
        raw_url = url_for_rel(rel) + "?raw=1"
        rows = []
        for n, line in enumerate(text.split("\n"), 1):
            safe = html.escape(line, quote=False)
            rows.append('<span class="srcline" id="L%d">%s</span>' % (n, safe))
        body = (_crumbs(rel) + '\n<p class="note">源码视图（每行带锚点，可从搜索直接跳转）。'
                '<a href="%s">看渲染结果</a></p>\n<pre class="rawsrc">%s</pre>'
                % (html.escape(url_for_rel(rel), quote=True), "\n".join(rows)))
        return HTTPStatus.OK, self._render_page(
            rel, posixpath.basename(rel) + "（源码）", body,
            nav_right='<a class="btn" href="%s">渲染</a>'
            % html.escape(url_for_rel(rel), quote=True))
    @staticmethod
    def _read_text(abs_path):
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
        raw_link = ('<a class="btn" href="%s?raw=1" title="查看原始 Markdown">源</a>'
                    % html.escape(url_for_rel(rel), quote=True))
        body = _crumbs(rel) + "\n" + cached
        return HTTPStatus.OK, self._render_page(rel, title, body, nav_right=raw_link)
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
    if not _has_md(root):
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
            scored.append((0, rel))
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
def _has_md(path):
    try:
        for name in os.listdir(path):
            if os.path.isfile(os.path.join(path, name)) and name.lower().endswith(MD_EXT):
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
