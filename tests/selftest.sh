#!/usr/bin/env bash
# selftest.sh —— mdview 端到端冒烟测试
#
#   bash tests/selftest.sh            # 在仓库根执行
#   PORT=9000 bash tests/selftest.sh  # 换一组临时端口
#
# 脚本从自身位置推出仓库根（ROOT），所以从任何目录执行都可以。
#
# 自己起一个 127.0.0.1 的临时服务，跑完所有断言后关闭。
# 全部通过才算可用；失败项会打印期望值。
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"        # tests/
ROOT="$(cd "$HERE/.." && pwd)"               # 仓库根：mdview.py 与 docs/ 在这里
PORT="${PORT:-8731}"
# MDVIEW 可指向别处的同名脚本（例如压缩版），校验行为一致：
#   MDVIEW=dist/mdview.min.py bash tests/selftest.sh
MDVIEW="${MDVIEW:-$ROOT/mdview.py}"
BASE="http://127.0.0.1:${PORT}"
LOG="$(mktemp -t mdview-selftest)"

# 所有临时实例都要登记，否则 EXIT 时后起的 --safe/--no-search/端口回退实例会变孤儿
PIDS=""
cleanup() {
  for pid in $PIDS; do kill "$pid" 2>/dev/null; done
  wait 2>/dev/null
}
trap cleanup EXIT

# 等某个端口上的服务就绪（最多 6 秒）
wait_ready() {
  local port="$1" i
  for i in $(seq 1 30); do
    curl -s -o /dev/null "http://127.0.0.1:$port/" && break
    sleep 0.2
  done
}

# 起一个临时实例并等它就绪；用法: serve_temp <端口> <日志文件> [额外参数...]
# 把实例 PID 登记进 PIDS，EXIT 时统一回收（否则会留下孤儿进程）。
serve_temp() {
  local port="$1" log="$2"; shift 2
  python3 "$MDVIEW" --root "$ROOT/docs" --port "$port" --host 127.0.0.1 "$@" \
      >"$log" 2>&1 &
  local pid=$!
  PIDS="$PIDS $pid"
  wait_ready "$port"
  printf '%s' "$pid"
}

# 数一个请求在**同一条连接**上写出了几个 HTTP 响应（协议正确性用）。
# 用法: count_responses <base-url> <路径>
count_responses() {
  python3 - "$1" "$2" <<'PYEOF'
import socket, sys
host = sys.argv[1].replace("http://", "")
hostname, port = host.split(":")
sock = socket.create_connection((hostname, int(port)))
sock.sendall(("GET %s HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
              % sys.argv[2]).encode())
data = b""
while True:
    chunk = sock.recv(65536)
    if not chunk:
        break
    data += chunk
sock.close()
print(data.count(b"HTTP/1.1 "))
PYEOF
}

SERVER_PID="$(serve_temp "$PORT" "$LOG")"

# 指定任意 root 起临时实例：serve_root <端口> <root> [额外参数...]
serve_root() {
  local port="$1" root="$2"; shift 2
  python3 "$MDVIEW" --root "$root" --port "$port" --host 127.0.0.1 "$@" \
      >/dev/null 2>&1 &
  local pid=$!
  PIDS="$PIDS $pid"
  wait_ready "$port"
  printf '%s' "$pid"
}

pass=0; fail=0; failed_names=""
chk() { # 名称 内容 期望子串
  if printf '%s' "$2" | grep -qF -- "$3"; then
    printf '  \033[32mok\033[0m   %s\n' "$1"; pass=$((pass+1))
  else
    printf '  \033[31mFAIL\033[0m %s  (期望包含: %s)\n' "$1" "$3"; fail=$((fail+1)); failed_names="$failed_names $1"
  fi
}
nchk() { # 名称 内容 不应出现的子串
  if printf '%s' "$2" | grep -qF -- "$3"; then
    printf '  \033[31mFAIL\033[0m %s  (不应包含: %s)\n' "$1" "$3"; fail=$((fail+1)); failed_names="$failed_names $1"
  else
    printf '  \033[32mok\033[0m   %s\n' "$1"; pass=$((pass+1))
  fi
}
code() { curl -s -o /dev/null -w '%{http_code}' "$1"; }

echo "== 目录索引 / =="
IDX="$(curl -s "$BASE/")"
chk "列出 index.md"       "$IDX" 'index.md'
chk "列出 guide/ 子目录"  "$IDX" 'guide/'
chk "带搜索框"            "$IDX" 'action="/search"'
chk "带返回上级"          "$(curl -s "$BASE/guide/")" '上级目录'

echo "== Markdown 渲染 /index.md =="
MD="$(curl -s "$BASE/index.md")"
chk "h1 生成锚点 id"      "$MD" '<h1 id="mdview-示例文档">'
chk "粗体"                "$MD" '<strong>粗体</strong>'
chk "斜体"                "$MD" '<em>斜体</em>'
chk "粗斜 ***"            "$MD" '<strong><em>粗斜</em></strong>'
chk "删除线 ~~"           "$MD" '<del>删除线</del>'
chk "行内代码"            "$MD" '<code>行内代码</code>'
chk "文档间链接"          "$MD" 'href="/guide/install.md"'
chk "带锚点链接"          "$MD" 'href="/guide/install.md#安装步骤"'
chk "同页锚点"            "$MD" 'href="#表格与对齐"'
chk "外链"                "$MD" 'href="https://example.com"'
chk "表格 thead"          "$MD" '<thead>'
chk "表格对齐属性"        "$MD" 'style="text-align:center"'
chk "任务列表已勾选"      "$MD" '<input type="checkbox" disabled checked>'
chk "任务列表未勾选"      "$MD" '<input type="checkbox" disabled>'
chk "嵌套列表"            "$MD" '<li>子项一</li>'
chk "引用块"              "$MD" '<blockquote>'
chk "代码高亮关键字"      "$MD" '<span class="kw">import</span>'
chk "代码高亮字符串"      "$MD" '<span class="str">`hello ${name}`</span>'
chk "代码高亮注释"        "$MD" '<span class="com">'
chk "分隔线"              "$MD" '<hr>'
chk "引用式链接标题"      "$MD" 'title="零依赖离线 Markdown 预览"'
chk "HTML 实体"           "$MD" '©'
chk "裸 HTML 被转义"      "$MD" '&lt;script&gt;'
nchk "无未转义 script"    "$MD" '<script>alert'
chk "样式内联"            "$MD" '<style>'
nchk "无外部样式表请求"   "$MD" '<link rel="stylesheet"'
nchk "无外部脚本请求"     "$MD" '<script src='
# 示例页里的裸 URL 演示小节（docs/index.md「裸 URL 自动链接」）
chk "示例页有裸 URL 小节"   "$MD" '<h2 id="裸-url-自动链接">'
chk "示例页裸 URL 可点"     "$MD" '访问 <a href="https://example.com/mdview" rel="noreferrer noopener">https://example.com/mdview</a> 看看'
chk "示例页句末标点归句子"  "$MD" '</a>. 结束'
chk "示例页全角句号归句子"  "$MD" '</a>。结束'
chk "示例页括号配平"        "$MD" 'href="https://en.wikipedia.org/wiki/A_(b)"'
chk "示例页行内码不链接化"  "$MD" '<code>https://example.com/code</code>'
nchk "示例页标签不嵌套"     "$MD" '<a href="https://example.com/e"'

