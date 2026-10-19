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
  if printf '%s' "$haystack" | grep -Fq -- "$needle"; then ok "$name"; else bad "$name (missing: $needle)"; fi
}
nchk() {
  local name="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -Fq -- "$needle"; then bad "$name (unexpected: $needle)"; else ok "$name"; fi
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
printf 'hello\nworld\n' >"$ROOT/b.txt"
printf 'needle in text\n' >"$ROOT/search.md"
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
chk "目录有搜索框" "$HOME_HTML" 'class="search"'
chk "目录显示文件大小" "$HOME_HTML" ' B · '
chk "文件带下载入口" "$HOME_HTML" 'a.md?download=1'
nchk "目录不带下载入口" "$HOME_HTML" 'sub/?download=1'
ROOT_FILES="$(find "$ROOT" -maxdepth 1 -mindepth 1 -type f | wc -l | tr -d ' ')"
chk_num "下载入口数等于文件数" "$(count "$HOME_HTML" '?download=1')" "$ROOT_FILES"
nchk "根目录无上级链接" "$HOME_HTML" '上级目录'
chk "空目录提示" "$(curl -s "$BASE/empty/")" '这个目录是空的。'
SUB_HTML="$(curl -s "$BASE/sub/")"
chk "子目录有上级链接" "$SUB_HTML" '上级目录'
chk "一级上级指到根" "$SUB_HTML" 'class="parent" href="/"'
chk "子目录文件链接正确" "$SUB_HTML" 'href="/sub/c.md"'
nchk "子目录无双重斜杠" "$SUB_HTML" '/sub//'
nchk "上级链接不是 //" "$SUB_HTML" 'href="//"'

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
chk "源码页行锚点" "$SRC" 'id="L1"'
chk "源码页内容" "$SRC" "hello"
chk "源码页下载入口" "$SRC" "?download=1"

RENDER="$(curl -s "$BASE/a.md")"
chk "Markdown 标题" "$RENDER" "<h1>Hello</h1>"
chk "Markdown 粗体" "$RENDER" "<strong>bold</strong>"
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
chk "raw 回渲染链接" "$RAW" '看渲染结果'
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

SEARCH="$(curl -s --get --data-urlencode 'q=needle' "$BASE/search")"
chk "搜索正文命中" "$SEARCH" "正文命中"
chk "搜索文件名命中" "$SEARCH" "search.md"
chk "搜索大小写不敏感" "$(curl -s "$BASE/search?q=CASENEEDLE")" "CaseNeedle.md"
chk "搜索文件名命中标记" "$(curl -s "$BASE/search?q=CaseNeedle")" "文件名命中"
chk "搜索中文查询" "$(curl -s "$BASE/search?q=%E5%85%B3%E9%94%AE%E8%AF%8D")" "关键词.md"
HIDDEN_SEARCH="$(curl -s "$BASE/search?q=HIDDENNEEDLE")"
nchk "搜索跳过隐藏目录" "$HIDDEN_SEARCH" ".hidden/h.md"
nchk "搜索跳过 node_modules" "$HIDDEN_SEARCH" "node_modules/n.md"

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
TRAVERSAL_CODE="$(code "$BASE/..%2F..%2Fetc%2Fpasswd")"
if [ "$TRAVERSAL_CODE" = "403" ] || [ "$TRAVERSAL_CODE" = "404" ]; then ok "路径穿越拒绝"; else bad "路径穿越拒绝 ($TRAVERSAL_CODE)"; fi

chk "资产 highlight.js" "$(code "$BASE/_assets/highlight.js")" "200"
chk "资产 highlight.css" "$(code "$BASE/_assets/highlight.css")" "200"
chk "资产 markdown.css" "$(code "$BASE/_assets/markdown.css")" "200"
chk "资产 mdview.js" "$(code "$BASE/_assets/mdview.js")" "200"
ASSET_HTML="$(curl -s "$BASE/a.md")"
chk "页面引用 highlight.js" "$ASSET_HTML" "/_assets/highlight.js"
chk "页面引用 mdview.js" "$ASSET_HTML" "/_assets/mdview.js"

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
chk "--safe 放行图片" "$(code "$SAFE/img.png")" "200"
chk "--safe 拦截 Makefile" "$(code "$SAFE/Makefile")" "404"

echo "== no-search server =="
NOS_PORT="$((BASE_PORT + 2))"
start_server "$NOS_PORT" --trust --no-search --port-tries 0
wait_http "$NOS_PORT" || { echo "no-search server failed"; exit 2; }
NOS="http://127.0.0.1:$NOS_PORT"
chk "--no-search 关闭路由" "$(code "$NOS/search?q=x")" "404"
nchk "--no-search 无搜索框" "$(curl -s "$NOS/")" 'class="search"'

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
MP_SEARCH="$(curl -s "$MPB/search?q=big")"
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
TOKEN="$(printf '%s' "$PAGE" | grep -oE 'open=[a-f0-9]+' | head -1 | cut -d= -f2)"
[ -n "$TOKEN" ] || { echo "no token"; exit 2; }
OPENED="$(curl -s "$UNTRUST/a.md?open=$TOKEN")"
chk "一次性令牌打开" "$OPENED" "<h1>Hello</h1>"
REUSED="$(curl -s "$UNTRUST/a.md?open=$TOKEN")"
chk "令牌复用再次拦截" "$REUSED" "仍要打开"
chk "raw 绕过拦截" "$(curl -s "$UNTRUST/a.md?raw=1")" "源码视图"
chk "download 绕过拦截" "$(curl -s "$UNTRUST/a.md?download=1")" "# Hello"

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
