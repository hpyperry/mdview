#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d node_modules ]; then
  npm ci
fi

python3 extract_corpus.py
node oracle.mjs
cargo build --release --quiet
./target/release/comrak-probe corpus/corpus.jsonl results/comrak.jsonl
node compare.mjs
