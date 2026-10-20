#!/usr/bin/env bash
# Smoke-test a packaged artifact with no repo checkout assumptions:
#   bash tests/smoke-artifact.sh path/to/mdview
set -euo pipefail

BIN="${1:?usage: smoke-artifact.sh <binary>}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mdview-artifact-smoke.XXXXXX")"
ROOT="$TMP/root"
PORT=$((25000 + RANDOM % 2000))
PASS=0
FAIL=0
PID=""

cleanup() {
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
  [ -n "$PID" ] && wait "$PID" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

ok() { PASS=$((PASS + 1)); printf '  \033[32mok\033[0m   %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
chk() {
  local name="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -Fq -- "$needle"; then ok "$name"; else bad "$name (missing: $needle)"; fi
}
header() {
  curl -s -D - -o /dev/null "$1" | tr -d '\r' | awk -v n="$2" \
    'tolower($0) ~ "^" n ":" {sub(/^[^:]+:[[:space:]]*/, ""); print; exit}'
}

mkdir -p "$ROOT"
printf '# Artifact\n\nbody\n' >"$ROOT/a.md"
printf 'hello\n' >"$ROOT/b.txt"
printf '\211PNG\r\n\032\n' >"$ROOT/i.png"

"$BIN" --root "$ROOT" --host 127.0.0.1 --port "$PORT" --port-tries 0 --trust \
  >"$TMP/server.log" 2>&1 &
PID=$!
for _ in $(seq 1 80); do
  curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1 && break
  sleep 0.1
done
if ! curl -sf "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
  echo "artifact failed to start:"; cat "$TMP/server.log"; exit 1
fi
BASE="http://127.0.0.1:$PORT"

chk "目录页" "$(curl -s "$BASE/")" "a.md"
chk "Markdown 渲染" "$(curl -s "$BASE/a.md")" ">Artifact</h1>"
chk "资产内嵌" "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/_assets/highlight.js")" "200"
chk "下载原始字节" "$(curl -s "$BASE/b.txt?download=1")" "hello"
chk "下载头" "$(header "$BASE/b.txt?download=1" content-disposition)" "attachment"
chk "CSP nonce" "$(header "$BASE/a.md" content-security-policy)" "script-src 'nonce-"
chk "nosniff" "$(header "$BASE/a.md" x-content-type-options)" "nosniff"

echo
printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
