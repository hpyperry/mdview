# Changelog

## 未发布

### 新增

- 文件编码检测与预览：BOM → UTF-8 校验 → UTF-16 启发式 → chardetng；GBK、
  Shift_JIS、UTF-16 BOM 文件解码为 Unicode 后输出 UTF-8。Markdown 页头与源码页
  显示检测编码（含 BOM/有替换后缀）；搜索正文使用同一解码。
- 非 HTML 文本的 `?download=1` 与 raw 子资源 charset 使用检测值；HTML 响应保持
  `text/html` 不带 charset。UTF-32 按二进制下载。
- 全站导航改为分层预载：初始只取根 + 三层目录，深层目录通过
  `/_nav?__mdview=nav&dir=<相对路径>` 按需展开一层；`active=<当前路径>` 脊柱让深页
  打开导航一次定位当前文件；桌面悬停约 150ms 预热下一层。不再在每个页面空闲时
  递归扫描并传输整棵树。
- 压缩包格式扩展：新增 `.tar`、`.tar.bz2`/`.tbz2`/`.tbz`、`.tar.xz`/`.txz`，以及
  `.jar`/`.war`/`.ear`/`.apk`/`.aar`/`.whl`/`.nupkg`/`.vsix`/`.xpi`/`.ipa`/`.aab`/
  `.epub`/`.cbz`/`.kmz` 等 ZIP 容器；包内 `.xhtml`/`.xht`/`.mf` 按源码页查看。
  `.tar.xz` 使用纯 Rust `XzReader`，128 MiB 解码器内存上限。

### 已知限制

- 编码检测是启发式的；短小 legacy 文件可能误判，无 BOM 的中文 UTF-16 可能识别
  失败；本轮不提供手动编码覆盖。
- 导航第 3 层目录在展开前不知道是否为空，统一显示展开箭头；单个超大目录仍一次
  列出全部条目，未做分页/虚拟滚动。
- 压缩包不支持 `.tar.zst`/RAR/RAR5/单文件 `.gz`/`.bz2`/`.xz`/`.zst` 流与
  Office/ODF 容器（`.docx` 等）；ZIP 容器只做归档浏览，不渲染 EPUB/Office 原生
  格式。嵌套包不递归解包。

### 测试

- 手动夹具按 feature 收拢到 `tests/fixtures/<feature>/`，每个目录可直接作为
  `--root` 启动；编码目录补齐 README、UTF-16 Markdown 与 UTF-32 样本，黑盒测试
  从目录整体复制。
- 开发流程固化：每个 feature/fix 在 `tests/fixtures/<slug>/README.md` 新增/更新人工
  复测文档（纯修复可 README-only），PR 描述与受影响 `F-xx` 链接它；`docs/testing/`
  只放执行记录与报告。
- 压缩包夹具补齐 tar.bz2/tar.xz、高字典 xz、JAR/EPUB/CBZ 与 `.xhtml`；黑盒与浏览器
  探针覆盖新格式、包内章节源码页与 `--safe` 隐藏。

### 修复

- 修复导航开关在加载状态变化时重复注册监听器、可能连续 toggle 的竞态。

## 2.1.0（2026-10-27）

静态服务器兼容、内部 URL 查询参数消歧与 Markdown 扩展名口径。

### 变更

- 内部 URL 改用查询参数消歧：搜索页、导航 JSON、内嵌资产分别为
  `/search?__mdview=search`、`/_nav?__mdview=nav`、`/_assets/<name>?__mdview=asset`。
  不带标记的同路径按普通文件处理，同名文件/目录优先。
- `.markdown` 按 Markdown 文档渲染并进入正文搜索；`.mdx` 保持源码页（MDX 标签）。
- 源码页编码标签只显示编码名（如 `GBK`），与 Markdown 页头一致；`title` 仍为
  “检测编码”。
- 目录始终列目录，不自动寻找 `index.html`/`index.htm`（明确非目标）。

### 破坏性变更

- 旧的不带 `__mdview` 标记的 `/search`、`/_nav`、`/_assets/*` 不再作为内部别名；
  旧搜索书签、旧导航请求与旧缓存页面里的资产请求会失效。

### 修复