echo "== ?raw=1 源码视图（每行带锚点，供搜索跳转）=="
RAW="$(curl -s "$BASE/index.md?raw=1")"
chk "返回原始 Markdown 文本" "$RAW" '# mdview 示例文档'
nchk "源码视图不做 Markdown 渲染" "$RAW" '<strong>'
chk "每行都有行锚点 id=\"L1\"" "$RAW" 'id="L1"'
chk "行锚点覆盖到文末"     "$RAW" 'id="L30"'
chk "高亮当前行的样式"     "$RAW" '.srcline:target'
chk "可从源码视图回到渲染" "$RAW" '看渲染结果'
# 行号必须与源文件真实行一致（取第 5 行核对）
LINE5_SRC="$(sed -n '5p' "$ROOT/docs/index.md")"
chk "第 5 行锚点内容与源文件一致" "$RAW" "$LINE5_SRC"

echo "== 子目录与图片 =="
G="$(curl -s "$BASE/guide/install.md")"
chk "子目录文档渲染"      "$G" '<h2 id="安装步骤">'
chk "上级相对链接"        "$G" 'href="/index.md"'
chk "同级相对链接"        "$G" 'href="/guide/advanced.md"'
chk "图片相对路径"        "$G" 'src="/media/logo.svg"'
chk "svg Content-Type"    "$(curl -s -D - -o /dev/null "$BASE/media/logo.svg")" 'image/svg+xml'

echo "== 图片放大（服务端包裹 + 脚本内联） =="
# 不在链接里的正文图片都要包一层可放大链接；href 与 img 的 src 必须同源
# （编码管线只走一次）。没有 JS 时它就是降级路径，有 JS 时被脚本接管。
chk "图片包了可放大链接"    "$G" '<a class="zoom" href="/media/logo.svg">'
chk "href 与 src 逐字节同源" "$G" '<a class="zoom" href="/media/logo.svg"><img src="/media/logo.svg"'
chk "放大脚本已内联"        "$G" 'createElement("dialog")'
chk "放大脚本用 showModal"  "$G" 'showModal'
chk "遮罩样式已内联"        "$G" 'dialog.zoomdlg'
chk "滚动锁样式已内联"      "$G" 'html.zoomlock'
# 关闭按钮必须贴在图片右上角（不是钉在视口右上角抢走"点空白处"的点击，SELFTEST §27）
chk "关闭按钮贴在图片上"    "$G" 'dialog.zoomdlg .zoomclose{position:absolute'
# × 是现画的内联 SVG + 按钮 flex 居中。字体字形（U+00D7）在 em 盒里不居中，各字体
# 偏得还不一样，写死任何 px 校正值都会在别的平台翻车（SELFTEST §30）
chk "关闭图标由 SVG 绘制"   "$G" 'createElementNS(NS, "svg")'
chk "图标描边用 currentColor" "$G" 'setAttribute("stroke", "currentColor")'
# 遮罩的定位与排版在基础规则里，[open] 只切 display：几何不随可见性开关变化
# （SELFTEST §28）。先剥掉 CSS 注释再压掉空白 —— 注释里会引用那条错写法，
# 不剥的话下面的 nchk 会被自己的注释命中。
GFLAT="$(printf '%s' "$G" | python3 -c 'import re,sys; s=sys.stdin.read(); sys.stdout.write(re.sub(r"\s+", "", re.sub(r"/\*.*?\*/", "", s, flags=re.S)))')"
chk "遮罩定位在基础规则"    "$GFLAT" 'dialog.zoomdlg{max-width:none;max-height:none;padding:0;border:0;position:fixed;inset:0;margin:auto;'
chk "遮罩排版在基础规则"    "$GFLAT" 'flex-direction:column;align-items:center;gap:10px;'
chk "[open] 只切 display"   "$GFLAT" 'dialog.zoomdlg[open]{display:flex}'
chk "关闭按钮 flex 居中"    "$GFLAT" 'display:flex;align-items:center;justify-content:center}'
chk "关闭图标 24×24"        "$GFLAT" 'dialog.zoomdlg.zoomclosesvg{display:block;width:24px;height:24px}'
# 打开后的初始焦点落在遮罩自己（tabindex="-1"）而不是 × 上：否则上一轮交互是键盘时，
# 程序化聚焦会命中 :focus-visible，再打开时 × 带一圈白边（SELFTEST §31）
chk "遮罩可作焦点落脚点"    "$G" 'd.tabIndex = -1'
chk "打开后焦点收回遮罩"    "$G" 'zoom.focus();'
chk "遮罩自身不画焦点环"    "$GFLAT" 'dialog.zoomdlg:focus{outline:none}'
nchk "键盘焦点环没被删掉"   "$GFLAT" 'zoomclose:focus-visible{outline:none'
# 只做入场动画：不许有出场过渡（allow-discrete 会把退场拖成 150ms，图片在淡出而
# × / caption 原地亮着 —— "关掉之后关闭按钮还停留一下"，SELFTEST §29）
nchk "退场不做过渡（无 allow-discrete）" "$GFLAT" 'allow-discrete'
nchk "退场不做过渡（无 transition:display）" "$GFLAT" 'transition:display'
chk "入场动画仍在（图片）"  "$GFLAT" '@starting-style{dialog.zoomdlg[open]img{opacity:0;transform:scale(.97)}}'
chk "入场动画仍在（遮罩）"  "$GFLAT" 'dialog.zoomdlg::backdrop{opacity:0;transition:opacity.15sease}'
# 基线（无 JS）里不能有写死的遮罩或关闭按钮 —— 那会是点不动的死元素
nchk "正文里没有写死的 dialog" "$(printf '%s' "$G" | sed -n '/<body>/,/<script>/p')" '<dialog'

echo "== 目录跳转 =="
RED="$(curl -s -D - -o /dev/null "$BASE/guide")"
chk "目录补斜杠 301"      "$RED" '301'
chk "301 Location"        "$RED" 'Location: /guide/'
# 展开树功能已移除：入口与 ?depth= 都不该再出现
nchk "首页无展开树入口"   "$IDX" 'depth=3'
nchk "无 .tree 样式"      "$IDX" '\.tree'
chk "?depth= 无害忽略"    "$(code "$BASE/?depth=3")" '200'
chk "忽略时仍是普通列表"  "$(curl -s "$BASE/?depth=3")" 'dirlist'

echo "== 全文搜索 =="
S="$(curl -s --get --data-urlencode 'q=标准库' "$BASE/search")"
chk "正文命中分区"        "$S" '正文命中'
chk "命中高亮"            "$S" '<mark>标准库</mark>'
chk "结果带行号锚点"      "$S" '#L'
S2="$(curl -s "$BASE/search?q=MDVIEW")"
chk "大小写不敏感"        "$S2" '<mark>mdview</mark>'
chk "文件名命中分区"      "$S2" '文件名命中'
chk "无结果提示"          "$(curl -s "$BASE/search?q=zzz不存在的词")" '没有命中'
chk "空查询提示"          "$(curl -s "$BASE/search")" '输入关键词'
chk "搜索结果指向源码行锚点" "$S" 'href="/index.md?raw=1#L'
chk "搜索分栏带计数"        "$S" '正文命中（'
# 仅文件名命中：临时造一个「名字含关键词、正文不含」的文件
UNI="$ROOT/docs/guide/zzz-selftest-unicorn.md"
printf '# 与关键词无关\n\n正文不提那个词。\n' > "$UNI"
SU="$(curl -s --get --data-urlencode 'q=unicorn' "$BASE/search")"
chk "仅文件名命中也会列出"  "$SU" 'zzz-selftest-unicorn.md'
chk "标注「仅文件名命中」"  "$SU" '仅文件名命中'
rm -f "$UNI"

