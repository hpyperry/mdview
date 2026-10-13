#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_preview_samples.py —— 生成 docs/preview/ 下的渲染样例文件。

这些样例用来在浏览器里逐一看「本服务支持内联渲染哪些文件」。全部用 Python
标准库就地生成，因此**不需要把二进制图片提交进仓库** —— 想重建随时跑本脚本：

    python3 docs/preview/make_preview_samples.py

生成内容：
    code/     各种源码与配置（命中 TEXT_EXT，按 text/plain; charset=utf-8 发送）
    config/   配置与数据类
    text/     纯文本类（含一个 GBK 文件，用来验证编码声明）
    media/    png / bmp / gif（动图）/ ico / svg —— 浏览器可内联显示的真图片
              （含一张 1600×900 带网格的大图，用来验证放大视图确实按视口缩放）
"""

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# 纯标准库生成合法图片（每种都已在 Chrome 里验证 naturalWidth/naturalHeight）
# --------------------------------------------------------------------------

def write_png(path, size=120, rgb=(9, 105, 218), grid=0):
    """8 位真彩 PNG。

    size 既可以是边长，也可以是 (宽, 高)。grid > 0 时每 grid 像素画一条白线，
    最外圈也画满 —— 单色方块看不出「被缩放到视口里」这回事，带网格的大图才能
    一眼看出放大视图到底缩了多少（见 media/sample-large.png）。
    """
    w, h = (size, size) if isinstance(size, int) else size
    plain = bytes(rgb) * w

    def edge(x, n):
        return x % grid == 0 or x == n - 1

    if grid:
        marked = b"".join(bytes((255, 255, 255)) if edge(x, w) else bytes(rgb)
                          for x in range(w))
        raw = b"".join(b"\x00" + (marked if edge(y, h) else plain)
                       for y in range(h))
    else:
        raw = b"".join(b"\x00" + plain for _ in range(h))

    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body +
                struct.pack(">I", zlib.crc32(body) & 0xffffffff))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
                 chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def write_bmp(path, size=120, rgb=(9, 105, 218)):
    """24 位未压缩 BMP。"""
    w = h = size
    row = bytes(rgb) * w
    pad = b"\x00" * ((-w * 3) % 4)
    pixels = (row + pad) * h
    header = struct.pack("<2sIHHI", b"BM", 14 + 40 + len(pixels), 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pixels),
                      2835, 2835, 0, 0)
    with open(path, "wb") as fh:
        fh.write(header + dib + pixels)


def _gif_lzw(indices, min_code=2):
    """极简 LZW：只发 clear + 逐像素 + end，不做字典压缩（演示足够）。"""
    clear = 1 << min_code
    end = clear + 1
    codes = [clear] + list(indices) + [end]
    out = bytearray()
    cur = n = 0
    code_size = min_code + 1
    for c in codes:
        cur |= c << n
        n += code_size
        while n >= 8:
            out.append(cur & 0xFF)
            cur >>= 8
            n -= 8
    if n:
        out.append(cur & 0xFF)
    return bytes(out)


def write_gif(path, size=120, frames=((9, 105, 218), (218, 96, 9))):
    """两帧动画 GIF，验证浏览器会动（不是静态图）。"""
    w = h = size
    # 调色板：索引 0/1/2 依次是各帧颜色，索引 3 白色
    pal = b"".join(bytes(c) for c in frames) + b"\xff\xff\xff"
    pal += b"\x00" * (12 - len(pal))                 # 补齐 4 色 * 3 字节
    out = bytearray(b"GIF89a" + struct.pack("<HH", w, h) + b"\xf1\x00\x00" + pal)
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"   # 无限循环
    for idx in range(len(frames)):
        out += b"\x21\xf9\x04\x00\x0a\x00\x00\x00"           # 10/100 秒延时
        out += b"\x2c" + struct.pack("<HHHH", 0, 0, w, h) + b"\x00"
        data = _gif_lzw(bytes([idx]) * (w * h))
        out += b"\x02" + bytes([len(data) & 0xFF]) + data + b"\x00"
    out += b"\x3b"
    with open(path, "wb") as fh:
        fh.write(bytes(out))


def write_ico(path, size=64, rgb=(9, 105, 218)):
    """ICO（内含 32 位 BMP + AND 掩码）。"""
    w = h = size
    bgra = bytes([rgb[2], rgb[1], rgb[0], 255])
    pixels = b"".join(bgra * w for _ in range(h))
    mask = b"\x00" * ((((w + 31) // 32) * 4) * h)
    dib = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                      len(pixels) + len(mask), 2835, 2835, 0, 0)
    img = dib + pixels + mask
    header = (struct.pack("<HHH", 0, 1, 1) +
              bytes([w % 256, h % 256, 0, 0]) +
              struct.pack("<HHII", 1, 32, len(img), 22))
    with open(path, "wb") as fh:
        fh.write(header + img)


# --------------------------------------------------------------------------
# 文本样例
# --------------------------------------------------------------------------

PY = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文注释：验证 .py 在浏览器里的编码是否正确。"""

