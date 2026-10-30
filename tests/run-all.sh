#!/usr/bin/env bash
# Run the full local acceptance suite in the same order as docs/testing/agent-guide.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

section() { printf '\n== %s ==\n' "$1"; }

section "web typecheck"
npm --prefix web run typecheck

section "rust fmt"
cargo fmt --all --check

section "rust clippy"
cargo clippy --all-targets -- -D warnings

section "rust tests"
cargo test

section "doc links"
node tests/check-doc-links.mjs

section "css baseline"
node tests/check-css-baseline.mjs

section "black-box HTTP"
bash tests/selftest-rust.sh

section "TTY trust"
bash tests/trust-tty.sh

section "browser probe"
node tests/browser-probe.mjs

section "source performance"
node tests/perf-source.mjs

section "artifact smoke"
bash tests/smoke-artifact.sh target/release/mdview

printf '\nALL LOCAL CHECKS PASSED\n'