echo "== 错误处理与安全 =="
chk "不存在返回 404"      "$(code "$BASE/nope.md")" '404'
chk "404 页面友好"        "$(curl -s "$BASE/nope.md")" '文件不存在'
chk "越界路径不泄漏"      "$(code "$BASE/etc/passwd")" '404'
nchk "不返回 passwd 内容" "$(curl -s "$BASE/etc/passwd")" 'root:'
chk "HEAD 可用"           "$(curl -sI -o /dev/null -w '%{http_code}' "$BASE/index.md")" '200'
chk "非 md 文件也可读"    "$(code "$BASE/guide/install.md")" '200'

echo "== 站内链接与图片全部可解析（断链检查） =="
# 把每个渲染页里的 href/src 抓出来，逐个请求，缺一个就算失败
link_fail=0; link_total=0
for page in /index.md /guide/install.md /guide/advanced.md; do
  body="$(curl -s "$BASE$page")"
  for target in $(printf '%s' "$body" | grep -oE '(href|src)="/[^"#?]*"' \
                  | sed -E 's/^(href|src)="//; s/"$//' | sort -u); do
    link_total=$((link_total+1))
    st="$(code "$BASE$target")"
    if [ "$st" != "200" ]; then
      printf '  \033[31mFAIL\033[0m %s 里的 %s -> HTTP %s\n' "$page" "$target" "$st"
      link_fail=$((link_fail+1))
    fi
  done
done
if [ "$link_fail" -eq 0 ]; then
  printf '  \033[32mok\033[0m   站内链接全部可解析（共 %d 个）\n' "$link_total"
  pass=$((pass+1))
else
  fail=$((fail+1)); failed_names="$failed_names 断链"
fi
# 代码块专项文档：12 种语言 + 围栏变体都要渲染出来
CB="$(curl -s "$BASE/guide/code-blocks.md")"
for lang in python javascript typescript go rust java c cpp bash sql json yaml toml ini makefile dockerfile docker-compose brainfuck text markdown; do
  chk "code-blocks: $lang 块" "$CB" "language-$lang"
done
chk "code-blocks: 无语言块不留空白带" "$CB" 'class="codeblock"><pre><code>' 
chk "code-blocks: 围栏内 HTML 被转义"  "$CB" '&lt;div&gt;'
chk "code-blocks: 围栏内 div 未被当标签" "$(printf '%s' "$CB" | grep -c '<div>这不是' || true)" '0'
chk "code-blocks: 行内码保护星号"      "$CB" '<code>**不是粗体**</code>'
chk "code-blocks: 转义反引号"          "$CB" '<span class="esc">`</span>不是代码'
chk "code-blocks: Dockerfile 指令着色"  "$CB" '<span class="kw">FROM</span>'
chk "code-blocks: Dockerfile 小写也着色" "$CB" '<span class="kw">run</span>'
chk "code-blocks: Compose 键着色"       "$CB" '<span class="kw">services</span>'
chk "code-blocks: 语言标签 Dockerfile"  "$CB" 'Dockerfile</span>'
chk "code-blocks: 语言标签 Compose"     "$CB" 'Docker Compose</span>'
chk "code-blocks: UTF-8 未切数字"       "$(printf '%s' "$CB" | grep -c 'UTF-<span class="num">' || true)" '0'

# 根目录选错时（用上层目录启动）必须给出可操作的 --root 提示。
# 场景：以 md-preview 的上一层为根，此时根下没有 .md，但 md-preview/docs 里有。
python3 "$MDVIEW" --root "$ROOT/.." --port $((PORT+5)) --host 127.0.0.1 \
    >"$LOG.alt" 2>&1 &
ALT_PID=$!; PIDS="$PIDS $ALT_PID"
wait_ready $((PORT+5))
# 断言提示的**实质内容**（该用哪个 --root），不要写死脚本名 ——
# 用压缩版跑时提示会写 mdview.min.py，那是正确行为（按 sys.argv[0] 取名）。
chk "根目录选错时给出 --root 提示" "$(cat "$LOG.alt")" "--root md-preview/docs"
# 服务根绝对路径（/media/...）按定义依赖 --root 指向文档库根：这里明确断言其行为
chk "默认根下 /media 为 404（语义明确）" \
    "$(code "http://127.0.0.1:$((PORT+5))/media/logo.svg")" '404'
chk "改用 --root docs 后 /media 为 200"  "$(code "$BASE/media/logo.svg")" '200'

echo "== 源码/配置类文件按 UTF-8 文本发送（中文不能乱码） =="
SRCDIR="$(mktemp -d -t mdview-src)"
printf '# 中文注释\nname = "中文"\n'  > "$SRCDIR/code.py"
printf '# 中文注释\n'                   > "$SRCDIR/code.sh"
printf '// 中文注释\n'                  > "$SRCDIR/code.ts"
printf '# 中文注释\n'                   > "$SRCDIR/code.go"
printf '中文日志\n'                     > "$SRCDIR/code.log"
printf '[s]\nk=中文\n'                 > "$SRCDIR/code.ini"
printf '# 中文\nall:\n\techo 中文\n'  > "$SRCDIR/Makefile"
printf '\x89PNG\r\n\x1a\n\xff'      > "$SRCDIR/pic.png"
SRC_PID="$(serve_root "$((PORT+6))" "$SRCDIR")"
SRCB="http://127.0.0.1:$((PORT+6))"
for f in code.py code.sh code.ts code.go code.log code.ini Makefile; do
  chk "源码文本带 charset: $f" "$(curl -s -o /dev/null -w '%{content_type}' "$SRCB/$f")" 'charset=utf-8'
done
chk ".ts 判为文本而不是视频" "$(curl -s -o /dev/null -w '%{content_type}' "$SRCB/code.ts")" 'text/plain'
nchk ".ts 不能是 video"      "$(curl -s -o /dev/null -w '%{content_type}' "$SRCB/code.ts")" 'video/'
chk "二进制仍是图片类型"     "$(curl -s -o /dev/null -w '%{content_type}' "$SRCB/pic.png")" 'image/png'
# 声明的只是头：字节必须原样
PY_LOCAL="$(python3 -c "import hashlib;print(hashlib.sha256(open('$SRCDIR/code.py','rb').read()).hexdigest())")"
PY_SERVED="$(curl -s "$SRCB/code.py" | python3 -c "import hashlib,sys;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())")"
chk "源码文件字节原样"       "$PY_SERVED" "$PY_LOCAL"
{ kill "$SRC_PID" 2>/dev/null; wait "$SRC_PID" 2>/dev/null; }
rm -rf "$SRCDIR"

echo "== 代码块复制按钮（JS 注入，不产生死按钮） =="
CB2="$(curl -s "$BASE/guide/code-blocks.md")"
chk "页面内联了脚本"            "$CB2" 'createElement("button")'
chk "有 Clipboard API 路径"     "$CB2" 'navigator.clipboard'
chk "有 http 下的兜底路径"      "$CB2" 'execCommand'
chk "按钮一直显示（无隐藏态）"  "$CB2" '.copybtn{flex:none;background:none'
nchk "没有悬停淡入规则"          "$CB2" '.codeblock:hover .copybtn'
chk "顶部条为 flex 两端布局"    "$CB2" '.codebanner{display:flex'
chk "按钮注入到顶部条"          "$CB2" 'banner.appendChild(btn)'
chk "语言名在顶部条左侧"        "$CB2" '<span class="lang">'
# 关键：按钮不能出现在 HTML 里（否则禁用 JS 时是个点了没反应的死按钮）
nchk "HTML 里没有硬编码按钮"    "$CB2" 'class="copybtn"'
# 没有代码块的页面也必须能正常渲染（脚本不能报错）
chk "目录索引仍正常"            "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/")" '200'

