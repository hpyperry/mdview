# 文件编码检测与 UTF-8 预览

**Status**: accepted（2026-10-27）

当前 Markdown、源码页与搜索都直接 `String::from_utf8_lossy`：GBK/Shift_JIS 文件
预览乱码，UTF-16 因含 NUL 被当二进制下载。决定增加启发式编码检测，让 mdview
生成的预览统一解码成 UTF-8，同时在页面上显示检测编码；HTML 原文仍遵守
[ADR 0015](0015-html-file-preview-and-sandbox.md)，不强制 charset、不转码。

## 决定

### 1. 检测顺序

1. **BOM 优先**：UTF-8 BOM、UTF-16LE/BE BOM 直接确定编码。UTF-32 BOM
   （`FF FE 00 00` / `00 00 FE FF`）必须在 UTF-16 判断前识别；UTF-32 不支持预览，
   按二进制下载。
2. **合法 UTF-8 快速路径**：完整字节通过 UTF-8 校验即为 UTF-8；ASCII 也标为
   UTF-8。
3. **无 BOM UTF-16 启发式**：只对 Markdown 文档与已知文本扩展名/文件名启用；
   用奇偶位 NUL 比例做高置信度判断。失败就回到普通检测；不把扩展名未知的
   NUL 文件猜成 UTF-16。
4. **chardetng**：非法 UTF-8 且没有强 UTF-16 信号时，用 `chardetng 1.0` 对样本
   做启发式检测；允许 UTF-8 候选，允许 ISO-2022-JP（输出只进 HTML 文本，不执行）。
   没有匹配时按 UTF-8 替换解码。
5. **UTF-32**：只识别 BOM 并拒绝预览；不猜无 BOM UTF-32。

检测样本最多 64 KiB；预览/搜索在完整字节上做 UTF-8 校验，并在首个非 ASCII
附近取窗口喂检测器。流式下载/raw 只读前 64 KiB，BOM 优先。

### 2. 解码与输出

- 预览与搜索使用完整源字节解码；按检测编码解码成 Unicode，再以 UTF-8 输出
  HTML/源码页。BOM 从预览文本中移除。
- 解码出现替换字符（U+FFFD）时继续预览，但编码标签追加 `（有替换）`。
- 生成页面始终 UTF-8；源文件不被改写。

### 3. 显示范围

- Markdown 文档页头部：`Markdown · 大小 · <编码> · 更新时间`。
- 源码页标签：类型、大小、行数、`编码 <编码>`、更新时间；`.mdx`、HTML 源码页、
  压缩包内文本同样适用。
- 编码标签：BOM 追加 ` BOM`（如 `UTF-8 BOM`、`UTF-16LE BOM`）；有替换字符时
  追加 `（有替换）`。`title`/`aria-label` 写明“检测编码”。
- 目录列表不加编码列；搜索页不显示编码标签。
- **HTML 原文/沙箱 iframe 不显示、不转码**：trusted 根仍原字节、无 charset；
  untrusted iframe 仍由浏览器按 BOM/meta 解码。

### 4. 下载与子资源

- `?download=1`、`?raw=` 子资源始终发送原始字节。
- 非 HTML 文本（Markdown、纯文本、JSON、CSS、JS、XML）的 `Content-Type`
  charset 使用检测值；HTML 响应（trusted 原文、HTML 下载、HTML 子资源）保持
  `text/html` 不带 charset。
- 流式响应只按前 64 KiB 检测 charset；大文件后段若有不同编码，头部可能不准确。
  预览/搜索不受这个限制，它们用完整字节。

### 5. 搜索与缓存

- 搜索正文使用同一检测/解码结果；行号与摘要基于解码后的文本。
- Markdown 渲染缓存键仍是 `(path, mtime, size)`；HTML 中包含编码标签，源文件
  变化会失效。源码页与搜索每次按需检测。
- 合法 UTF-8 是快速路径，不跑 chardetng；只有非法 UTF-8 才进入启发式检测。

### 6. 依赖与许可

- 新增 `chardetng 1.0`（Apache-2.0 OR MIT）；沿用现有 `encoding_rs` 解码。
- 更新 `THIRD-PARTY-NOTICES.md` 与依赖审计；保持单文件、运行时零外部请求。

## 考虑过的替代方案

- **只支持 UTF-8/BOM**：不新增依赖，但 GBK/Shift_JIS 仍乱码，不满足需求。
- **只用 encoding_rs 手写启发式**：产物更小，但中文/日文误判概率明显更高。
- **让 HTML 也按检测编码转码**：会让 HTML 的 BOM/meta 声明失效，破坏 ADR 0015
  的静态文件语义；否决。
- **无 BOM UTF-16 也用于未知扩展名**：NUL 启发式误伤二进制的风险高；否决。
- **下载/raw 也读完整文件再定 charset**：破坏流式响应和大文件内存边界；否决。
- **目录列表增加编码列**：超出“预览时显示”的需求，且每次列目录都要读文件；
  否决。

## 后果与已知限制

- “检测编码”是启发式结果，不保证等于文件的真实编码；UI 不写“实际编码”。
- 无 BOM 且以非 ASCII 为主的中文 UTF-16 仍可能无法识别；UTF-32 一律下载。
- 流式下载/raw 的 charset 基于前缀，可能与完整文件不一致。
- 编码检测会增加非 UTF-8 文件的 CPU 开销；UTF-8 文件走快速路径。
- HTML 原文没有 mdview 外壳，因此无法显示检测编码；这是 ADR 0015 的既有边界。
