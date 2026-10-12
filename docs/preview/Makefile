# 中文注释：Makefile（无扩展名，按文件名判定为文本）
PY := python3
PORT ?= 8000

.PHONY: run test

run:
	$(PY) mdview.py --root docs --port $(PORT)

test:
	$(PY) tests/tests_render.py && bash tests/selftest.sh