echo "== 搜索跳转落点居中 =="
RAW2="$(curl -s "$BASE/index.md?raw=1")"
chk "源码视图有行锚点"          "$RAW2" 'id="L1"'
chk "有 scroll-margin 兜底"     "$RAW2" 'scroll-margin-top:20vh'
chk "有 scrollTo 居中逻辑"      "$RAW2" 'window.scrollTo'
chk "居中只在 L 锚点生效"       "$RAW2" "charAt(1) !== \"L\""
chk "上下边界做了夹紧"          "$RAW2" 'if (y > max) y = max;'
chk "已居中则不重复滚动"        "$RAW2" 'replaceState'

echo "== 裸 URL 自动链接（GFM autolink literal） =="
# 端到端确认：正文里手写的 http(s):// 真的产出可点的 <a>，且代码块里不受影响
ALDIR="$(mktemp -d -t mdview-autolink)"
cat > "$ALDIR/bare.md" <<'MDEOF'
正文 https://example.com/a 结束。

带查询串 https://e.com/x?a=1&b=2 结束。

括号 https://en.wikipedia.org/wiki/A_(b) 结束。

全角 https://e.com/a。结束。

中文 https://zh.wikipedia.org/wiki/中文条目 结束。

行内码 `https://e.com/code` 与尖括号 <https://e.com/angle>。

标签里 [见 https://e.com/label 说明](other.md)。

```text
https://e.com/fenced
```
MDEOF
AL_PID="$(serve_root "$((PORT+11))" "$ALDIR")"
ALB="http://127.0.0.1:$((PORT+11))"
AL="$(curl -s "$ALB/bare.md")"
chk "裸 URL 变可点"        "$AL" '<a href="https://example.com/a" rel="noreferrer noopener">https://example.com/a</a>'
chk "查询串只转义一次"     "$AL" 'href="https://e.com/x?a=1&amp;b=2"'
nchk "查询串不双重转义"    "$AL" '&amp;amp;'
chk "括号配平归 URL"       "$AL" 'href="https://en.wikipedia.org/wiki/A_(b)"'
chk "全角句号归句子"       "$AL" '</a>。结束'
chk "URL 里的中文保留"     "$AL" 'href="https://zh.wikipedia.org/wiki/中文条目"'
chk "行内码不链接化"       "$AL" '<code>https://e.com/code</code>'
nchk "行内码里无 <a>"      "$AL" '<code><a'
chk "围栏块不链接化"       "$AL" '>https://e.com/fenced</code>'
nchk "围栏块里无 <a>"      "$AL" '<code class="language-text"><a'
chk "尖括号自动链接仍在"   "$AL" '<a href="https://e.com/angle" rel="noreferrer noopener">https://e.com/angle</a>'
chk "标签里的 URL 不嵌套"  "$AL" '>见 https://e.com/label 说明</a>'
nchk "标签里没有嵌套 <a>"  "$AL" '<a href="https://e.com/label"'
{ kill "$AL_PID" 2>/dev/null; wait "$AL_PID" 2>/dev/null; }
rm -rf "$ALDIR"

echo "== 渲染样例（docs/preview）全部可访问且类型正确 =="
# 逐个请求索引页里链接的样例文件，任何一个不是 200 就算失败
PREV="$(curl -s "$BASE/preview/index.md")"
SAMPLE_FAIL=0; SAMPLE_N=0
for target in $(printf '%s' "$PREV" | grep -oE 'href="/preview/[^"#?]*"' \
                | sed -E 's/^href="//; s/"$//' | sort -u); do
  SAMPLE_N=$((SAMPLE_N+1))
  st="$(code "$BASE$target")"
  if [ "$st" != "200" ]; then
    printf '  \033[31mFAIL\033[0m %s -> HTTP %s\n' "$target" "$st"
    SAMPLE_FAIL=$((SAMPLE_FAIL+1))
  fi
done
if [ "$SAMPLE_FAIL" -eq 0 ]; then
  printf '  \033[32mok\033[0m   %d 个样例文件全部 200\n' "$SAMPLE_N"; pass=$((pass+1))
else
  fail=$((fail+1)); failed_names="$failed_names 样例文件"
fi
# 逐类型核对 Content-Type（这是"能否内联显示"的决定因素）
chk "样例 .py 为文本"        "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/code/sample.py")" 'text/plain; charset=utf-8'
chk "样例 .ts 不是视频"      "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/code/sample.ts")" 'text/plain'
nchk "样例 .ts 不含 video"   "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/code/sample.ts")" 'video/'
chk "样例 .ini 为文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/config/sample.ini")" 'text/plain'
chk "样例 .log 为文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/text/sample.log")" 'text/plain'
# Chrome 对 text/csv 一律下载，所以 csv 必须声明为 text/plain 才能内联
chk "样例 .csv 声明为 text/plain"   "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/text/sample.csv")" 'text/plain'
nchk "样例 .csv 不能是 text/csv"    "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/text/sample.csv")" 'text/csv'
chk "样例 .csv 带 charset"          "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/text/sample.csv")" 'charset=utf-8'
chk "无扩展名 Makefile"      "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/Makefile")" 'text/plain'
chk "点文件 .gitignore"      "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/.gitignore")" 'text/plain'
chk "样例 .png"              "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/media/sample.png")" 'image/png'
chk "样例 .gif"              "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/media/sample.gif")" 'image/gif'
chk "样例 .bmp"              "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/media/sample.bmp")" 'image/bmp'
chk "样例 .ico"              "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/media/sample.ico")" 'image/x-icon'
chk "样例 .svg"              "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/media/sample.svg")" 'image/svg'
# 图片必须是真文件（校验魔数），不能是占位文本
PNG_MAGIC="$(curl -s "$BASE/preview/media/sample.png" | head -c 8 | od -An -tx1 | tr -d ' \n')"
chk "PNG 魔数正确"           "$PNG_MAGIC" '89504e470d0a1a0a'
# 大样例图：放大视图「按视口缩放」只能靠比视口大的图验证，所以它必须是真 1600×900
chk "大样例 .png"            "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/media/sample-large.png")" 'image/png'
LARGE_MAGIC="$(curl -s "$BASE/preview/media/sample-large.png" | head -c 8 | od -An -tx1 | tr -d ' \n')"
chk "大图 PNG 魔数正确"      "$LARGE_MAGIC" '89504e470d0a1a0a'
# IHDR 的前 8 字节就是宽高（大端）：1600 = 0x640，900 = 0x384
LARGE_WH="$(curl -s "$BASE/preview/media/sample-large.png" | od -An -tx1 -j16 -N8 | tr -d ' \n')"
chk "大图尺寸 1600x900"      "$LARGE_WH" '0000064000000384'
chk "示例页大图包了放大链接" "$PREV" '<a class="zoom" href="/preview/media/sample-large.png">'
GIF_MAGIC="$(curl -s "$BASE/preview/media/sample.gif" | head -c 6)"
chk "GIF 魔数正确"           "$GIF_MAGIC" 'GIF89a'
chk "空文件可访问"           "$(code "$BASE/preview/text/empty.txt")" '200'
chk "GBK 文件声明了编码"     "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/text/gbk-encoded.txt")" 'charset='

