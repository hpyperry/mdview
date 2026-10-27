#!/usr/bin/env bash
# Black-box HTTP tests for the Rust mdview binary.
#
# Usage:
#   bash tests/selftest-rust.sh
#   MDVIEW_BIN=target/release/mdview PORT=9400 bash tests/selftest-rust.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${MDVIEW_BIN:-}"
BASE_PORT="${PORT:-$((20000 + RANDOM % 10000))}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mdview-rust-selftest.XXXXXX")"
ROOT="$TMP/root"
PIDS=()
PASS=0
FAIL=0

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  done
  rm -rf "$TMP"
}
trap cleanup EXIT

ok() { PASS=$((PASS + 1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
chk() {
  local name="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then ok "$name"; else bad "$name (missing: $needle)"; fi
}
nchk() {
  local name="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then bad "$name (unexpected: $needle)"; else ok "$name"; fi
}
chk_num() {
  local name="$1" actual="$2" expected="$3"
  if [ "$actual" -eq "$expected" ] 2>/dev/null; then ok "$name"; else bad "$name (expected $expected, got $actual)"; fi
}
count() { printf '%s' "$1" | grep -oF -- "$2" | wc -l | tr -d ' ' || true; }
code() { curl -s -o /dev/null -w '%{http_code}' "$1"; }
ctype() { curl -s -o /dev/null -w '%{content_type}' "$1"; }
header() {
  local url="$1" name="$2"
  curl -s -D - -o /dev/null "$url" | tr -d '\r' | awk -v n="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')" \
    'tolower($0) ~ "^" n ":" {sub(/^[^:]+:[[:space:]]*/, ""); print; exit}'
}

start_server_at() {
  local port="$1" root="$2"; shift 2
  "$BIN" --root "$root" --host 127.0.0.1 --port "$port" "$@" \
    >"$TMP/server-$port.log" 2>&1 &
  PIDS+=("$!")
}
start_server() {
  local port="$1"; shift
  start_server_at "$port" "$ROOT" "$@"
}

wait_http() {
  local port="$1"
  for _ in $(seq 1 80); do
    if curl -sf "http://127.0.0.1:$port/" >/dev/null 2>&1; then return 0; fi
    sleep 0.1
  done
  return 1
}

# --- fixture -------------------------------------------------------------
mkdir -p "$ROOT/sub" "$ROOT/empty" "$ROOT/my dir" "$ROOT/中文目录" \
  "$ROOT/img dir" "$ROOT/.hidden" "$ROOT/node_modules"
cat >"$ROOT/a.md" <<'MD'
# Hello

**bold** 与 ~~del~~

- [x] task

<div id="raw">raw</div>

见 https://example.com/a。结束

| a | b |
|:--|--:|
| 1 | 2 |
MD
printf '# Child\n\nneedle in child\n' >"$ROOT/sub/c.md"
printf '<h1>SUB INDEX</h1>\n' >"$ROOT/sub/index.html"
printf 'hello\nworld\n' >"$ROOT/b.txt"
awk 'BEGIN { for (i = 1; i <= 11999; i++) print "line with some text 0123456789"; printf "last line marker" }' >"$ROOT/big.txt"
printf 'needle in text\n' >"$ROOT/search.md"
printf 'a real search file\n' >"$ROOT/search"
printf 'a real nav file\n' >"$ROOT/_nav"
mkdir -p "$ROOT/_assets"
printf 'a real app css\n' >"$ROOT/_assets/app.css"
printf '# Markdown Ext\n\nmarkdownneedle\n' >"$ROOT/a.markdown"
printf '# MDX\n\n<Component />\n' >"$ROOT/a.mdx"
cp "$REPO_ROOT/tests/fixtures/encodings/gbk.md" "$ROOT/gbk.md"
cp "$REPO_ROOT/tests/fixtures/encodings/gbk.txt" "$ROOT/gbk.txt"
cp "$REPO_ROOT/tests/fixtures/encodings/gbk.css" "$ROOT/gbk.css"
cp "$REPO_ROOT/tests/fixtures/encodings/utf16le.txt" "$ROOT/utf16le.txt"
cp "$REPO_ROOT/tests/fixtures/encodings/utf32le.txt" "$ROOT/utf32le.txt"
printf '\211PNG\r\n\032\n' >"$ROOT/img.png"
printf 'abc\0def' >"$ROOT/bin.dat"
printf '# in space dir\n' >"$ROOT/my dir/a.md"
printf '# 中文\n' >"$ROOT/中文目录/n.md"
printf '\211PNG\r\n\032\n' >"$ROOT/img dir/nested pic.png"
printf '\211PNG\r\n\032\n' >"$ROOT/带 空格.png"
printf '# hash\n' >"$ROOT/a#b.md"
printf 'extensionless text\n' >"$ROOT/README"
printf 'binary\0bytes' >"$ROOT/noextbin"
printf '{"a":1}\n' >"$ROOT/data.json"
printf 'key: value\n' >"$ROOT/config.yaml"
printf 'all:\n\techo hi\n' >"$ROOT/Makefile"
printf 'FROM scratch\n' >"$ROOT/Dockerfile"
printf 'node_modules/\n' >"$ROOT/.gitignore"
printf 'const x: number = 1;\n' >"$ROOT/app.ts"
printf '中文内容\n' >"$ROOT/中文 文件.txt"
printf '关键词在这里\n' >"$ROOT/关键词.md"
printf 'CaseNeedle body\n' >"$ROOT/CaseNeedle.md"
printf 'HIDDENNEEDLE\n' >"$ROOT/.hidden/h.md"
printf 'HIDDENNEEDLE\n' >"$ROOT/node_modules/n.md"
cp "$REPO_ROOT/tests/fixtures/archives/sample.zip" "$ROOT/sample.zip"
cp "$REPO_ROOT/tests/fixtures/archives/sample.tar.gz" "$ROOT/sample.tar.gz"
cp "$REPO_ROOT/tests/fixtures/archives/sample.7z" "$ROOT/sample.7z"
cat >"$ROOT/page.html" <<'HTML'
<!doctype html><html><head><meta charset="utf-8"><title>HTML Probe</title><link rel="stylesheet" href="style.css"></head><body><h1>HTML Probe</h1><p>htmlneedle</p><script>document.body.dataset.script='yes'</script></body></html>
HTML
printf 'body { color: rgb(1, 2, 3); }\n' >"$ROOT/style.css"
printf '<svg xmlns="http://www.w3.org/2000/svg"><script>document.documentElement.dataset.x=1</script></svg>\n' >"$ROOT/evil.svg"
cat >"$ROOT/links.md" <<'MD'
![a](img%20dir/nested%20pic.png)

![b](带%20空格.png)

![c](<img dir/nested pic.png>)

[x](a%23b.md)

[y](<my dir/a.md>)
MD

echo "== build =="
cargo build --release --quiet --manifest-path "$REPO_ROOT/Cargo.toml"
if [ -z "$BIN" ]; then
  BIN="$REPO_ROOT/target/release/mdview"
  [ -x "$BIN" ] || BIN="$BIN.exe"
fi
[ -x "$BIN" ] || { echo "missing binary: $BIN"; exit 2; }

echo "== trusted server =="
TRUST_PORT="$BASE_PORT"
start_server "$TRUST_PORT" --trust
if ! wait_http "$TRUST_PORT"; then
  echo "server failed to start"; cat "$TMP/server-$TRUST_PORT.log"; exit 2
fi
BASE="http://127.0.0.1:$TRUST_PORT"

HOME_HTML="$(curl -s "$BASE/")"
chk "目录索引 200" "$(code "$BASE/")" "200"
chk "目录列出 a.md" "$HOME_HTML" "a.md"
chk "目录有搜索入口" "$HOME_HTML" 'class="search-wrap"'
chk "目录显示文件大小" "$HOME_HTML" 'class="meta-size"><1 KB'
nchk "目录不显示字节单位" "$HOME_HTML" ' B · '
chk "目录有独立时间列" "$HOME_HTML" 'class="meta-time"'
chk "目录有固定操作列" "$HOME_HTML" 'class="row-actions"'
chk "目录统计用项目" "$HOME_HTML" '个项目'
nchk "目录无只读文档库" "$HOME_HTML" '只读文档库'
chk "文件带下载入口" "$HOME_HTML" 'a.md?download=1'
nchk "目录不带下载入口" "$HOME_HTML" 'sub/?download=1'
ROOT_FILES="$(find "$ROOT" -maxdepth 1 -mindepth 1 -type f | wc -l | tr -d ' ')"
chk_num "下载入口数等于文件数" "$(count "$HOME_HTML" '?download=1')" "$ROOT_FILES"
nchk "根目录无上级链接" "$HOME_HTML" '上级目录'
chk "空目录提示" "$(curl -s "$BASE/empty/")" '这个目录是空的。'
SUB_HTML="$(curl -s "$BASE/sub/")"
chk "子目录面包屑根链接" "$SUB_HTML" '<a href="/">'
chk "子目录面包屑" "$SUB_HTML" 'aria-label="面包屑"'
chk "子目录文件链接正确" "$SUB_HTML" 'href="/sub/c.md"'
nchk "子目录无双重斜杠" "$SUB_HTML" '/sub//'
nchk "上级链接不是 //" "$SUB_HTML" 'href="//"'
nchk "目录不自动 index" "$SUB_HTML" "<h1>SUB INDEX</h1>"
chk "目录列出 index.html" "$SUB_HTML" "index.html"
chk "文件尾斜杠 404" "$(code "$BASE/b.txt/")" "404"
chk "编码尾斜杠 404" "$(code "$BASE/b.txt%2f")" "404"
chk "目录尾斜杠仍 200" "$(code "$BASE/sub/")" "200"

LOC="$(header "$BASE/sub" location)"
chk "目录 301" "$(code "$BASE/sub")" "301"
chk "目录 301 目标" "$LOC" "/sub/"

# Redirects must encode exactly once (spaces and CJK).
chk "空格目录 301" "$(code "$BASE/my%20dir")" "301"
SPACE_LOC="$(header "$BASE/my%20dir" location)"
chk "空格目录 Location" "$SPACE_LOC" "/my%20dir/"
nchk "Location 无二次编码" "$SPACE_LOC" "%25"
chk "空格目录跟随后 200" "$(curl -sL -o /dev/null -w '%{http_code}' "$BASE/my%20dir")" "200"
CJK_DIR="/%E4%B8%AD%E6%96%87%E7%9B%AE%E5%BD%95"
chk "中文目录 301" "$(code "$BASE$CJK_DIR")" "301"
chk "中文目录跟随后 200" "$(curl -sL -o /dev/null -w '%{http_code}' "$BASE$CJK_DIR")" "200"

SRC="$(curl -s "$BASE/b.txt")"
chk "源码页标题文件名" "$SRC" '<h1>b.txt</h1>'
chk "源码页类型标签" "$SRC" '>文本<'
chk "源码页大小标签" "$SRC" '<1 KB'
chk "源码页行数标签" "$SRC" '3 行'
chk "源码页修改时间标签" "$SRC" '更新于 '
chk "源码页行锚点" "$SRC" 'id="L1"'
chk "源码页内容" "$SRC" "hello"
chk "源码页下载入口" "$SRC" "?download=1"
chk "源码页岛清单" "$SRC" 'data-islands="theme nav search totop source"'
nchk "源码页不挂 TOC 岛" "$SRC" ' totop toc'

BIG="$(curl -s "$BASE/big.txt")"
chk "大源码分块" "$BIG" 'class="source-wrap source-chunked"'
chk "大源码全文提示" "$BIG" '已加载完整内容'
nchk "大源码无实现说明" "$BIG" '浏览器按可视区域'
chk "大源码末行" "$BIG" "last line marker"
chk "大源码总行数" "$BIG" 'data-source-lines="12000"'
chk_num "大源码分块数" "$(count "$BIG" 'class="source-chunk"')" "24"
nchk "大源码不截断" "$BIG" '前 1000 行'
nchk "大源码无 text 通道" "$BIG" '?text=1'

RENDER="$(curl -s "$BASE/a.md")"
chk "文档岛清单" "$RENDER" 'data-islands="theme nav search totop toc linetarget code zoom"'
nchk "文档不挂 source 岛" "$RENDER" ' source"'
chk "渲染页行定位数据" "$RENDER" 'data-sourcepos='
chk "Markdown 标题" "$RENDER" ">Hello</h1>"
chk "Markdown 粗体" "$RENDER" ">bold</strong>"
chk "Markdown 删除线" "$RENDER" "<s>del</s>"
chk "任务列表字面量" "$RENDER" "[x] task"
chk "裸 HTML 透传" "$RENDER" '<div id="raw">raw</div>'
chk "表格 style 对齐" "$RENDER" 'style="text-align:left"'
nchk "没有 align 属性" "$RENDER" ' align="left"'
nchk "标题没有 id" "$RENDER" '<h1 id='

RAW="$(curl -s "$BASE/a.md?raw=1")"
chk "raw 原文" "$RAW" "# Hello"
nchk "raw 不渲染" "$RAW" "<strong>bold</strong>"
chk "raw 行锚点" "$RAW" 'id="L1"'
chk "raw 回渲染链接" "$RAW" '预览'
chk "raw 下载入口" "$RAW" "?download=1"
LINE5_SRC="$(sed -n '5p' "$ROOT/a.md")"
chk "raw 第 5 行内容一致" "$RAW" "$LINE5_SRC"

CSP="$(header "$BASE/a.md" content-security-policy)"
chk "CSP nonce" "$CSP" "script-src 'nonce-"
chk "CSP base-uri" "$CSP" "base-uri 'none'"
chk "nosniff" "$(header "$BASE/a.md" x-content-type-options)" "nosniff"

DL="$(curl -s -D - -o "$TMP/dl.md" "$BASE/a.md?download=1")"
chk "下载 Content-Disposition" "$DL" "attachment"
chk "下载 Markdown 类型" "$DL" "text/markdown"
chk "下载原始字节" "$(cat "$TMP/dl.md")" "# Hello"
chk "文本下载" "$(curl -s "$BASE/b.txt?download=1")" "hello"

SEARCH="$(curl -s --get --data-urlencode 'q=needle' "$BASE/search?__mdview=search")"
chk "搜索页岛清单" "$SEARCH" 'data-islands="theme nav search totop"'
NAVJSON="$(curl -s "$BASE/_nav?__mdview=nav")"
chk "导航 JSON" "$NAVJSON" '"type":"dir"'
chk "导航含文件" "$NAVJSON" '"name":"a.md"'
nchk "导航跳过隐藏目录" "$NAVJSON" '".hidden"'
chk "HTML 信任目录直接原文" "$(curl -s "$BASE/page.html")" '<h1>HTML Probe</h1>'
nchk "HTML 信任目录无外壳" "$(curl -s "$BASE/page.html")" 'html-toolbar'
chk "HTML 信任目录 MIME" "$(ctype "$BASE/page.html")" "text/html"
nchk "HTML 信任目录无 CSP" "$(header "$BASE/page.html" content-security-policy)" "sandbox"
chk "HTML 信任目录 view=1 也是原文" "$(curl -s "$BASE/page.html?view=1")" '<h1>HTML Probe</h1>'
chk "HTML 信任目录 iframe 请求也是原文" "$(curl -s -H 'Sec-Fetch-Dest: iframe' "$BASE/page.html")" '<h1>HTML Probe</h1>'
chk "HTML 源码有 tabs" "$(curl -s "$BASE/page.html?raw=1")" 'html-toolbar'
chk "HTML 源码行锚点" "$(curl -s "$BASE/page.html?raw=1")" 'id="L1"'
nchk "HTML 源码无 iframe" "$(curl -s "$BASE/page.html?raw=1")" '<iframe'
chk "CSS 子资源 MIME" "$(curl -s -o /dev/null -w '%{content_type}' -H 'Sec-Fetch-Dest: style' "$BASE/style.css")" "text/css; charset=utf-8"
chk "CSS 子资源原文" "$(curl -s -H 'Sec-Fetch-Dest: style' "$BASE/style.css")" "body { color: rgb(1, 2, 3); }"
chk "CSS 直接访问是源码页" "$(curl -s "$BASE/style.css")" '<h1>style.css</h1>'
chk "SVG 直开 CSP sandbox" "$(header "$BASE/evil.svg" content-security-policy)" "sandbox allow-top-navigation-by-user-activation"
chk "HTML 搜索行跳源码" "$(curl -s "$BASE/search?__mdview=search&q=htmlneedle")" 'href="/page.html?raw=1#L1"'
chk "HTML 目录行有源码入口" "$HOME_HTML" 'href="/page.html?raw=1"'
chk "目录下载图标有悬浮文案" "$HOME_HTML" 'title="下载 page.html"'
chk "目录源码图标有悬浮文案" "$HOME_HTML" 'title="查看 page.html 源码"'
chk "压缩包重定向" "$(code "$BASE/sample.zip")" "301"
chk "压缩包页面 200" "$(code "$BASE/sample.zip/")" "200"
chk "压缩包页面标题" "$(curl -s "$BASE/sample.zip/")" '<h1>sample.zip</h1>'
chk "压缩包格式与条目" "$(curl -s "$BASE/sample.zip/")" "ZIP ·"
chk "压缩包下载入口" "$(curl -s "$BASE/sample.zip/")" "下载压缩包"
chk "包内 Markdown" "$(curl -s "$BASE/sample.zip/docs/a.md")" "Archive A"
chk "包内 Markdown 图片" "$(curl -s "$BASE/sample.zip/docs/a.md")" 'src="/sample.zip/docs/pic.png"'
chk "包内图片 200" "$(code "$BASE/sample.zip/docs/pic.png")" "200"
chk "包内 HTML 原文" "$(curl -s "$BASE/sample.zip/docs/page.html")" "<h1>Archive HTML</h1>"
chk "包内源码" "$(curl -s "$BASE/sample.zip/docs/a.md?raw=1")" 'id="L1"'
chk "包内下载" "$(header "$BASE/sample.zip/docs/a.md?download=1" content-disposition)" "attachment"
chk "整包下载" "$(header "$BASE/sample.zip?download=1" content-disposition)" "attachment"
chk "tar.gz 条目" "$(curl -s "$BASE/sample.tar.gz/docs/a.md")" "Archive A"
chk "7z 条目" "$(curl -s "$BASE/sample.7z/docs/a.md")" "Archive A"
chk "嵌套 zip 不递归" "$(header "$BASE/sample.zip/inner.zip" content-type)" "application/zip"
chk "CSP connect-src" "$(header "$BASE/a.md" content-security-policy)" "connect-src 'self'"
chk "搜索正文结果" "$SEARCH" "result-group"
chk "搜索摘要用结果" "$SEARCH" '条结果'
nchk "搜索无命中字样" "$SEARCH" '命中'
nchk "搜索无扫描耗时" "$SEARCH" '实时扫描'
chk "搜索结果条目可点击" "$SEARCH" 'class="hit" href='
chk "Markdown 命中跳渲染行" "$SEARCH" 'href="/search.md#L1"'
chk "搜索文本命中跳行" "$(curl -s "$BASE/search?__mdview=search&q=hello")" 'href="/b.txt#L1"'
nchk "搜索不再出现源码 Ln" "$SEARCH" "源码 Ln"
nchk "搜索不再出现打开文档" "$SEARCH" '打开文档'
chk "搜索文件名命中" "$SEARCH" "search.md"
chk "搜索大小写不敏感" "$(curl -s "$BASE/search?__mdview=search&q=CASENEEDLE")" "CaseNeedle.md"
chk "搜索文件标题可点击" "$(curl -s "$BASE/search?__mdview=search&q=CaseNeedle")" 'class="result-head" href="/CaseNeedle.md"'
chk "搜索中文查询" "$(curl -s "$BASE/search?__mdview=search&q=%E5%85%B3%E9%94%AE%E8%AF%8D")" "关键词.md"
HIDDEN_SEARCH="$(curl -s "$BASE/search?__mdview=search&q=HIDDENNEEDLE")"
nchk "搜索跳过隐藏目录" "$HIDDEN_SEARCH" ".hidden/h.md"
nchk "搜索跳过 node_modules" "$HIDDEN_SEARCH" "node_modules/n.md"

# Internal URLs are marked; unmarked paths belong to the file system.
chk "search 同名文件优先" "$(curl -s "$BASE/search")" "a real search file"
chk "search 内部页面需标记" "$(curl -s "$BASE/search?__mdview=search&q=hello")" 'class="search-page-form"'
nchk "search 内部页面不返回同名文件" "$(curl -s "$BASE/search?__mdview=search&q=hello")" "a real search file"
chk "_nav 同名文件优先" "$(curl -s "$BASE/_nav")" "a real nav file"
chk "_nav 内部 JSON 需标记" "$(curl -s "$BASE/_nav?__mdview=nav")" '"tree"'
nchk "_nav 内部 JSON 不返回同名文件" "$(curl -s "$BASE/_nav?__mdview=nav")" "a real nav file"

# Markdown extension scope: .md/.markdown render; .mdx stays source.
chk ".markdown 渲染" "$(curl -s "$BASE/a.markdown")" 'class="markdown-body"'
chk ".markdown 内容" "$(curl -s "$BASE/a.markdown")" ">Markdown Ext</h1>"
chk ".mdx 源码页" "$(curl -s "$BASE/a.mdx")" 'class="source-wrap"'
chk ".mdx 标签" "$(curl -s "$BASE/a.mdx")" ">MDX<"
chk ".markdown 搜索内容" "$(curl -s "$BASE/search?__mdview=search&q=markdownneedle")" 'href="/a.markdown#L3"'

# Legacy encodings: decode before preview/search, label the detected encoding,
# and keep original bytes for downloads/raw.
chk "GBK Markdown 预览" "$(curl -s "$BASE/gbk.md")" "中文标题"
chk "GBK Markdown 编码标签" "$(curl -s "$BASE/gbk.md")" "GBK"
chk "GBK 源码编码标签" "$(curl -s "$BASE/gbk.txt")" "编码 GBK"
chk "GBK 搜索正文" "$(curl -s "$BASE/search?__mdview=search&q=%E4%B8%AD%E6%96%87")" 'href="/gbk.md#L1"'
chk "GBK 下载 charset" "$(header "$BASE/gbk.txt?download=1" content-type)" "charset=gbk"
chk "GBK CSS raw charset" "$(curl -s -o /dev/null -w '%{content_type}' -H 'Sec-Fetch-Dest: style' "$BASE/gbk.css")" "text/css; charset=gbk"
chk_num "GBK CSS 原始字节" "$(curl -s -H 'Sec-Fetch-Dest: style' "$BASE/gbk.css" | wc -c | tr -d ' ')" "$(wc -c <"$ROOT/gbk.css" | tr -d ' ')"
chk "UTF-16 预览" "$(curl -s "$BASE/utf16le.txt")" "UTF-16LE 文本"
chk "UTF-16 编码标签" "$(curl -s "$BASE/utf16le.txt")" "编码 UTF-16LE BOM"
nchk "UTF-32 不进源码页" "$(curl -s "$BASE/utf32le.txt")" "source-encoding"
chk "UTF-32 按二进制" "$(ctype "$BASE/utf32le.txt")" "application/octet-stream"
nchk "HTML 下载无 charset" "$(header "$BASE/page.html?download=1" content-type)" "charset="

chk "压缩包条目尾斜杠 404" "$(code "$BASE/sample.zip/docs/a.md/")" "404"

chk "图片 MIME" "$(ctype "$BASE/img.png")" "image/png"
chk "二进制 MIME" "$(ctype "$BASE/bin.dat")" "application/octet-stream"
chk "JSON MIME" "$(header "$BASE/data.json?download=1" content-type)" "application/json; charset=utf-8"
chk "TypeScript 是文本" "$(header "$BASE/app.ts?download=1" content-type)" "text/plain; charset=utf-8"
chk "Makefile 文本" "$(header "$BASE/Makefile?download=1" content-type)" "text/plain; charset=utf-8"
chk "Dockerfile 文本" "$(header "$BASE/Dockerfile?download=1" content-type)" "text/plain; charset=utf-8"
chk ".gitignore 文本" "$(header "$BASE/.gitignore?download=1" content-type)" "text/plain; charset=utf-8"
chk "无扩展名文本可预览" "$(curl -s "$BASE/README")" "extensionless text"
chk "无扩展名二进制下载" "$(ctype "$BASE/noextbin")" "application/octet-stream"
chk "无扩展名二进制原文完整" "$(curl -s -o /dev/null -w '%{size_download}' "$BASE/noextbin")" "$(wc -c <"$ROOT/noextbin" | tr -d ' ')"
UNI_PATH="/%E4%B8%AD%E6%96%87%20%E6%96%87%E4%BB%B6.txt"
chk "中文文件名列表编码" "$HOME_HTML" "$UNI_PATH"
chk "中文文件名可访问" "$(code "$BASE$UNI_PATH")" "200"
chk "TS 源码页语言类" "$(curl -s "$BASE/app.ts")" 'class="language-typescript"'

# Live round-trip for rewritten Markdown targets.
LINKS="$(curl -s "$BASE/links.md")"
chk "空格目录图片渲染" "$LINKS" 'src="/img%20dir/nested%20pic.png"'
chk_num "三种写法收敛" "$(count "$LINKS" 'src="/img%20dir/nested%20pic.png"')" 2
chk "中文+空格图片渲染" "$LINKS" 'src="/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png"'
chk "含 # 文件名渲染" "$LINKS" 'href="/a%23b.md"'
nchk "渲染结果无二次编码" "$LINKS" "%25"
chk "空格目录图片可取" "$(code "$BASE/img%20dir/nested%20pic.png")" "200"
chk "中文+空格图片可取" "$(code "$BASE/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png")" "200"
chk "含 # 文件可取" "$(code "$BASE/a%23b.md")" "200"
chk "尖括号目录链接可取" "$(code "$BASE/my%20dir/a.md")" "200"

chk "404" "$(code "$BASE/nope")" "404"
ERR="$(curl -s "$BASE/nope")"
chk "404 页面文案" "$ERR" "页面不存在"
chk "404 文件文案" "$ERR" "这个文件不存在，或已被移动"
chk "404 返回首页" "$ERR" "返回首页"
TRAVERSAL_CODE="$(code "$BASE/..%2F..%2Fetc%2Fpasswd")"
if [ "$TRAVERSAL_CODE" = "403" ] || [ "$TRAVERSAL_CODE" = "404" ]; then ok "路径穿越拒绝"; else bad "路径穿越拒绝 ($TRAVERSAL_CODE)"; fi

chk "资产 highlight.js" "$(code "$BASE/_assets/highlight.js?__mdview=asset")" "200"
chk "资产 highlight.css" "$(code "$BASE/_assets/highlight.css?__mdview=asset")" "200"
chk "资产 markdown.css" "$(code "$BASE/_assets/markdown.css?__mdview=asset")" "200"
chk "资产 app.css" "$(code "$BASE/_assets/app.css?__mdview=asset")" "200"
chk "资产 app.js" "$(code "$BASE/_assets/app.js?__mdview=asset")" "200"
chk "资产 app.css 是内嵌 CSS" "$(ctype "$BASE/_assets/app.css?__mdview=asset")" "text/css; charset=utf-8"
chk "同名 _assets/app.css 文件优先" "$(ctype "$BASE/_assets/app.css")" "text/html; charset=utf-8"
chk "同名 _assets/app.css 内容" "$(curl -s "$BASE/_assets/app.css")" "a real app css"
chk "无同名文件的内部路径 404" "$(code "$BASE/_assets/highlight.js")" "404"
ASSET_HTML="$(curl -s "$BASE/a.md")"
chk "页面引用 highlight.js" "$ASSET_HTML" "/_assets/highlight.js?__mdview=asset"
chk "页面引用 app.css" "$ASSET_HTML" "/_assets/app.css?__mdview=asset"
chk "页面引用 app.js" "$ASSET_HTML" "/_assets/app.js?__mdview=asset"

HEADERS="$(curl -s -I "$BASE/img.png" | tr -d '\r' | tr '[:upper:]' '[:lower:]')"
chk "HEAD 200" "$HEADERS" "200"
chk "HEAD Content-Length" "$HEADERS" "content-length:"
chk "HEAD 无 body（-I）" "$(curl -s -I "$BASE/img.png" | grep -c '^HTTP/')" "1"

echo "== safe server =="
SAFE_PORT="$((BASE_PORT + 1))"
start_server "$SAFE_PORT" --trust --safe --port-tries 0
wait_http "$SAFE_PORT" || { echo "safe server failed"; exit 2; }
SAFE="http://127.0.0.1:$SAFE_PORT"
chk "--safe 拦截文本" "$(code "$SAFE/b.txt")" "404"
chk "--safe 放行 md" "$(code "$SAFE/a.md")" "200"
chk "--safe 放行 .markdown" "$(code "$SAFE/a.markdown")" "200"
chk "--safe 放行 GBK Markdown" "$(code "$SAFE/gbk.md")" "200"
chk "--safe 放行图片" "$(code "$SAFE/img.png")" "200"
chk "--safe 拦截 Makefile" "$(code "$SAFE/Makefile")" "404"
chk "--safe 放行 HTML 源码" "$(code "$SAFE/page.html")" "200"
nchk "--safe HTML 无 iframe" "$(curl -s "$SAFE/page.html")" '<iframe'
nchk "--safe view 不渲染" "$(curl -s "$SAFE/page.html?view=1")" '<iframe'
chk "--safe CSS 拦截" "$(code "$SAFE/style.css")" "404"
SAFE_SEARCH="$(curl -s "$SAFE/search?__mdview=search&q=hello")"
chk "--safe 搜索扫 Markdown" "$SAFE_SEARCH" "a.md"
nchk "--safe 搜索不扫文本" "$SAFE_SEARCH" "b.txt"

echo "== no-search server =="
NOS_PORT="$((BASE_PORT + 2))"
start_server "$NOS_PORT" --trust --no-search --port-tries 0
wait_http "$NOS_PORT" || { echo "no-search server failed"; exit 2; }
NOS="http://127.0.0.1:$NOS_PORT"
chk "--no-search 关闭路由" "$(code "$NOS/search?__mdview=search&q=x")" "404"
chk "--no-search 同名文件仍可取" "$(code "$NOS/search")" "200"
NOS_HTML="$(curl -s "$NOS/")"
nchk "--no-search 无搜索入口" "$NOS_HTML" 'id="search-open"'
chk "--no-search 岛清单省略 search" "$NOS_HTML" 'data-islands="theme nav totop"'

echo "== max-preview server =="
MP="$TMP/maxprev"
mkdir -p "$MP"
printf 'small big hit\n' >"$MP/small.md"
for i in $(seq 1 40); do printf 'big huge %s\n' "$i"; done >"$MP/huge.md"
MP_PORT="$((BASE_PORT + 3))"
start_server_at "$MP_PORT" "$MP" --trust --max-preview 100 --port-tries 0
wait_http "$MP_PORT" || { echo "max-preview server failed"; exit 2; }
MPB="http://127.0.0.1:$MP_PORT"
chk "上限内仍渲染" "$(curl -s "$MPB/small.md")" "small big hit"
chk "超限强制下载" "$(header "$MPB/huge.md" content-disposition)" "attachment"
chk "超限内容完整" "$(curl -s -o /dev/null -w '%{size_download}' "$MPB/huge.md")" "$(wc -c <"$MP/huge.md" | tr -d ' ')"
MP_SEARCH="$(curl -s "$MPB/search?__mdview=search&q=big" | sed 's#.*<main class="main">##' | sed 's#</main>.*##')"
chk "搜索仍命中上限内文件" "$MP_SEARCH" "small.md"
nchk "搜索跳过超限文件" "$MP_SEARCH" "huge.md"

echo "== port fallback =="
FB_PORT="$((BASE_PORT + 4))"
start_server "$FB_PORT" --trust
wait_http "$FB_PORT" || { echo "fallback first server failed"; exit 2; }
"$BIN" --root "$ROOT" --host 127.0.0.1 --port "$FB_PORT" \
  >"$TMP/fallback.log" 2>&1 &
PIDS+=("$!")
if wait_http "$((FB_PORT + 1))"; then
  ok "端口占用自动回退"
  chk "回退后端口可用" "$(code "http://127.0.0.1:$((FB_PORT + 1))/")" "200"
  chk "回退日志显示实际端口" "$(cat "$TMP/fallback.log")" ":$((FB_PORT + 1))"
else
  bad "端口占用自动回退"
fi

echo "== untrusted server =="
UNTRUST_PORT="$((BASE_PORT + 7))"
start_server "$UNTRUST_PORT" --untrusted --port-tries 0
wait_http "$UNTRUST_PORT" || { echo "untrusted server failed"; exit 2; }
UNTRUST="http://127.0.0.1:$UNTRUST_PORT"
PAGE="$(curl -s "$UNTRUST/a.md")"
chk "未信任拦截面" "$PAGE" "仍要打开"
chk "Trust 页面文案" "$PAGE" "此目录尚未受信任"
TOKEN="$(printf '%s' "$PAGE" | grep -oE 'open=[a-f0-9]+' | head -1 | cut -d= -f2)"
[ -n "$TOKEN" ] || { echo "no token"; exit 2; }
OPENED="$(curl -s "$UNTRUST/a.md?open=$TOKEN")"
chk "一次性令牌打开" "$OPENED" ">Hello</h1>"
REUSED="$(curl -s "$UNTRUST/a.md?open=$TOKEN")"
chk "令牌复用再次拦截" "$REUSED" "仍要打开"
chk "raw 绕过拦截" "$(curl -s "$UNTRUST/a.md?raw=1")" "<h1>a.md</h1>"
chk "download 绕过拦截" "$(curl -s "$UNTRUST/a.md?download=1")" "# Hello"
UNTRUST_HTML="$(curl -s "$UNTRUST/page.html")"
chk "未信任 HTML 是沙箱外壳" "$UNTRUST_HTML" 'data-page="html"'
chk "未信任 HTML 有 tabs" "$UNTRUST_HTML" 'html-toolbar'
chk "未信任 HTML iframe" "$UNTRUST_HTML" 'src="/page.html?view=1"'
chk "未信任 HTML sandbox" "$UNTRUST_HTML" 'sandbox="allow-scripts allow-forms allow-modals allow-popups"'
chk "未信任 HTML frame-src self" "$(header "$UNTRUST/page.html" content-security-policy)" "frame-src 'self'"
chk "未信任裸页原文" "$(curl -s "$UNTRUST/page.html?view=1")" '<h1>HTML Probe</h1>'
chk "未信任裸页 CSP sandbox" "$(header "$UNTRUST/page.html?view=1" content-security-policy)" "sandbox allow-scripts"
chk "未信任裸页 Referrer-Policy" "$(header "$UNTRUST/page.html?view=1" referrer-policy)" "no-referrer"
chk "未信任 HTML 源码 tabs" "$(curl -s "$UNTRUST/page.html?raw=1")" 'html-toolbar'

echo "== filesystem edge cases =="
SEC="$TMP/security"
mkdir -p "$SEC"
printf 'ok\n' >"$SEC/real.txt"
if mkfifo "$SEC/pipe" 2>/dev/null && ln -s /etc/passwd "$SEC/escape" 2>/dev/null && ln -s "$SEC/real.txt" "$SEC/alias.txt" 2>/dev/null; then
  SEC_PORT="$((BASE_PORT + 8))"
  start_server_at "$SEC_PORT" "$SEC" --trust --port-tries 0
  wait_http "$SEC_PORT" || { echo "security server failed"; exit 2; }
  SECB="http://127.0.0.1:$SEC_PORT"
  chk "FIFO 立刻 404" "$(curl -s -m 4 -o /dev/null -w '%{http_code}' "$SECB/pipe" || true)" "404"
  FIFO_TIME="$(curl -s -m 4 -o /dev/null -w '%{time_total}' "$SECB/pipe" || true)"
  chk "FIFO 用时 <1 秒" "$(printf '%s' "$FIFO_TIME" | cut -d. -f1)" "0"
  chk "符号链接逃逸 403" "$(code "$SECB/escape")" "403"
  chk "根内符号链接可用" "$(code "$SECB/alias.txt")" "200"
  chk "常规文件仍 200" "$(code "$SECB/real.txt")" "200"
else
  echo "  (skip) FIFO/symlink fixture unavailable"
fi

echo
printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
