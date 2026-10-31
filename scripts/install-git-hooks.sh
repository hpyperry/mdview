#!/usr/bin/env bash
# 安装仓库自带的 git hooks（目前只有 post-merge）。
#
# git hooks 不随仓库分发，每个 clone 需要跑一次。
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if [ ! -d scripts/git-hooks ]; then
  echo "找不到 scripts/git-hooks/" >&2
  exit 1
fi

chmod +x scripts/git-hooks/*

current="$(git config --get core.hooksPath || true)"
if [ -n "$current" ] && [ "$current" != "scripts/git-hooks" ]; then
  echo "注意：core.hooksPath 原本指向 '$current'，将被覆盖。" >&2
fi

git config core.hooksPath scripts/git-hooks

echo "已设置 core.hooksPath = scripts/git-hooks"
echo "post-merge 会在合并或 git pull 后检查 target/debug（阈值 2 GB）。"
echo "关闭：git config --unset core.hooksPath"