echo "== 预览上限与无扩展名嗅探 =="
LIM="$(mktemp -d -t mdview-limit)"
# 无扩展名：文本 / 二进制（NUL 在 511 内）
printf '中文文本\n第二行\n' > "$LIM/plain"
printf 'DIRC\x00\x00\x01\xff' > "$LIM/binfile"
python3 -c "
open('$LIM/nul511','wb').write(b'A'*511 + b'\x00' + b'B'*50)
open('$LIM/nul512','wb').write(b'A'*512 + b'\x00' + b'B'*50)
open('$LIM/nulfar','wb').write(b'A'*5000 + b'\x00' + b'B'*50)
open('$LIM/gbk','wb').write('中文 GBK\n'.encode('gbk'))
"
# 有扩展名：不应被嗅探影响（内容含 NUL 也按文本发）
python3 -c "open('$LIM/weird.py','wb').write(b'\x00\x00\x00')"
# 大小：小文件与超过 20M 的文件
printf '# 小\n' > "$LIM/small.md"
# 用 ASCII 源码写 fixture（中文以 \u 转义，避免 b'...' 里出现非 ASCII）
python3 -c "
line = ('# \u4e2d\u6587\u6807\u9898\n').encode('utf-8')
n = (21*1024*1024)//len(line)
open('$LIM/big.md','wb').write(line*n)
# big.bin 要是真正的 21 MiB（不能复用上面算行数的 n）
with open('$LIM/big.bin','wb') as fh:
    fh.truncate(21*1024*1024)
"
LIM_PID="$(serve_root "$((PORT+7))" "$LIM")"
LIMB="http://127.0.0.1:$((PORT+7))"

chk "无扩展名文本 -> text/plain"  "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/plain")" 'text/plain'
chk "无扩展名文本 -> 不下载"      "$(curl -s -D - -o /dev/null "$LIMB/plain" | grep -ci 'content-disposition')" '0'
chk "无扩展名含 NUL -> 二进制"    "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/binfile")" 'application/octet-stream'
chk "NUL 在 511 -> 二进制"        "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/nul511")" 'application/octet-stream'
chk "NUL 在 512 -> 文本"          "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/nul512")" 'text/plain'
chk "NUL 在 5000 -> 文本"         "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/nulfar")" 'text/plain'
chk "无扩展名 GBK -> 仍算文本"    "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/gbk")" 'text/plain'
chk "有扩展名不被嗅探影响"        "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/weird.py")" 'text/plain'

chk "超限 .md -> 保留准确类型"    "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/big.md")" 'text/markdown'
chk "超限 .md -> 附件下载"        "$(curl -s -D - -o /dev/null "$LIMB/big.md" | grep -ci 'content-disposition: attachment')" '1'
chk "超限 .md?raw=1 -> 也下载"    "$(curl -s -D - -o /dev/null "$LIMB/big.md?raw=1" | grep -ci 'content-disposition: attachment')" '1'
chk "超限二进制 -> 也下载"        "$(curl -s -D - -o /dev/null "$LIMB/big.bin" | grep -ci 'content-disposition: attachment')" '1'
chk "小 .md 仍正常渲染"           "$(curl -s -o /dev/null -w '%{content_type}' "$LIMB/small.md")" 'text/html'
chk "附件头含 filename"         "$(curl -s -D - -o /dev/null "$LIMB/big.md" | grep -ci 'filename=')" '1'
{ kill "$LIM_PID" 2>/dev/null; wait "$LIM_PID" 2>/dev/null; }
rm -rf "$LIM"

# --max-preview 参数解析
chk "--max-preview 非法值被拒"    "$(python3 "$MDVIEW" --max-preview abc 2>&1 | grep -c '无法解析')" '1'
chk "--max-preview 0 表示不限制"  "$(python3 -c "import sys; sys.path.insert(0,'$ROOT'); import mdview; print(mdview._parse_size('0'))")" '0'
chk "--max-preview 单位解析"      "$(python3 -c "import sys; sys.path.insert(0,'$ROOT'); import mdview; print(mdview._parse_size('512K'))")" '524288'

echo "== 二进制/超大测试样例（docs/preview/binary 与 large）=="
BIN="$BASE/preview/binary"; LRG="$BASE/preview/large"
# 无扩展名：512 字节边界
chk "noext 文本 -> 预览"       "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_text")" 'text/plain'
chk "noext 空文件 -> 预览"     "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_empty")" 'text/plain'
chk "noext GBK -> 仍算文本"    "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_gbk")" 'text/plain'
chk "NUL@0 -> 二进制"          "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_nul_at_0")" 'application/octet-stream'
chk "NUL@511 -> 二进制"        "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_nul_at_511")" 'application/octet-stream'
chk "NUL@512 -> 文本"          "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_nul_at_512")" 'text/plain'
chk "NUL@5000 -> 文本"         "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_nul_at_5000")" 'text/plain'
chk "随机数据 -> 二进制"       "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/noext_random")" 'application/octet-stream'
# 真二进制格式
chk "真 PNG -> image/png"      "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/real.png")" 'image/png'
chk "真 PDF -> application/pdf" "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/real.pdf")" 'application/pdf'
chk "真 ZIP -> octet-stream"   "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/real.zip")" 'application/octet-stream'
chk "ELF 头 -> octet-stream"   "$(curl -s -o /dev/null -w '%{content_type}' "$BIN/fake.elf")" 'application/octet-stream'
# PNG 魔数必须是真图
PNG2="$(curl -s "$BIN/real.png" | head -c 8 | od -An -tx1 | tr -d ' \n')"
chk "真 PNG 魔数正确"          "$PNG2" '89504e470d0a1a0a'
chk "真 PDF 魔数正确"          "$(curl -s "$BIN/real.pdf" | head -c 5)" '%PDF-'
chk "真 ZIP 魔数正确"          "$(curl -s "$BIN/real.zip" | head -c 2)" 'PK'
# 超大（稀疏文件）：每种类型都要变成下载
for f in big.md big.txt big.bin big.png noext_big; do
  chk "超大 $f -> 附件下载"    "$(curl -s -D - -o /dev/null "$LRG/$f" | grep -ci 'content-disposition: attachment')" '1'
done
chk "超大 .md 保留类型"        "$(curl -s -o /dev/null -w '%{content_type}' "$LRG/big.md")" 'text/markdown'
chk "超大 .png 保留类型"       "$(curl -s -o /dev/null -w '%{content_type}' "$LRG/big.png")" 'image/png'
chk "超大 ?raw=1 也下载"       "$(curl -s -D - -o /dev/null "$LRG/big.md?raw=1" | grep -ci 'content-disposition: attachment')" '1'
chk "附件头含 filename"        "$(curl -s -D - -o /dev/null "$LRG/big.md" | grep -ci 'filename=')" '1'
# 测试页本身可访问，且里面没有断链
chk "测试页可访问"             "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/preview/binary-test.md")" '200'

echo "== 下载按钮（?download=1）=="
DL="$(curl -s "$BASE/preview/")"
chk "目录索引含下载链接"      "$DL" 'download=1'
chk "下载按钮有 title"        "$DL" 'title="下载'
chk "下载按钮有 aria-label"   "$DL" 'aria-label="下载'
# 目录行不该有下载链接
nchk "目录行无下载按钮"       "$DL" '📁 <a href="/preview/binary/">binary</a></span><span class="meta">目录</span><a class="dl"'
# 各种类型走 ?download=1 都必须带附件头，且类型不退化
for u in "preview/binary-test.md" "preview/code/sample.py" "preview/binary/real.png" \
         "preview/binary/real.zip" "preview/media/sample.gif" "preview/large/big.md"; do
  chk "下载头: $u"   "$(curl -s -D - -o /dev/null "$BASE/$u?download=1" | grep -ci 'content-disposition: attachment')" '1'
