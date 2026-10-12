# 支持哪些文件在浏览器里直接看

这一页是**渲染效果总览**。下面每一个链接点开，看到的都是本服务对那种文件的真实处理方式。

判断规则只有四条（按顺序）：

| # | 条件 | 结果 |
|---|------|------|
| 1 | `.md` | **渲染成 HTML 页面** |
| 2 | 命中源码/配置类扩展名或文件名表 | `text/plain; charset=utf-8` → **内联显示，中文正常** |
| 3 | 命中内置 MIME 表（图片、PDF 等） | 按表里的类型 → **内联显示** |
| 4 | 其余一切 | `application/octet-stream` → **浏览器下载** |

> 这些样例文件由 [`make_preview_samples.py`](make_preview_samples.py) 就地生成，
> 图片全部是**纯标准库**构造的真文件（不是占位文本），可随时重跑重建。

---

## 1. 源码类（`text/plain; charset=utf-8`）

中文注释、字符串、标识符都应当**正常显示，不出现乱码**。

- [Python](code/sample.py) `.py`　[Shell](code/sample.sh) `.sh`
- [C](code/sample.c) `.c`　[C++](code/sample.cpp) `.cpp`　[头文件](code/sample.h) `.h`
- [Java](code/sample.java) `.java`　[Go](code/sample.go) `.go`　[Rust](code/sample.rs) `.rs`
- [TypeScript](code/sample.ts) `.ts` ← 注意它**不会**被当成视频
- [JSX](code/sample.jsx) `.jsx`　[SQL](code/sample.sql) `.sql`

## 2. 配置与数据

- [YAML](config/sample.yaml) `.yaml`　[TOML](config/sample.toml) `.toml`
- [INI](config/sample.ini) `.ini`　[properties](config/sample.properties) `.properties`
- [JSON](config/sample.json) `.json`　[XML](config/sample.xml) `.xml`
- [`.env`](config/.env) ← 无扩展名的点文件

## 3. 纯文本类

- [普通文本](text/sample.txt) `.txt`　[日志](text/sample.log) `.log`
- [CSV](text/sample.csv) `.csv`　[TSV](text/sample.tsv) `.tsv`
- [reStructuredText](text/sample.rst) `.rst`（按纯文本显示，不做 RST 渲染）
- [diff](text/sample.diff) `.diff`　[patch](text/sample.patch) `.patch`
- [空文件](text/empty.txt) ← 0 字节，应当显示空白页而不是报错
- [**GBK 编码的文本**](text/gbk-encoded.txt) ← 这个文件不是 UTF-8，用来验证编码兜底

## 4. 无扩展名、按文件名判定

- [Makefile](Makefile)　[Dockerfile](Dockerfile)　[.gitignore](.gitignore)　[README](README)

## 5. 图片（浏览器内联显示）

- [PNG](media/sample.png)　[BMP](media/sample.bmp)　[ICO](media/sample.ico)
- [SVG](media/sample.svg)（矢量，可缩放）
- [**GIF**](media/sample.gif) ← 两帧动画，应当**看到它在动**（证明按图片处理而非静态文本）

`.jpg` / `.jpeg` / `.webp` / `.avif` 也在支持列表里，但**本目录没有样例** ——
它们是有损/复杂格式，纯标准库造不出有意义的内容。放一个真文件进目录即可验证。

## 6. 会**下载**的（不是 bug，是标准库的推断结果）

`.zip` `.docx` `.xlsx` `.pptx` `.tar` `.gz` 以及未知扩展名 → `application/octet-stream` → 下载。
这类文件不适合放在文档目录里，所以这里不放样例。

---

## 对照：`python3 -m http.server` 会怎样

| 文件 | 本服务 | `python3 -m http.server` |
|------|--------|--------------------------|
| `.md` | 渲染成页面 | `text/markdown`，浏览器显示源码 |
| `.py` `.sh` `.go` 等 | `text/plain; charset=utf-8`，中文正常 | `text/x-python` 等，**不带 charset → 中文乱码** |
| `.ts` | `text/plain` | `video/mp2t`，**当成视频打不开** |
| `.cfg` `.ini` `.log` 等 | 文本 | `application/octet-stream` → 下载 |
| `.png` `.pdf` | 图片 / PDF | 同 |

---

[返回首页](../index.md) · [代码块专项测试](../guide/code-blocks.md) · [边界与约定](../guide/advanced.md)