- 文件路径带尾斜杠（字面 `/` 或 `%2f`）返回 404，与 Python 静态服务器及压缩包条目一致。
- `--safe` 的帮助文本改为与行为一致：放行 `.md`/`.markdown`、图片与 HTML 源码。
- `--safe` 下搜索不再扫描被拦截的文本/压缩包文件，避免直连 404 但搜索结果泄漏正文。
- `--safe` 现在也放行 `.markdown`，与新的 Markdown 扩展名口径一致。

## 2.0.1（2026-10-21）

HTML 文件 Trust 门控、压缩包虚拟目录、目录行布局与导航容错。

### 新增

- HTML 文件按 Trust 门控：已信任根 `/x.html` 直接以 `text/html` 顶层返回原文，
  无外壳/沙箱/CSP，脚本、localStorage、同源 fetch、下载与顶层链接都正常（Python/
  静态服务器行为）；未信任根才用外壳 + 沙箱 iframe，脚本处于 opaque origin。
  `?raw=1` 始终源码，`?view=1` 在可信时是原文、未信任时是沙箱裸页。
- HTML 预览子资源按真实 MIME 返回：相对 CSS/JS/JSON 可加载，直接导航仍进源码页；
  HTML 内容命中在搜索里跳到 `?raw=1#L<n>`。
- SVG 直开加 `CSP: sandbox`，内嵌 `<script>` 不再以同源执行。
- 压缩包预览：`.zip` / `.tar.gz` / `.tgz` / `.7z` 映射为虚拟目录
  （`/a.zip/docs/x.md`），包内 Markdown、HTML、源码、图片与下载复用现有管线；
  解压到进程私有临时缓存，支持整包与条目下载。嵌套包不递归；`--safe` 下不可见。
- `--verbose` 请求日志：方法、路径、`Sec-Fetch-Dest`、状态、`Content-Type/Length` 与耗时；启动时打印内嵌资产尺寸；`?open=` 一次性令牌脱敏。
- 目录行在触屏设备上常显下载/源码动作（`@media (hover: none)`）。

### 修复

- 构建时拒绝空的 `app.js` / `app.css`，启动时对空内嵌资产输出 warning；
  避免离线自编译产物静默丢样式。
- `--max-preview` 不再误伤预览内的 CSS/JS/图片子资源；直接打开文档仍按上限下载。
- 目录行改为图标/名称/大小/时间/操作五列固定布局；HTML 的源码入口不再把大小与
  修改时间列挤左，≤720px 隐藏大小/时间。下载入口改为图标 + 悬浮提示，与源码图标一致；操作点击区 36×36、间距 8，避免误触。
- `/_nav` 遇到读不了的目录/条目时跳过并标记 `partial`，不再让 `/lost+found`
  这类权限目录导致整树 500；导航浮岛显示“部分目录无法读取，内容未显示”。

### 文档

- ADR 0015（HTML 文件预览与沙箱）、ADR 0016（压缩包虚拟路径与解压缓存）。
- `AGENT.md` 更名为标准 `AGENTS.md`，补“Issue → 分支 → PR → 合并 → tag/Release”
  协作流程。

## 2.0.0（2026-10-20）

Rust 重写。旧 Python 单文件实现已删除，历史台账见
[`docs/archive/selftest-python.md`](docs/archive/selftest-python.md)。

### 新增

- 单文件原生二进制（macOS arm64 / Linux x86_64+arm64 musl / Windows x86_64 static CRT）；
  内嵌 VS Code `markdown.css`、`highlight.css`、highlight.js 11.11.1 与岛屿前端。
- 源码构建引入 `web/`（TypeScript + esbuild + Preact）与 Node 22；运行时仍不需要
  Node。CI 的 musl 构建使用 `MDVIEW_WEB_PREBUILT` 复用 host 产物。
- Markdown 语义与代码高亮对齐 VS Code 1.142.0；页面外壳改为文档站风格；
  P0 差分 98.07%（1015/1035），25 条 accepted deviations 有记录。
- Trust 模型：目录级信任、未信任 `.md` 的一次性令牌拦截面、用户配置持久化。
- 4 档 CSP：nonce-only `script-src`、`frame/base/object 'none'`、
  `form-action 'self'`（仅搜索表单）、nosniff。
- 非 Markdown 文本统一源码查看页（文件名为标题、类型/大小/行数/时间标签、行号、
  行锚点、客户端高亮）。
- `data:image/*;…` 在链接与图片位置放行（VS Code 1.142 行为）；拒绝 `vscode:` 链接。
- 岛屿前端：TypeScript + esbuild 单入口，Preact 用于 TOC/代码工具条/图片放大/全站导航；
  `body[data-islands]` 控制 9 个岛，外壳立即水合、重岛空闲/可见时启动。