done
chk "下载 .md 保留 text/markdown" "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/binary-test.md?download=1")" 'text/markdown'
chk "下载 .png 保留 image/png"    "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/binary/real.png?download=1")" 'image/png'
chk "下载 .py 保留 text/plain"    "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/preview/code/sample.py?download=1")" 'text/plain'
# .md 走下载必须返回原始 Markdown，而不是渲染后的 HTML
chk ".md 下载返回原文"        "$(curl -s "$BASE/preview/binary-test.md?download=1" | head -1)" '# 二进制 / 超大文件测试'
nchk ".md 下载不含 HTML 标签" "$(curl -s "$BASE/preview/binary-test.md?download=1" | head -3)" '<html'
# 不加参数时仍然是预览
nchk "不带参数时不下载"       "$(curl -s -D - -o /dev/null "$BASE/preview/code/sample.py" | grep -ci 'content-disposition')" '1'

echo "== 下载头的文件名（实测裸 attachment 会被浏览器改名）=="
DISP() { curl -s -D - -o /dev/null "$1" | grep -i '^content-disposition' | tr -d '\r'; }
chk ".md 下载带 filename"      "$(DISP "$BASE/preview/binary-test.md?download=1" | grep -c 'filename="binary-test.md"')" '1'
chk ".md 下载带 filename*"     "$(DISP "$BASE/preview/binary-test.md?download=1" | grep -c "filename\*=UTF-8''")" '1'
chk "点文件带 filename"        "$(DISP "$BASE/preview/.gitignore?download=1" | grep -c 'filename=".gitignore"')" '1'
chk "超大文件也带 filename"    "$(DISP "$BASE/preview/large/big.md?download=1" | grep -c 'filename="big.md"')" '1'
chk "非 ASCII 名不进 filename"  "$(DISP "$BASE/preview/%E7%BC%96%E7%A0%81.txt?download=1" | grep -c 'filename="[^"]*[^\x00-\x7f]')" '0'
# 头必须能按 latin-1 编码（含中文会直接 500 / 连接断开）
chk "含中文名的下载不崩"       "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/preview/.gitignore?download=1")" '200'

echo "== 修复回归：单响应 / 重定向编码 / 文件类型 / 符号链接 / 搜索上限 =="
# B2：一个 ?raw=1 请求只能有一个响应（曾经写出 200 + 残缺 200 + 500 三个）
chk "?raw=1 只写一个响应"     "$(count_responses "$BASE" "/index.md?raw=1")" '1'
nchk "?raw=1 不再出现 500"    "$(curl -s "$BASE/index.md?raw=1" | grep -c '500 detail')" '1'
chk "?raw=1 仍是 200"         "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/index.md?raw=1")" '200'
chk "不可读 .md 也只一个响应" "$(count_responses "$BASE" "/nope-404.md")" '1'

# B3：重定向 Location 不能双重编码（空格与中文目录）
B3DIR="$(mktemp -d -t mdview-b3)"
mkdir -p "$B3DIR/my dir" "$B3DIR/中文目录"
printf '# in\n' > "$B3DIR/my dir/a.md"
printf '# 中文\n' > "$B3DIR/中文目录/n.md"
B3PID="$(serve_root "$((PORT+8))" "$B3DIR")"; B3B="http://127.0.0.1:$((PORT+8))"
chk "空格目录 301"           "$(curl -s -o /dev/null -w '%{http_code}' "$B3B/my%20dir")" '301'
chk "Location 单次编码"      "$(curl -s -D - -o /dev/null "$B3B/my%20dir" | grep -i '^location' | tr -d '\r' | cut -d' ' -f2-)" '/my%20dir/'
chk "跟随后可访问"           "$(curl -s -L -o /dev/null -w '%{http_code}' "$B3B/my%20dir")" '200'
nchk "Location 无 %25"       "$(curl -s -D - -o /dev/null "$B3B/my%20dir" | grep -ci '%25')" '1'
chk "中文目录 301"           "$(curl -s -o /dev/null -w '%{http_code}' "$B3B/%E4%B8%AD%E6%96%87%E7%9B%AE%E5%BD%95")" '301'
chk "中文目录跟随后 200"     "$(curl -s -L -o /dev/null -w '%{http_code}' "$B3B/%E4%B8%AD%E6%96%87%E7%9B%AE%E5%BD%95")" '200'
chk "中文文件源的链接可用"   "$(curl -s -o /dev/null -w '%{http_code}' "$B3B/%E4%B8%AD%E6%96%87%E7%9B%AE%E5%BD%95/n.md?raw=1")" '200'
{ kill "$B3PID" 2>/dev/null; wait "$B3PID" 2>/dev/null; }
rm -rf "$B3DIR"

# B5/B6：FIFO 与符号链接
B56DIR="$(mktemp -d -t mdview-b56)"
printf 'ok\n' > "$B56DIR/real.txt"
mkfifo "$B56DIR/pipe" 2>/dev/null
ln -sf /etc/passwd "$B56DIR/escape" 2>/dev/null
ln -sf "$B56DIR/real.txt" "$B56DIR/alias.txt" 2>/dev/null
B56PID="$(serve_root "$((PORT+9))" "$B56DIR")"; B56B="http://127.0.0.1:$((PORT+9))"
chk "FIFO 立刻 404"          "$(curl -s -m 4 -o /dev/null -w '%{http_code}' "$B56B/pipe")" '404'
chk "FIFO 用时 <1 秒"        "$(curl -s -m 4 -o /dev/null -w '%{time_total}' "$B56B/pipe" | cut -d. -f1)" '0'
chk "符号链接逃逸 403"       "$(curl -s -o /dev/null -w '%{http_code}' "$B56B/escape")" '403'
chk "root 内符号链接可用"    "$(curl -s -o /dev/null -w '%{http_code}' "$B56B/alias.txt")" '200'
chk "常规文件仍 200"         "$(curl -s -o /dev/null -w '%{http_code}' "$B56B/real.txt")" '200'
{ kill "$B56PID" 2>/dev/null; wait "$B56PID" 2>/dev/null; }
rm -rf "$B56DIR"

# B7：搜索跳过超限文件（与 --max-preview 一致）
B7DIR="$(mktemp -d -t mdview-b7)"
printf '关键词ZZZ命中\n' > "$B7DIR/small.md"
python3 -c 'line = ("# \u5173\u952e\u8bcdZZZ\n").encode(); open("'"$B7DIR"'/huge.md", "wb").write(line * ((21*1024*1024)//len(line)))'
B7PID="$(serve_root "$((PORT+10))" "$B7DIR")"; B7B="http://127.0.0.1:$((PORT+10))"
SR="$(curl -s --get --data-urlencode 'q=关键词ZZZ' "$B7B/search")"
chk "搜索仍能找到小文件"     "$(printf '%s' "$SR" | grep -c 'small.md')" '1'
chk "搜索跳过超限文件"       "$(printf '%s' "$SR" | grep -c 'huge.md')" '0'
{ kill "$B7PID" 2>/dev/null; wait "$B7PID" 2>/dev/null; }
rm -rf "$B7DIR"

# B9：客户端中断不再刷 traceback
curl -s --limit-rate 100k --max-time 0.2 -o /dev/null "$BASE/preview/large/big.txt" 2>/dev/null || true
sleep 0.5
chk "断开不刷 traceback"     "$(grep -c 'Traceback' "$LOG" 2>/dev/null || echo 0)" '0'

