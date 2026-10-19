# 中文注释：Makefile（无扩展名，按文件名判定为文本）
CARGO := cargo
PORT ?= 8000

.PHONY: run build test

build:
	$(CARGO) build --release --locked

run:
	./target/release/mdview --root docs --port $(PORT)

test:
	$(CARGO) test && $(CARGO) clippy --all-targets -- -D warnings
	bash tests/selftest-rust.sh
