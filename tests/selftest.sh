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
  python3 "$ROOT/mdview.py" --root "$ROOT/docs" --port "$port" --host 127.0.0.1 "$@" \
      >"$log" 2>&1 &
  local pid=$!
  PIDS="$PIDS $pid"
  wait_ready "$port"
  printf '%s' "$pid"
}

SERVER_PID="$(serve_temp "$PORT" "$LOG")"

# 指定任意 root 起临时实例：serve_root <端口> <root> [额外参数...]
serve_root() {
  local port="$1" root="$2"; shift 2
  python3 "$ROOT/mdview.py" --root "$root" --port "$port" --host 127.0.0.1 "$@" \
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
python3 "$ROOT/mdview.py" --root "$ROOT/.." --port $((PORT+5)) --host 127.0.0.1 \
    >"$LOG.alt" 2>&1 &
ALT_PID=$!; PIDS="$PIDS $ALT_PID"
wait_ready $((PORT+5))
chk "根目录选错时给出 --root 提示" "$(cat "$LOG.alt")" "python3 mdview.py --root md-preview/docs"
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
python3 "$ROOT/mdview.py" --root "$ROOT/docs" --port $((PORT+3)) --host 127.0.0.1 \
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