import os
from typing import Dict, List


MAX_RETRY = 3
PI = 3.14159


class 中文类名:
    """三引号字符串里的中文也应该正常。"""

    def __init__(self, root: str, depth: int = 0) -> None:
        self.root = root
        self._cache: Dict[str, str] = {}

    def 渲染(self, paths: List[str]) -> str:
        if not paths:
            return "空"
        return "\\n".join(f"{p}: {os.path.getsize(p)}" for p in paths)


if __name__ == "__main__":
    print(中文类名(".").渲染(["README.md"]))
'''

SAMPLES = {
    "code/sample.py": ("python", PY),
    "code/sample.sh": ("bash", '''#!/usr/bin/env bash
# 中文注释：Shell 脚本
set -euo pipefail

ROOT="${1:-docs}"
echo "服务根目录：$ROOT"
for f in "$ROOT"/*.md; do
  printf '  %s (%s 行)\\n' "$f" "$(wc -l < "$f")"
done | sort | head -5
'''),
    "code/sample.c": ("c", '''#include <stdio.h>
/* 中文注释：C 语言 */
#define MAX 128

int main(void) {
    int 计数 = 0;
    for (int i = 0; i < MAX; i++) {
        计数 += i;
    }
    printf("结果=%d\\n", 计数);
    return 0;
}
'''),
    "code/sample.cpp": ("cpp", '''// 中文注释：C++
#include <string>
#include <vector>

template <typename T>
class 栈 {
public:
    void push(const T& v) { items_.push_back(v); }
    bool empty() const { return items_.empty(); }
private:
    std::vector<T> items_;
};
'''),
    "code/sample.h": ("c", '''/* 中文注释：头文件 */
#ifndef SAMPLE_H
#define SAMPLE_H

struct 配置 {
    const char *名称;
    int 端口;
};

int 启动(const struct 配置 *cfg);

#endif
'''),
    "code/sample.java": ("java", '''// 中文注释：Java
package com.example;

public class 示例 {
    private static final int 上限 = 100;

    public static void main(String[] args) {
        System.out.println("中文输出：" + 上限);
    }
}
'''),
    "code/sample.go": ("go", '''// 中文注释：Go
package main

import "fmt"

type 服务器 struct {
	名称 string
	端口 int
}

func main() {
	s := 服务器{名称: "mdview", 端口: 8000}
	fmt.Printf("%s:%d\\n", s.名称, s.端口)
}
'''),
    "code/sample.rs": ("rust", '''// 中文注释：Rust
use std::collections::HashMap;

fn main() {
    let mut 映射: HashMap<u64, String> = HashMap::new();
    映射.insert(1, String::from("中文"));
    for (k, v) in &映射 {
        println!("{} => {}", k, v);
    }
}
'''),
    "code/sample.ts": ("typescript", '''// 中文注释：TypeScript（注意 .ts 不能被当成视频）
interface 文档 {
  id: number;
  title: string;
}

const 加载 = async (path: string): Promise<文档> => {
  return { id: 1, title: `中文标题 ${path}` };
};
'''),
    "code/sample.jsx": ("jsx", '''// 中文注释：JSX
export default function 按钮({ 文本 }) {
  return <button onClick={() => alert("中文")}>{文本}</button>;
}
'''),
    "code/sample.sql": ("sql", '''-- 中文注释：SQL
SELECT d.id, d.title, COUNT(c.id) AS 评论数
FROM docs AS d
LEFT JOIN comments AS c ON c.doc_id = d.id
WHERE d.status = 'active'
GROUP BY d.id, d.title
ORDER BY 评论数 DESC
LIMIT 10;
'''),
    "config/sample.yaml": ("yaml", '''# 中文注释：YAML
name: mdview
版本: 1.0.0
服务:
  地址: 0.0.0.0
  端口: 8000
  安全模式: false
特性:
  - 搜索
  - 高亮
  - 复制按钮: true
'''),
    "config/sample.toml": ("toml", '''# 中文注释：TOML
[server]
host = "0.0.0.0"
port = 8000
中文键 = "中文值"

[features]
search = true
highlight = true
'''),
    "config/sample.ini": ("ini", '''; INI 的分号注释本轮不着色（分号在 C/JS 里是语句结束符）
[mdview]
host=0.0.0.0
port=8000
safe=true
# 井号注释会着色
verbose=false
'''),
    "config/sample.json": ("json", '''{
  "名称": "mdview",
  "version": "1.0.0",
  "依赖": [],
  "特性": { "搜索": true, "高亮": true, "计数": 3 },
  "标签": ["离线", "标准库", null]
}
'''),
    "config/sample.xml": ("xml", '''<?xml version="1.0" encoding="UTF-8"?>
