# mdview

mdview 是一个**单文件、离线、零外部请求**的文档预览服务器。用 Rust 写成一个可执行
文件，把一个目录变成可浏览的文档站：Markdown 渲染、源码查看、目录浏览、全文搜索、
压缩包虚拟目录与文件下载都可以直接在浏览器里完成。

## 能力

- **Markdown 预览**：CommonMark + GFM（表格、删除线、自动链接），对齐 VS Code 的
  渲染与代码高亮；支持右侧 TOC、代码块复制、图片放大、导出图片 / PDF。
- **源码查看**：行号、`#L<n>` 行锚点、语法高亮；大文件按可见分块懒加载，超大单块
  交给同源 Web Worker 在后台高亮，超时自动回落纯文本。
- **目录与文件**：统一的目录列表、文件大小与修改时间、面包屑、文件下载；可信根下
  可以把整个文件夹打包成 zip 下载。
- **全文搜索**：文件名覆盖所有文件，正文覆盖 Markdown 与文本；分批扫描、渐进追加。
- **文件内查找与复制**：在文档/源码页内查找并上下切换匹配，一键复制原始全文。
- **压缩包浏览**：ZIP（含 JAR/EPUB/CBZ 等容器）、tar 家族与 7z 以虚拟目录浏览，
  包内条目复用 Markdown、源码、图片与下载管线。
- **编码检测**：GBK、Shift_JIS、UTF-16 等文本先检测再预览，下载与 raw 保留原始字节。
- **Trust 与 CSP**：未信任目录有一次性确认；未信任 HTML 在独立的第二 origin 运行；
  CSP 默认严格，脚本只信任 per-response nonce。
- **主题与导航**：跟随系统 / 浅色 / 深色，全站导航、TOC、快捷键与响应式布局。
- **离线单文件**：所有 CSS、JavaScript、高亮包与 Worker 都内嵌在二进制里，运行时
  不请求任何外部资源。

使用手册（含每个功能的操作步骤与截图）：
[`docs/manual/README.md`](docs/manual/README.md)。

## 手动编译与运行

需要 Rust 1.89+ 与 Node.js 22+。

```bash
npm --prefix web ci
cargo build --release
```

启动：

```bash
./target/release/mdview --root ./docs --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000/
```

`--root` 可以是任意目录；默认只监听本机，需要局域网访问时把 `--host` 改成
`0.0.0.0`。其余参数（`--trust`、`--safe`、`--max-preview`、`--no-search`、
`--security-level` 等）见使用手册。

交叉编译 Linux musl 目标时，先构建 Web 资产并复用：

```bash
npm --prefix web run build:web
MDVIEW_WEB_PREBUILT=web/dist cross build --release --locked \
  --target x86_64-unknown-linux-musl
```

产物只有一个 `mdview` 可执行文件，部署时不需要 Node、Python 或任何动态资源。

## License

MIT。见 [`LICENSE`](LICENSE)。
