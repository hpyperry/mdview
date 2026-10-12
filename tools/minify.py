#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""minify.py —— 把 mdview.py 压成"只用于运行"的版本。

压缩内容（只做**语义安全**的三件事）：
  1. 删除注释；
  2. 删除模块/函数/类的 docstring；
  3. 删除空行。

不做的事（明确不做，因为风险大于收益）：
  * 不改标识符名 —— 会让回溯变难，且收益有限；
  * 不做"多语句合并成一行"之类的美化 —— 只在 `--compact` 下可选，默认关闭；
  * 不碰任何字符串字面量里的内容（CSS/JS/模板都在字符串里，必须原样保留）。

安全性靠两道保证：
  * 先 `ast.parse` 确认输入是合法 Python；
  * 用 `tokenize` 精确定位注释与 docstring 的行号（**不用正则**），
    按整行删除，避免切断跨行的括号与字符串。
  删除 docstring 后若该作用域只剩它一条语句（函数/类体），补一个 `pass`，
  否则会产生缩进错误。

用法:
    python3 tools/minify.py                      # -> dist/mdview.min.py
    python3 tools/minify.py --out /tmp/x.py
    python3 tools/minify.py --check              # 只报告体积，不写文件
"""

import argparse
import ast
import io
import os
import sys
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SRC = os.path.join(ROOT, "mdview.py")
DEFAULT_OUT = os.path.join(ROOT, "dist", "mdview.min.py")


def docstring_lines(tree):
    """返回所有 docstring 占据的行号集合（1-based，含首尾）。"""
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if not (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            continue
        # 只有"整块只有这一条语句"时才需要补 pass
        start = first.lineno
        end = getattr(first, "end_lineno", start)
        lines.update(range(start, end + 1))
    return lines


def needs_pass(tree):
    """找出「删掉 docstring 后作用域会变空」的 docstring 起始行。"""
    need = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if len(node.body) != 1:
            continue
        first = node.body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            need.add(first.lineno)
            if node.body[0].lineno == getattr(node, "lineno", None):
                # 单行函数体 `def f(): "doc"` 也能被整行删掉
                need.add(first.lineno)
    return need


def string_lines(src):
    """返回被字符串字面量覆盖的行号集合（含三引号跨行字符串的内部行）。

    删空行时必须避开这些行 —— 否则会把字符串**内容**里的空行删掉，
    改变模板/CSS/JS 的输出（实测：COPY_JS 里的一个空行被删后，
    每个 HTML 页面少 1 字节）。
    """
    covered = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.STRING:
            for ln in range(tok.start[0], tok.end[0] + 1):
                covered.add(ln)
    return covered


def comment_lines(src):
    """返回只含注释的行号集合。"""
    out = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            out.add(tok.start[0])
    return out


def minify(src, compact=False):
    tree = ast.parse(src)                      # 先确认输入合法
    drop = docstring_lines(tree)
    emit_pass = needs_pass(tree)
    comments = comment_lines(src)
    in_string = string_lines(src)

    kept = []
    for n, line in enumerate(src.split("\n"), 1):
        if n in drop:
            # docstring 整行删掉；若这是该作用域唯一语句，补 pass
            if n in emit_pass:
                indent = len(line) - len(line.lstrip(" "))
                kept.append(" " * indent + "pass")
            continue
        if n in comments:
            stripped = line.split("#", 1)[0]
            if not stripped.strip():
                continue                        # 整行都是注释
            kept.append(stripped.rstrip())
            continue
        if not line.strip():
            # 字符串字面量内部的空行**必须保留**（它是内容的一部分）
            if n in in_string:
                kept.append(line)
            continue
        kept.append(line.rstrip())

    out = "\n".join(kept) + "\n"
    if compact:
        out = compact_lines(out)
    return out


def compact_lines(src):
    """把相邻的简单赋值并成一行（可选，默认不启用）。

    只合并顶层的 `NAME = ...` 与 import，保证不会破坏块结构。
    """
    lines = src.split("\n")
    out = []
    for line in lines:
        if (out and line.startswith(("import ", "from ", "MD_EXT", "__version__"))
                and out[-1].startswith(("import ", "from "))):
            out[-1] = out[-1] + "; " + line
        else:
            out.append(line)
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="压缩 mdview.py 为运行版")
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--compact", action="store_true",
                    help="额外合并部分顶层语句（默认关闭）")
    ap.add_argument("--check", action="store_true", help="只报告，不写文件")
    args = ap.parse_args(argv)

    with open(args.src, encoding="utf-8") as fh:
        src = fh.read()
    out = minify(src, compact=args.compact)

    # 压缩结果必须仍是合法 Python
    try:
        ast.parse(out)
    except SyntaxError as exc:
        print("压缩结果不是合法 Python: %s" % exc, file=sys.stderr)
        return 2

    a, b = len(src.encode("utf-8")), len(out.encode("utf-8"))
    print("  源文件:   %6d 字节  %5d 行" % (a, src.count("\n")))
    print("  压缩后:   %6d 字节  %5d 行" % (b, out.count("\n")))
    print("  减少:     %6d 字节  (%.1f%%)" % (a - b, 100.0 * (a - b) / a))
    if not args.check:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        os.chmod(args.out, 0o755)
        print("  已写入:   %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