- 内容主导的全宽外壳：内容面最大 1240px、阅读行最大 1000px；页头横跨内容面
  （左右 30px），搜索页表单在页头右侧；≥1360px 为正文 + 24px TOC 细轨，
  901–1359px 与 ≤900px 都为单列；搜索改成顶栏图标 + 弹层，路径移入正文头部。
- 全站导航浮岛：默认收起、页面空闲时预取 `/_nav`，包含所有可见目录与文件；
  目录行只展开、文件行导航，当前路径展开、用户展开状态记忆；桌面浮岛不挤压正文，
  ≤900px 为抽屉 + 遮罩。目录页改为无分组的统一列表。
- 搜索覆盖 Markdown/文本正文与所有文件名，结果按文件分组；每条结果整行可点击，
  Markdown 内容行跳到渲染页对应块并高亮，文件标题与文件条目跳到文件开头；
  不再有独立的“打开文档/源码 Ln”按钮。
- 页内目录（运行时 h2/h3、细轨 + 悬停文字大纲 + 固定 + scroll-spy）、代码块语言条、
  目录统一列表、源码页“预览”回链。
- 渲染页输出 `data-sourcepos`，由 `linetarget` 岛把搜索 `#L<n>` 映射到包含该行的
  最小渲染块；块级近似，无 JS 时仍打开文档但不滚动。
- 文件大小统一按 1024 进制显示 KB/MB/GB，1 位小数去尾零；0 字节为 `0 KB`，
  1–1023 字节为 `<1 KB`。
- 主题三态改为当前页面内存状态：localStorage 写入失败仍能继续切换；每次点击在
  按钮旁短暂显示“跟随系统/浅色/深色”。
- 前端文案去技术化：搜索结果统一用“条结果”，文件标题整行可点击；目录统计用
  “个项目”，错误页、Trust 拦截面、源码大文件提示与代码块提示改为用户语言。
- 文档按用途重组为 `architecture/`、`guides/`、`reference/`、`testing/`、
  `research/`、`archive/`；新增功能矩阵 `docs/reference/features.md`、浏览器验收
  报告与 agent 自主测试指南；`tests/run-all.sh` 和文档链接检查加入本地验收。
- 大文本源码页全文分块：>256 KB 仍输出全文，按 500 行分块并用
  `content-visibility: auto` 跳过离屏绘制；1 MB 文本从约 42 s 降到约 0.08 s，
  10 MB 约 0.11 s（本机基准）。行锚点与高亮由 JS 按可见块懒加载。
- 关闭 highlight.js 自动语言探测，仅对明确 `language-*` 的代码块高亮；
  大源码的每个可见块单独高亮，单块上限 256 KB。
- 资产 URL 内容哈希（`?v=<FNV-1a>`）+ `immutable` 缓存。

### 变更（与 1.x 不兼容）

- 裸 HTML **原样透传**，安全性由 Trust + CSP 承担（旧版一律转义）。
- 不生成标题 `id`；任务列表按字面量显示；`~~x~~` 输出 `<s>` 而非 `<del>`。
- linkify / reference definition / front matter / URL 与 alt 采用 comrak 行为：
  `www.` 与裸邮箱会链接化，全角句号进 URL，front matter 被消费。
- 相对路径解码两次：文件名里字面含 `%xx` 的文件不能通过相对 Markdown 目标到达。
- 非 Markdown 文本不再直接以 `text/plain` 发送，而是源码查看页。
- 删除 Python 实现、`dist/`、`tools/minify.py` 与 Python 测试。
- 不再支持缩进式代码块之外的旧自定义解析边角（转义装饰、标题锚点等）。

### 测试

- `cargo test`：50 项单元/集成 + 134 项渲染兼容 + 27 条 golden。
- `bash tests/selftest-rust.sh`：151 项黑盒 HTTP 断言；`trust-tty.sh` 9 项；
  `browser-probe.mjs` 163 项；性能预算 4 项；artifact 冒烟 7 项。
- CI：macOS / Linux / Windows 测试矩阵、4 目标构建、`cargo audit`。

### 已知后果

见 [README 已知限制](README.md#已知限制) 与
[ADR 0007](docs/architecture/adr/0007-hard-edge-cases-use-comrak.md)。
