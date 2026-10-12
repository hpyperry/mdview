#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_nav.py —— 重新生成 mdview.py 顶部的 SECTION 导航行号。

`mdview.py` 顶部的导航注释里写了每个 section 的起始行号，那是**生成物**：
改代码后行号会漂移，所以提供这个脚本一键重算，而不是靠手动维护。

用法（在任意目录均可执行）:
    python3 tests/sync_nav.py           # 就地更新 mdview.py 的导航块
    python3 tests/sync_nav.py --check    # 只检查是否已同步，不同步则退出码 1

它只改注释块，不动任何代码；改完请复跑
    python3 tests/tests_render.py
    bash tests/selftest.sh
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 本脚本在 tests/ 下，目标在仓库根
TARGET = os.path.join(ROOT, "mdview.py")

BEGIN = "SECTION 导航"
END = "# ===="
SEC_RE = re.compile(r"^# =+\n# SECTION (\d+)\s+(.+?)\n# =+$", re.M)


def section_lines(source):
    """返回 [(编号, 标题, 行号)]，按出现顺序。"""
    out = []
    for m in re.finditer(r"^# SECTION (\d+)\s+(.+?)\s*$", source, re.M):
        line_no = source.count("\n", 0, m.start()) + 1
        out.append((int(m.group(1)), m.group(2).strip(), line_no))
    return out


# 中文标签：mdview.py 的导航块用的是可读名字，不是 SECTION 标题
LABELS = {
    1: "常量与配置", 2: "内联 CSS", 3: "HTML 模板", 4: "语法高亮器", 5: "内联解析",
    6: "链接/图片重写", 7: "块级解析", 8: "目录索引 / 搜索页", 9: "HTTP 处理器",
    10: "CLI 与启动",
}


def render_nav(sections):
    """生成导航行（含真实行号）。行号是生成物，改代码后重跑本脚本。"""
    lines = [BEGIN]
    for num, title, line in sections:
        label = LABELS.get(num, title)
        lines.append("    [%-2d] %-20s %-26s mdview.py:%d" % (num, label, title, line))
    return "\n".join(lines) + "\n"


def splice(source):
    """把新的导航块替换进源码，返回 (新源码, 旧块文本, 新块文本)。

    只替换「紧跟 BEGIN 之后、格式匹配导航行的那些连续行」—— 这是唯一能
    精确定位的方式：模块 docstring 里没有 # 分隔带，用 # ==== 当结束标记
    会一路吃到 import（曾经因此删掉大段代码）。找不到或格式不符就报错拒改。
    """
    begin = source.index(BEGIN)
    after = source[begin + len(BEGIN):].split("\n")
    # 兼容两种格式：旧块结尾是 "SECTION 1  CONSTANTS"，新块结尾是 "mdview.py:57"
    # [1 ] 这种对齐空格也要容忍；两种格式都接受（旧块结尾 SECTION n，新块结尾 mdview.py:n）
    nav_line = re.compile(r"^\s*\[\s*\d+\s*\]\s*\S.*(mdview\.py:\d+|SECTION\s+\d+.*?)\s*$")
    body = []
    for line in after[1:]:              # after[0] 是 BEGIN 所在行的剩余部分
        if nav_line.match(line):
            body.append(line)
        else:
            break
    if not body:
        raise SystemExit("未找到导航行，拒绝改写（请人工检查 %s）" % TARGET)
    # 只替换导航行本身（BEGIN 那一行后面紧跟说明文字，不能一起当锚点）
    old = "\n".join(body)
    new = "\n".join(render_nav(section_lines(source)).split("\n")[1:]).rstrip("\n")
    if old not in source:
        raise SystemExit("导航块定位失败，拒绝改写")
    return source.replace(old, new, 1), old, new


def main(argv):
    check_only = "--check" in argv
    with open(TARGET, "r", encoding="utf-8") as fh:
        source = fh.read()
    updated, old, new = splice(source)
    if check_only:
        if old.strip() == new.strip():
            print("导航注释已同步 ✔")
            return 0
        print("导航注释与代码行号不一致，请运行: python3 sync_nav.py", file=sys.stderr)
        return 1
    if updated == source:
        print("导航注释已是同步状态，无需修改。")
        return 0
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("已更新 %s 的导航注释。" % os.path.basename(TARGET))
    for num, title, line in section_lines(updated):
        print("  [%-2d] %-24s 行 %d" % (num, title, line))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
