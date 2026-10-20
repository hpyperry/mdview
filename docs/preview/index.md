# 支持哪些文件在浏览器里直接看

这一页是**渲染效果总览**。下面每一个链接点开，看到的都是本服务对那种文件的真实处理方式。

判断规则（按顺序）：

| # | 条件 | 结果 |
|---|------|------|
| 1 | 超过 `--max-preview`（默认 20 MiB） | 准确类型 + `Content-Disposition: attachment` → **下载** |
| 2 | `.md` | **渲染成 HTML 页面**（未信任目录先出现确认页） |
| 3 | 命中源码/配置扩展名或文件名表 | **源码查看页**：行号、行锚点、客户端高亮 |
| 4 | 无扩展名且前 512 字节无 NUL | **源码查看页**（按文本处理） |
| 5 | 命中内置 MIME 表（图片、PDF 等） | 按表里的类型 → **浏览器内联显示** |
| 6 | 其余一切 | `application/octet-stream` → **浏览器下载** |

> 样例文件由 [`make_preview_samples.py`](make_preview_samples.py) 就地生成；
> 它是开发夹具工具，不是运行时依赖。图片都是真文件，可随时重跑重建。

---

## 1. 源码类（源码查看页）

中文注释、字符串、标识符应当**正常显示，不出现乱码**。

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
  ← 按纯文本显示（不做表格解析）
- [reStructuredText](text/sample.rst) `.rst`（按纯文本显示，不做 RST 渲染）
- [diff](text/sample.diff) `.diff`　[patch](text/sample.patch) `.patch`
- [空文件](text/empty.txt) ← 0 字节，应当显示空白页而不是报错
- [**GBK 编码的文本**](text/gbk-encoded.txt) ← 非 UTF-8，按 UTF-8 lossy 显示（可能乱码，但不下载）

## 4. 无扩展名、按文件名判定

- [Makefile](Makefile)　[Dockerfile](Dockerfile)　[.gitignore](.gitignore)　[README](README)

## 5. 图片（浏览器内联显示）

- [PNG](media/sample.png)　[BMP](media/sample.bmp)　[ICO](media/sample.ico)
- [SVG](media/sample.svg)（矢量，可缩放）
- [**GIF**](media/sample.gif) ← 两帧动画，应当**看到它在动**
- [**大图 1600×900**](media/sample-large.png) ← 比视口大，用来验证放大视图

### 图片放大（点下面这张图试）

正文里的图片会被包上一层可放大的链接：**禁用 JS** 时点一下直接打开原图，
**有 JS 时**弹出遮罩并按视口缩放居中（Esc / 点遮罩空白 / 右上角 × 关闭；
`Cmd`/`Ctrl` + 点击或中键走浏览器原生行为）。

![1600×900 网格大图（点击放大）](media/sample-large.png)

> **另有专项测试页**：[二进制 / 超大文件测试](binary-test.md) —— 512 字节嗅探边界、
> 真 ZIP/ELF/PDF、超过 20 MiB 的各类型文件，逐个标了预期行为。

`.jpg` / `.jpeg` / `.webp` / `.avif` 也在支持列表里，但本目录没有样例。

## 6. 会**下载**的

`.zip` `.docx` `.xlsx` `.pptx` `.tar` `.gz` 以及未知扩展名 → 下载。
这类文件不适合放在文档目录里，所以这里不放样例。

---

## 对照：`python3 -m http.server` 会怎样

| 文件 | 本服务 | `python3 -m http.server` |
|------|--------|--------------------------|
| `.md` | 渲染成页面 | `text/markdown`，浏览器显示源码 |
| `.py` `.sh` `.go` 等 | 源码查看页，中文正常 | `text/x-python` 等，**不带 charset → 中文乱码** |
| `.ts` | 按文本预览 | `video/mp2t`，**当成视频打不开** |
| `.cfg` `.ini` `.log` 等 | 文本 | `application/octet-stream` → 下载 |
| `.png` `.pdf` | 图片 / PDF | 同 |

---

[返回首页](../index.md) · [代码块专项测试](../guides/code-blocks.md) · [边界与约定](../guides/advanced.md)