<!-- 中文注释：XML -->
<配置>
  <服务 地址="0.0.0.0" 端口="8000">中文文本</服务>
  <特性>搜索</特性>
</配置>
'''),
    "config/.env": ("env", '''# 中文注释：无扩展名的点文件
PORT=8000
HOST=0.0.0.0
备注=中文值
'''),
    "config/sample.properties": ("properties", '''# 中文注释：Java properties
server.port=8000
server.name=中文名称
'''),
    "text/sample.txt": ("plain", '''中文纯文本样例
================

这一行是第二行，用来确认换行没有被改动。
第三行包含特殊字符：< > & " ' 以及 emoji 🙂🚀
'''),
    "text/sample.log": ("log", '''2026-10-12 21:00:01 INFO  服务启动，根目录=/docs
2026-10-12 21:00:02 WARN  端口 8000 被占用，尝试 8001
2026-10-12 21:00:03 ERROR 中文错误信息：找不到配置文件
2026-10-12 21:00:04 INFO  已渲染 12 篇文档
'''),
    "text/sample.csv": ("csv", '''名称,端口,说明
mdview,8000,中文说明
搜索,8001,"含逗号, 的字段"
'''),
    "text/sample.tsv": ("tsv", '''名称\t端口\t说明
mdview\t8000\t中文说明
'''),
    "text/sample.rst": ("rst", '''中文 RST 样例
==============

这是 ``rst`` 文件，浏览器里按纯文本显示（不做 RST 渲染）。

* 列表项一
* 列表项二
'''),
    "text/sample.diff": ("diff", '''--- a/mdview.py
+++ b/mdview.py
@@ -1,3 +1,4 @@
 # 中文注释
-旧的一行
+新的一行（中文）
+再新增一行
'''),
    "text/sample.patch": ("patch", '''*** 原文
--- 修改
***************
*** 1,3 ****
  中文上下文
! 旧内容
--- 1,3 -----
  中文上下文
! 新内容
'''),
    "text/empty.txt": ("plain", ""),
    "Makefile": ("makefile", '''# 中文注释：Makefile（无扩展名，按文件名判定为文本）
PY := python3
PORT ?= 8000

.PHONY: run test

run:
	$(PY) mdview.py --root docs --port $(PORT)

test:
	$(PY) tests/tests_render.py && bash tests/selftest.sh
'''),
    "Dockerfile": ("dockerfile", '''# 中文注释：Dockerfile
FROM python:3.12-slim AS builder
ENV LANG=C.UTF-8
WORKDIR /app
COPY mdview.py ./
RUN echo "中文构建步骤"
EXPOSE 8000
CMD ["python3", "mdview.py"]
'''),
    ".gitignore": ("gitignore", '''# 中文注释：.gitignore（点文件，按文件名判定为文本）
__pycache__/
*.pyc
.DS_Store
'''),
}

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120" viewBox="0 0 160 120">
  <rect width="160" height="120" rx="10" fill="#0d1117" stroke="#3d444d"/>
  <circle cx="40" cy="40" r="18" fill="#4493f8"/>
  <rect x="70" y="26" width="70" height="10" rx="5" fill="#9198a1"/>
  <rect x="70" y="46" width="50" height="10" rx="5" fill="#3d444d"/>
  <text x="20" y="92" font-family="monospace" font-size="13" fill="#e6edf3">SVG 中文</text>
</svg>
'''


def write_text(rel, text, encoding="utf-8"):
    path = os.path.join(HERE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text.encode(encoding))
    return path


def main():
    count = 0
    for rel, (_kind, text) in sorted(SAMPLES.items()):
        write_text(rel, text)
        count += 1
    # 一个 GBK 编码文件：验证「非 UTF-8 文本」在浏览器里的表现
    write_text("text/gbk-encoded.txt",
               "中文 GBK 编码样例\n================\n\n"
               "这个文件是以 GBK 编码保存的。\n"
               "如果响应头没声明 charset，浏览器会按默认编码解 -> 乱码；\n"
               "声明 charset=gb18030 之后应当正常显示。\n",
               encoding="gbk")
    count += 1
    # 无扩展名之外，再放一个「无扩展名的纯文本」验证文件名判定
    write_text("README", "这是无扩展名的 README 文件，按文件名判定为文本。\n")
    count += 1
    # 图片（二进制，就地生成）
    write_text("media/sample.svg", SVG)
    count += 1
    write_png(os.path.join(HERE, "media", "sample.png"))
    write_png(os.path.join(HERE, "media", "sample-large.png"),
              size=(1600, 900), grid=160)
    write_bmp(os.path.join(HERE, "media", "sample.bmp"))
    write_gif(os.path.join(HERE, "media", "sample.gif"))
    write_ico(os.path.join(HERE, "media", "sample.ico"))
    count += 5
    print("已生成 %d 个样例文件到 %s" % (count, HERE))


if __name__ == "__main__":
    main()