# B10：markdown 目标路径的编码规则（空格 / 字面 % / 文件名里含 #）
#      坏过的样子：图片目标被编码两次（%20 -> %2520），图片 404；
#      链接先解码后切 ?/#，文件名含 # 的文件链不到。
B10DIR="$(mktemp -d -t mdview-b10)"
mkdir -p "$B10DIR/img dir"
printf '\211PNG\r\n\032\n' > "$B10DIR/img dir/nested pic.png"
printf '\211PNG\r\n\032\n' > "$B10DIR/带 空格.png"
printf '\211PNG\r\n\032\n' > "$B10DIR/x%20y.png"          # 文件名里字面的 %20
printf '# hash\n' > "$B10DIR/a#b.md"
printf '![a](img%%20dir/nested%%20pic.png)\n\n![b](带%%20空格.png)\n\n![c](<img dir/nested pic.png>)\n\n![d](img dir/nested pic.png)\n\n![e][ref]\n\n[x](a%%23b.md)\n\n[y](a b.md)\n\n[ref]: img%%20dir/nested%%20pic.png\n' \
    > "$B10DIR/doc.md"
printf '![b](x%%2520y.png)\n' > "$B10DIR/literal.md"
B10PID="$(serve_root "$((PORT+15))" "$B10DIR")"; B10B="http://127.0.0.1:$((PORT+15))"
P10="$(curl -s "$B10B/doc.md")"
chk "空格目录图片单次编码"   "$P10" 'src="/img%20dir/nested%20pic.png"'
chk "空格文件名图片可取"     "$(code "$B10B/img%20dir/nested%20pic.png")" '200'
chk "中文+空格文件名编码"    "$P10" 'src="/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png"'
chk "中文+空格图片可取"      "$(code "$B10B/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png")" '200'
nchk "渲染结果里没有 %25"    "$P10" '%25'
chk "含 # 的文件名按 %23 输出" "$P10" 'href="/a%23b.md"'
chk "含 # 的文件可取"        "$(code "$B10B/a%23b.md")" '200'
# 尖括号写法、百分号写法、引用式定义三条路必须收敛到同一个 src
chk "三种写法渲染出同一个 src" \
    "$(printf '%s' "$P10" | grep -o 'src="/img%20dir/nested%20pic.png"' | wc -l | tr -d ' ')" '3'
chk "裸空格图片退化成字面文本" "$P10" '![d](img dir/nested pic.png)'
chk "裸空格链接退化成字面文本" "$P10" '[y](a b.md)'
L10="$(curl -s "$B10B/literal.md")"
chk "字面 %20 文件名写 %2520" "$L10" 'src="/x%2520y.png"'
chk "字面 %20 文件可取"      "$(code "$B10B/x%2520y.png")" '200'
chk "断链仍然 404（对照）"   "$(code "$B10B/nope.png")" '404'
{ kill "$B10PID" 2>/dev/null; wait "$B10PID" 2>/dev/null; }
rm -rf "$B10DIR"

# B11：docs/media 里那个真的带空格文件（尖括号 + %20 两种写法在示例页里各出现一次）
#      断链巡检会顺带请求它们，这里再明确断言一次渲染结果。
GD="$(curl -s "$BASE/guide/install.md")"
chk "示例页尖括号写法"       "$GD" 'src="/media/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png"'
chk "带空格示例图可取"       "$(code "$BASE/media/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png")" '200'

echo "== 上级目录链接（根边界：不能出现 //）=="
PL="$(mktemp -d -t mdview-parent)"
mkdir -p "$PL/lvl1/lvl2"
printf '# a\n' > "$PL/lvl1/a.md"
printf '# b\n' > "$PL/lvl1/lvl2/b.md"
printf '# top\n' > "$PL/top.md"
PLPID="$(serve_root "$((PORT+11))" "$PL")"; PLB="http://127.0.0.1:$((PORT+11))"
chk "根目录页无上级链接"     "$(curl -s "$PLB/" | grep -c '上级目录')" '0'
chk "一级子目录上级是 /"     "$(curl -s "$PLB/lvl1/" | grep -o 'href="[^"]*">\.\./ 上级目录' | sed 's/href="//; s/">.*//')" '/'
nchk "一级子目录不出现 //"   "$(curl -s "$PLB/lvl1/" | grep -ci 'href="//"')" '1'
chk "二级子目录上级是 /lvl1/" "$(curl -s "$PLB/lvl1/lvl2/" | grep -o 'href="[^"]*">\.\./ 上级目录' | sed 's/href="//; s/">.*//')" '/lvl1/'
chk "点上级能回到根（200）"  "$(curl -s -o /dev/null -w '%{http_code}' "$PLB/")" '200'
# 全站目录页里不允许出现 href="//"
nchk "目录页无 // 链接"      "$(for d in / /lvl1/ /lvl1/lvl2/; do curl -s "$PLB$d"; done | grep -ci 'href="//"')" '1'
{ kill "$PLPID" 2>/dev/null; wait "$PLPID" 2>/dev/null; }
rm -rf "$PL"

echo "== 生态白名单（前端/Java/.NET 常见文件）=="
ECO="$(mktemp -d -t mdview-eco)"
for f in yarn.lock bun.lock Pipfile.lock poetry.lock Cargo.lock go.sum go.mod \
         build.gradle settings.gradle gradle.properties build.gradle.kts \
         settings.gradle.kts gradlew mvnw Makefile.in configure.ac \
         rollup.config.mjs project.pbxproj Package.resolved; do
  printf 'text\n' > "$ECO/$f"
done
printf 'text\n' > "$ECO/MANIFEST.MF"; printf 'text\n' > "$ECO/App.csproj"
printf 'text\n' > "$ECO/proj.sln"; printf 'text\n' > "$ECO/Directory.Build.props"
printf 'text\n' > "$ECO/props.resx"; printf 'text\n' > "$ECO/.pnpmfile.cjs"
printf 'text\n' > "$ECO/.terraform.lock.hcl"
# 反例：bun.lockb 是二进制锁文件，必须仍然下载
printf 'bun-lockb\x01\x00\x00\x00\x00\x00' > "$ECO/bun.lockb"
ECOPID="$(serve_root "$((PORT+12))" "$ECO")"; ECOB="http://127.0.0.1:$((PORT+12))"
ECOBAD=0
for f in yarn.lock bun.lock Pipfile.lock poetry.lock Cargo.lock go.sum go.mod \
         build.gradle settings.gradle gradle.properties build.gradle.kts \
         settings.gradle.kts gradlew mvnw Makefile.in configure.ac \
         rollup.config.mjs project.pbxproj Package.resolved \
         MANIFEST.MF App.csproj proj.sln Directory.Build.props props.resx \
         .pnpmfile.cjs .terraform.lock.hcl; do
  ct="$(curl -s -o /dev/null -w '%{content_type}' "$ECOB/$f")"
  if [ "$ct" != "text/plain; charset=utf-8" ]; then
    printf '  \033[31mFAIL\033[0m %s -> %s\n' "$f" "$ct"; ECOBAD=$((ECOBAD+1))
  fi
done
if [ "$ECOBAD" -eq 0 ]; then
  printf '  \033[32mok\033[0m   26 个生态文件均为文本\n'; pass=$((pass+1))
else
  fail=$((fail+1)); failed_names="$failed_names 生态白名单"
fi
chk "bun.lockb 仍是二进制"    "$(curl -s -o /dev/null -w '%{content_type}' "$ECOB/bun.lockb")" 'application/octet-stream'
chk "package.json 仍是 JSON"  "$(printf '{}' > "$ECO/package.json"; curl -s -o /dev/null -w '%{content_type}' "$ECOB/package.json")" 'application/json; charset=utf-8'
chk "pom.xml 仍是 XML"        "$(printf '<a/>' > "$ECO/pom.xml"; curl -s -o /dev/null -w '%{content_type}' "$ECOB/pom.xml")" 'application/xml; charset=utf-8'
{ kill "$ECOPID" 2>/dev/null; wait "$ECOPID" 2>/dev/null; }
rm -rf "$ECO"

echo "== 第三层兜底：没登记过的文本也能预览（嗅探）=="
SN="$(mktemp -d -t mdview-sniff)"
printf '纯文本，无 NUL\n' > "$SN/weird.random"
printf 'another unknown ext\n' > "$SN/notes.xyz"
printf '<?xml version="1.0"?><plist/>\n' > "$SN/x.plist"
printf 'no extension text\n' > "$SN/noext_plain"
printf 'header\x00\x01binary' > "$SN/blob.dat"
printf 'header\x00\x01binary' > "$SN/noext_binary"
printf '\x89PNG\r\n\x1a\n' > "$SN/fake.png"
printf 'x\x00\x00' > "$SN/weird.py"
SNPID="$(serve_root "$((PORT+13))" "$SN")"; SNB="http://127.0.0.1:$((PORT+13))"
chk "未知扩展名文本 -> 预览"   "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/weird.random")" 'text/plain; charset=utf-8'
chk "另一个未知扩展名"        "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/notes.xyz")" 'text/plain; charset=utf-8'
chk "文本 .plist -> 预览"     "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/x.plist")" 'text/plain; charset=utf-8'
chk "无扩展名文本 -> 预览"    "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/noext_plain")" 'text/plain; charset=utf-8'
chk "未知扩展名含 NUL -> 下载" "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/blob.dat")" 'application/octet-stream'
chk "无扩展名含 NUL -> 下载"  "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/noext_binary")" 'application/octet-stream'
# 前两层优先：白名单即使内容含 NUL 也按文本；MIME 表保住图片类型
chk "白名单优先（含 NUL 的 .py）" "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/weird.py")" 'text/plain; charset=utf-8'
chk "MIME 表优先（.png 类型不变）" "$(curl -s -o /dev/null -w '%{content_type}' "$SNB/fake.png")" 'image/png'
{ kill "$SNPID" 2>/dev/null; wait "$SNPID" 2>/dev/null; }
rm -rf "$SN"

