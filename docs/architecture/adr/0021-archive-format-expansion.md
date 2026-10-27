# 压缩包格式扩展：tar 家族与 ZIP 容器

**Status**: accepted（2026-10-26）。扩展
[ADR 0016](0016-archive-virtual-paths.md) 的格式列表；虚拟包路径、解压缓存、
安全上限与“不递归解包”保持不变。

ADR 0016 只支持 `.zip`、`.tar.gz`/`.tgz`、`.7z`。实际文档库还会遇到未压缩
`.tar`、bzip2/xz 压缩的 tar，以及 `.jar`、`.epub`、`.cbz` 这类本质是 ZIP 的
容器。用户要求增加这些预览，同时坚持单文件、纯 Rust 优先、不递归解包与现有
安全上限。

## 决定

### 1. tar 家族

支持：

| 扩展名 | 标签 | 解码器 |
|---|---|---|
| `.tar` | `tar` | `tar` crate |
| `.tar.gz` / `.tgz` | `tar.gz` | `flate2` |
| `.tar.bz2` / `.tbz2` / `.tbz` | `tar.bz2` | `bzip2`（`MultiBzDecoder`） |
| `.tar.xz` / `.txz` | `tar.xz` | `lzma-rust2` 的 `XzReader` |

`.tar.zst`/`.tzst`/`.tar.zstd` 本轮不支持：现有 zstd 解码器是 C 实现，虽然已在
ZIP 的 zstd 支持中使用，但为了不让新格式继续扩大 C 依赖，也不引入第二套纯 Rust
zstd 解码器，暂不把 `.tar.zst` 纳入虚拟包；这类文件仍按普通文件下载。

### 2. ZIP 容器

以下扩展名按 ZIP 结构解析，URL 仍是 `/a.jar/docs/x.md` 这种虚拟包路径：

`.zip`、`.jar`、`.war`、`.ear`、`.apk`、`.aar`、`.whl`、`.nupkg`、`.vsix`、
`.xpi`、`.ipa`、`.aab`、`.epub`、`.cbz`、`.kmz`。

它们是“归档浏览”，不是原生格式预览：`.epub` 不渲染成电子书阅读器，`.jar`/`.apk`
中的代码不执行，`.cbz` 的图片按普通图片预览。Office/ODF 容器（`.docx` 等）不在
本轮范围，避免把“打开包内 XML”误解成“渲染 Word/Excel/PPT”。

### 3. `.xhtml` 与清单文件

`.xhtml`/`.xht` 加入文本扩展名，包内章节（如 `.epub` 的 `OEBPS/chapter1.xhtml`）
进入现有源码页；不扩展 HTML 的 Trust/MIME 路径，不做 EPUB 阅读器。`.mf` 也加入
文本扩展名，便于查看 JAR 的 `META-INF/MANIFEST.MF`。

### 4. 标签

tar 别名归一到规范压缩格式名：`.tbz2`/`.tbz` 显示 `tar.bz2`，`.txz` 显示
`tar.xz`，`.tgz` 显示 `tar.gz`。ZIP 容器保留扩展名标签：`.zip` 显示 `ZIP`，
`.jar` 显示 `JAR`，`.epub` 显示 `EPUB`，`.cbz` 显示 `CBZ`。

### 5. 解码依赖与内存

- 新增直接依赖只有 `bzip2 0.6`（默认 `libbz2-rs-sys`，纯 Rust）与
  `lzma-rust2 0.22`（纯 Rust，`zip` 已引入同版本）；没有新增 C 库。
- `.tar.xz` 使用 `XzReader::new_mem_limit(reader, true, 128 MiB)`：xz 块头可以
  声明很大的字典，上限在解压前阻止异常分配；128 MiB 允许常见的 `xz -9` 预设。
- `.tar.bz2` 使用 `MultiBzDecoder`，支持 pbzip2 式多流；`.tar.xz` 允许多个 xz
  stream。
- `.tar.gz`、`.zip`、`.7z` 行为不变；`.zip` 内部已有的 bzip2/zstd/lzma/deflate64
  支持不变。

### 6. 安全与边界

- 继续使用 ADR 0016 的上限：包 200 MB、解压 1 GB、2 万条、单条 100 MB。
- 继续拒绝加密、多卷、绝对路径、`..`、NUL/反斜杠、软链/硬链、设备/管道文件、
  重复规范化路径与 Windows 大小写冲突路径。
- 仍然只有 URL 第一个压缩包段是容器；包内再遇到 `.zip`/`.tar.bz2` 等只当普通
  文件下载，不递归解包。
- `--safe` 下所有压缩包仍不可见；包内条目不进入全站搜索与导航展开。
- 加密 ZIP、分卷 ZIP、`.zipx` 的未启用压缩方法会按现有错误路径整包拒绝；这些
  文件不会变成可预览包。

## 考虑过的替代方案

- **`.tar.zst` 复用现有 C zstd**：不新增 crate，但新格式继续依赖 C；与“新格式
  纯 Rust 优先”冲突。保留为后续单独决策。
- **纯 Rust `ruzstd`**：可以严格纯 Rust，但会与 ZIP 已链接的 C zstd 并存，增加
  第二套解码器、体积和 1.4–3.5 倍解码耗时；本轮不做。
- **RAR/RAR5**：纯 Rust 方案（`unrar-rs`/`rars`/`rar-codec`）都较新或受限，C++
  UnRAR 绑定又带来许可证、C++ 工具链与 musl 未验证风险；本轮不做。
- **单文件 `.gz/.bz2/.xz/.zst` 流**：不是归档容器，没有条目列表；需要另一套
  “解压后单文件预览”的 URL 语义，和虚拟包路径混在一起会让人误解。
- **Office/ODF 容器**：`.docx` 等是 ZIP，但浏览包内 XML 不等于文档预览；容易
  制造错误预期，本轮不做。
- **libarchive / 外部 unrar**：破坏单文件、零外部运行时依赖与跨平台一致性。

## 后果

- 包根页与目录页会显示新的格式标签；`.jar`/`.epub`/`.cbz` 等直接进入虚拟包。
- `.xhtml`/`.xht`/`.mf` 真实文件也会按源码页打开，并进入文本搜索范围。
- tar.bz2/tar.xz 首次打开比 tar.gz 慢；解压结果仍走现有缓存。
- xz 字典超过 128 MiB 的包会被拒绝；这是资源保护，不是压缩包体积上限变化。
- ZIP 容器仍受 2 万条目、100 MB 单条与 1 GB 解压总量限制；大型 `.apk`/`.jar`
  可能因此整包失败。
- 需要新增 tar.bz2/tar.xz、jar/epub/cbz 夹具与黑盒/浏览器断言；二进制夹具在
  `.gitattributes` 标记。
