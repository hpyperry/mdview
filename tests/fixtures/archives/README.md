# 压缩包复测文档

关联：Issue #20 / F-92。用于手动验证压缩包虚拟目录、tar 家族与 ZIP 容器。

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/archives --trust --port 8002 --port-tries 0
```

入口：

- `/sample.tar/`、`/sample.tar.gz/`、`/sample.tar.bz2/`、`/sample.tar.xz/`
- `/sample.zip/`、`/sample.jar/`、`/sample.epub/`、`/sample.cbz/`
- `/sample.7z/`

## 复测步骤

1. 打开包根页。
   预期：显示包名、格式标签、大小、条目数与“下载压缩包”；tar 别名显示规范标签
   （`.tar.bz2`、`.tar.xz`），ZIP 容器显示扩展名标签（`JAR`、`EPUB`、`CBZ`）。
2. 打开 `/sample.tar.bz2/docs/a.md`、`/sample.tar.xz/docs/a.md`。
   预期：与 `/sample.zip/docs/a.md` 一样渲染 Markdown；图片地址保持在当前包内。
3. 打开 `/sample.jar/META-INF/MANIFEST.MF`。
   预期：源码页，可看到 `Manifest-Version`。
4. 打开 `/sample.epub/OEBPS/chapter1.xhtml`。
   预期：按源码页显示 XHTML 行号与内容（不渲染成电子书页面）。
5. 打开 `/sample.cbz/page-01.png`。
   预期：图片内联预览；包根页可进入 `page-02.png` 与 `info.md`。
6. 打开 `/sample.tar/inner.zip`。
   预期：作为普通文件下载，不递归解压。
7. 打开 `/high-dict.tar.xz/`。
   预期：整包拒绝并显示错误（xz 字典超过解码器 128 MiB 内存上限）。
8. 用 `--safe` 启动，打开任意包根路径。
   预期：404，不进入包内。
9. `?download=1` 下载整包或条目。
   预期：整包返回原始字节；条目返回解压后的字节与附件头。

## 自动化覆盖

- `src/archive.rs`：扩展名/别名检测、标签、tar 三件套提取、ZIP 容器、xz 内存上限。
- `src/server.rs`：虚拟路径、ZIP 容器标签、`.xhtml` 源码页、嵌套包、safe、错误路径。
- `tests/selftest-rust.sh`：真二进制上的 tar.bz2/tar.xz、jar/epub/cbz、`.xhtml`。
- `tests/browser-probe.mjs`：ZIP 容器页面与 `.epub` 章节源码页。

## 已知限制

- 不支持 `.tar.zst`/`.tzst`/`.tar.zstd`、RAR/RAR5、单文件 `.gz/.bz2/.xz/.zst` 流、
  Office/ODF 容器（`.docx` 等）与 `.zipx`。
- 嵌套压缩包只当普通文件下载，不递归解压。
- `.epub` 只是 ZIP 归档浏览，`.xhtml` 不渲染成阅读器页面；`.jar`/`.apk` 中的代码
  不会执行。
- 加密、多卷、损坏包整包拒绝；条目超过 2 万或解压超过 1 GB 也会拒绝。
- xz 解码器内存上限 128 MiB；异常大字典的包会被拒绝。

## 清理

停止临时服务并释放端口；进程退出会清理自己的解压缓存。