# 基线回归：对着**真实服务**逐个核对各类文件的 Content-Type 判定，
# 确保"加嗅探兜底"没有改变已登记类型的既有行为。
echo "== 基线回归：已登记类型的判定不变 =="
BR="$(mktemp -d -t mdview-base)"
printf '# 标题\n' > "$BR/a.md"
printf 'x = 1\n' > "$BR/a.py"
printf 'plain\n' > "$BR/a.txt"
printf '{}\n' > "$BR/a.json"
printf '<a/>\n' > "$BR/a.xml"
printf 'a,b\n' > "$BR/a.csv"
printf 'k: v\n' > "$BR/a.yaml"
printf 'k=1\n' > "$BR/a.ini"
printf 'x\n' > "$BR/a.log"
printf '\x89PNG\r\n\x1a\n' > "$BR/a.png"
printf 'GIF89a\n' > "$BR/a.gif"
printf '%%PDF-1.4\n' > "$BR/a.pdf"
printf '<svg/>\n' > "$BR/a.svg"
printf 'body{}\n' > "$BR/a.css"
printf 'var a=1;\n' > "$BR/a.js"
printf '# 中文\nall:\n' > "$BR/Makefile"
printf 'FROM x\n' > "$BR/Dockerfile"
BRPID="$(serve_root "$((PORT+14))" "$BR")"; BRB="http://127.0.0.1:$((PORT+14))"
chk "基线 .md 渲染"        "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.md")" 'text/html; charset=utf-8'
chk "基线 .py 文本"        "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.py")" 'text/plain; charset=utf-8'
chk "基线 .txt 文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.txt")" 'text/plain; charset=utf-8'
chk "基线 .json 类型"      "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.json")" 'application/json; charset=utf-8'
chk "基线 .xml 类型"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.xml")" 'application/xml; charset=utf-8'
chk "基线 .csv 文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.csv")" 'text/plain; charset=utf-8'
chk "基线 .yaml 文本"      "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.yaml")" 'text/plain; charset=utf-8'
chk "基线 .ini 文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.ini")" 'text/plain; charset=utf-8'
chk "基线 .log 文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.log")" 'text/plain; charset=utf-8'
chk "基线 .png 图片"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.png")" 'image/png'
chk "基线 .gif 图片"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.gif")" 'image/gif'
chk "基线 .pdf 类型"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.pdf")" 'application/pdf'
chk "基线 .svg 图片"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.svg")" 'image/svg+xml'
chk "基线 .css 文本"       "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.css")" 'text/css; charset=utf-8'
chk "基线 .js 类型"        "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/a.js")" 'text/javascript; charset=utf-8'
chk "基线 Makefile 文本"   "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/Makefile")" 'text/plain; charset=utf-8'
chk "基线 Dockerfile 文本" "$(curl -s -o /dev/null -w '%{content_type}' "$BRB/Dockerfile")" 'text/plain; charset=utf-8'
{ kill "$BRPID" 2>/dev/null; wait "$BRPID" 2>/dev/null; }
rm -rf "$BR"

echo "== 参数开关（另起临时实例） =="

{ kill "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID" 2>/dev/null; } ; sleep 0.3

# --safe：只放行 .md 与图片
SAFE_PID="$(serve_temp $((PORT+1)) /dev/null --safe)"
chk "safe: .md 仍可读"    "$(code "http://127.0.0.1:$((PORT+1))/index.md")" '200'
chk "safe: 图片仍可读"    "$(code "http://127.0.0.1:$((PORT+1))/media/logo.svg")" '200'
chk "safe: 其他文件 404"  "$(code "http://127.0.0.1:$((PORT+1))/../mdview.py")" '404'
{ kill "$SAFE_PID" 2>/dev/null; wait "$SAFE_PID" 2>/dev/null; } ; sleep 0.3

# --no-search：搜索路由与界面搜索框都要消失
NS_PID="$(serve_temp $((PORT+2)) /dev/null --no-search)"
NSB="http://127.0.0.1:$((PORT+2))"
chk "no-search: /search 404" "$(code "$NSB/search?q=x")" '404'
nchk "no-search: 无搜索框"   "$(curl -s "$NSB/")" 'name="q"'
nchk "no-search: 文档页也无" "$(curl -s "$NSB/index.md")" 'name="q"'
{ kill "$NS_PID" 2>/dev/null; wait "$NS_PID" 2>/dev/null; } ; sleep 0.3

# 端口占用自动回退
P1="$(serve_temp $((PORT+3)) /dev/null)"
python3 "$MDVIEW" --root "$ROOT/docs" --port $((PORT+3)) --host 127.0.0.1 \
    >"$LOG.fallback" 2>&1 &
P2=$!; PIDS="$PIDS $P2"
wait_ready $((PORT+4))
chk "端口占用自动回退"    "$(cat "$LOG.fallback")" "尝试 $((PORT+4))"
chk "回退后端口可用"      "$(code "http://127.0.0.1:$((PORT+4))/")" '200'
{ kill "$P1" "$P2" 2>/dev/null; wait "$P1" "$P2" 2>/dev/null; }

echo
printf 'PASS=%d FAIL=%d\n' "$pass" "$fail"
if [ "$fail" -gt 0 ]; then
  printf '失败项:%s\n' "$failed_names"
  exit 1
fi
echo "全部通过 ✔  服务日志: $LOG"
