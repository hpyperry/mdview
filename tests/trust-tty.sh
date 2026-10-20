#!/usr/bin/env bash
# TTY trust prompt and persistence (P4-3).
#
# Runs the binary under a pseudo-terminal, answers "y", then verifies:
#   - the prompt was shown and the config was persisted;
#   - a second run reuses the stored trust without prompting;
#   - a fresh HOME without a TTY defaults to untrusted (interstitial).
#
# Requires `script` (macOS/BSD or util-linux). Skips cleanly if unavailable.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "${MDVIEW_BIN:-}" ]; then
  BIN="$MDVIEW_BIN"
elif [ -x "$REPO_ROOT/target/debug/mdview" ]; then
  BIN="$REPO_ROOT/target/debug/mdview"
elif [ -x "$REPO_ROOT/target/release/mdview" ]; then
  BIN="$REPO_ROOT/target/release/mdview"
else
  (cd "$REPO_ROOT" && cargo build --quiet)
  BIN="$REPO_ROOT/target/debug/mdview"
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/mdview-trust-tty.XXXXXX")"
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

command -v expect >/dev/null 2>&1 || { echo "  (skip) expect(1) unavailable"; exit 0; }

ROOT="$TMP/root"
mkdir -p "$ROOT"
printf '# Hi\n\ntrusted body\n' >"$ROOT/a.md"

BASE_PORT=$((23000 + RANDOM % 2000))
wait_http() {
  local port="$1"
  for _ in $(seq 1 80); do
    if curl -sf "http://127.0.0.1:$port/" >/dev/null 2>&1; then return 0; fi
    sleep 0.1
  done
  return 1
}

# --- 1) interactive prompt persists "trusted" ------------------------------
HOME_DIR="$TMP/home"
mkdir -p "$HOME_DIR"
PORT="$BASE_PORT"
env HOME_DIR="$HOME_DIR" ROOT="$ROOT" PORT="$PORT" BIN="$BIN" PIDFILE="$TMP/pid" \
  expect "$REPO_ROOT/tests/trust-tty.exp" >"$TMP/tty.log" 2>&1 &
WRAPPER=$!
PIDS+=("$WRAPPER")

for _ in $(seq 1 100); do
  [ -f "$TMP/pid" ] && wait_http "$PORT" && break
  sleep 0.1
done
if [ ! -f "$TMP/pid" ] || ! wait_http "$PORT"; then
  bad "TTY 服务启动"
  cat "$TMP/tty.log"
  exit 1
fi
SERVER_PID="$(cat "$TMP/pid")"
PIDS+=("$SERVER_PID")
chk "TTY 显示信任询问" "$(cat "$TMP/tty.log")" "是否信任该目录"
chk "TTY 启动后标记 trusted" "$(cat "$TMP/tty.log")" "trust:       trusted"
CONFIG="$(find "$HOME_DIR" -name trust.toml -type f | head -1)"
if [ -n "$CONFIG" ]; then ok "信任配置已写入"; else bad "信任配置已写入"; fi
if [ -n "$CONFIG" ]; then
  chk "配置记录 trusted = true" "$(cat "$CONFIG")" "trusted = true"
fi

# --- 2) stored trust is reused without a prompt ---------------------------
PORT2="$((BASE_PORT + 1))"
env -u XDG_CONFIG_HOME HOME="$HOME_DIR" "$BIN" --root "$ROOT" --host 127.0.0.1 \
  --port "$PORT2" --port-tries 0 </dev/null >"$TMP/second.log" 2>&1 &
PIDS+=("$!")
wait_http "$PORT2" || { bad "第二次启动"; cat "$TMP/second.log"; exit 1; }
chk "第二次不再询问" "$(cat "$TMP/second.log")" "trust:       trusted"
nchk "第二次日志无询问" "$(cat "$TMP/second.log")" "是否信任"
chk "第二次直接渲染" "$(curl -s "http://127.0.0.1:$PORT2/a.md")" ">Hi</h1>"

# --- 3) fresh HOME + no TTY defaults to untrusted -------------------------
HOME2="$TMP/home2"
mkdir -p "$HOME2"
PORT3="$((BASE_PORT + 2))"
env -u XDG_CONFIG_HOME HOME="$HOME2" "$BIN" --root "$ROOT" --host 127.0.0.1 \
  --port "$PORT3" --port-tries 0 </dev/null >"$TMP/third.log" 2>&1 &
PIDS+=("$!")
wait_http "$PORT3" || { bad "非交互启动"; cat "$TMP/third.log"; exit 1; }
chk "非交互默认 untrusted" "$(cat "$TMP/third.log")" "trust:       untrusted"
chk "非交互出现拦截面" "$(curl -s "http://127.0.0.1:$PORT3/a.md")" "仍要打开"

echo
printf 'PASS=%d FAIL=%d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
