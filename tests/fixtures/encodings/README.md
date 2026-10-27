# 文件编码手动夹具

用于手动验证编码检测、编码标签、搜索解码与下载/raw charset。所有文件都在本地。

## 启动

在仓库根目录：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/encodings --trust --port 8003 --port-tries 0
```

打开 `http://127.0.0.1:8003/`。

## 文件与预期

| 文件 | 预期 |
|---|---|
| `gbk.md` | Markdown 正常渲染“中文标题”；页头显示 `GBK` |
| `gbk.txt` | 源码页正文正常；标签显示 `GBK` |
| `gbk.css` | 直接导航是源码页；`Sec-Fetch-Dest: style` 时返回原始字节与 `text/css; charset=gbk` |
| `utf16le.txt` | 源码页正文正常；标签显示 `UTF-16LE BOM` |
| `utf16.md` | Markdown 正常渲染“UTF-16 标题”；页头显示 `UTF-16LE BOM` |
| `utf32le.txt` | 不进入源码页，按 `application/octet-stream` 下载原始字节 |

搜索：

```text
http://127.0.0.1:8003/search?__mdview=search&q=中文
```

应命中 `gbk.md` 第 1 行（`/gbk.md#L1`），摘要为正确中文。

下载/raw：

```bash
curl -sI 'http://127.0.0.1:8003/gbk.txt?download=1' | grep -i content-type
# Content-Type: text/plain; charset=gbk

curl -sI -H 'Sec-Fetch-Dest: style' http://127.0.0.1:8003/gbk.css | grep -i content-type
# Content-Type: text/css; charset=gbk
```

HTML 原文不属于本夹具：它继续按 BOM/meta 自行解码，不带 charset。

## 自动化

`tests/selftest-rust.sh` 与 `tests/browser-probe.mjs` 会从本目录复制夹具；新增编码样本
时同时补 README 与自动断言。

## 已知限制

- 检测是启发式的；短小 legacy 文件可能误判（例如短 GBK 片段判成 EUC-KR/Big5）。
- 无 BOM 且以非 ASCII 为主的中文 UTF-16 可能识别失败；UTF-32 按二进制下载。
- 本轮不提供手动 `?encoding=` 覆盖。
