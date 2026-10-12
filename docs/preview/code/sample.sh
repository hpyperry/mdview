#!/usr/bin/env bash
# 中文注释：Shell 脚本
set -euo pipefail

ROOT="${1:-docs}"
echo "服务根目录：$ROOT"
for f in "$ROOT"/*.md; do
  printf '  %s (%s 行)\n' "$f" "$(wc -l < "$f")"
done | sort | head -5
