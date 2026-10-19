# 执行计划：Rust 单文件 mdview

**Status**: P0–P5 完成；P6 基本完成（CI 全绿，release tag 待验证）
**Branch**: `refactor/new-md-view-server`
**依据**: [设计方案](new-md-view-server.md) · [ADR 0004](../adr/0004-rust-rewrite-and-dependencies.md) ·
[ADR 0005](../adr/0005-vscode-1.142-as-oracle.md) · [ADR 0006](../adr/0006-html-trust-and-csp.md) ·
[ADR 0007](../adr/0007-hard-edge-cases-use-comrak.md)

这份计划把设计方案落成可执行的工作包。**P0 是决策门**：先量化 comrak 与
markdown-it 的差异，再决定是否全速实现。P0 不通过时，停下来重选解析器，
不要在错误的基础上建服务器。

> **P0 结果（2026-10-19）**：1035 条计分语料 **1015 条精确匹配（98.07%）**，
> **0 条未解释差异**；20 条计分差异 = 17 条 accepted + 3 条表格对齐待修。
> 按 [ADR 0007](../adr/0007-hard-edge-cases-use-comrak.md)，linkify、reference
> definition、front matter、URL normalization、图像 alt 的 23 条差异接受 comrak
> 行为；另有 2 条 `vscode:` 链接服务器偏差 accepted。P2 由 8–12 天下调到
> **4–6 天**。详见 [差分报告](../spikes/comrak-vs-markdown-it.md)。

## 0. 原则

1. **先验证最高风险，再写产品代码**：解析器一致性是唯一可能推翻架构的风险。
2. **每个阶段有可验收的产物**：不是“写完了”，而是“测试/报告/二进制能证明”。
3. **旧断言不是规格**：与 VS Code 冲突时按 ADR 0005/0007 改期望，并记录原因。
4. **安全边界单独验收**：Trust/CSP/协议校验/路径夹紧不混在功能测试里“顺带看看”。
5. **单二进制是交付形态**：源码可以分模块，运行时不能依赖外部资产。
6. **代码在 P0 门通过后开始**；P0 的探针是临时代码，不进入发布物。

## 1. 阶段总览

| 阶段 | 目标 | 粗估 | 依赖 |
|---|---|---|---|
| P0 | comrak vs markdown-it 差分探针 + 决策门 | **完成（黄）** | 无 |
| P1 | Rust 骨架、CLI、静态服务、Trust/CSP、测试骨架 | 3–4 天 | 可与 P0 并行 |
| P2 | Markdown 渲染管线 + golden 差分收敛 | **4–6 天** | P0 绿/黄 |
| P3 | VS Code CSS + 完整 highlight.js + 源码查看页 + 前端 | 3–4 天 | P1、P2 |
| P4 | 移植旧测试、重写 selftest、安全/性能/跨平台 | 3–5 天 | P2、P3 |
| P5 | 删除 Python、更新示例与文档、归档旧台账 | 1–2 天 | P4 |
| P6 | 全平台构建、发布 artifact、许可证与烟测 | 1–2 天 | P4、P5 |

**总量级**：单人全职约 **4–5 周**（含测试；按 ADR 0007 第二次下调）。最大变量仍是
P2 的 URL/安全/表格对齐层；P1 可以先落骨架，P3 的资产准备可以在 P2 期间做。

> **实现状态（2026-10-19）**：P1–P5 已完成；`cargo test` 45 + 134 + 27 golden、黑盒 110、pty 9、
> 浏览器 58、artifact 冒烟 7，clippy/fmt 全绿，release 约 3.3 MB。P6 的 CI 矩阵、打包与依赖审计已实跑通过；
> 许可证 MIT，release tag 工作流待验证。

## 2. P0：解析器差分探针（决策门）

**目标**：回答“comrak + 自定义渲染器能否达到 VS Code 核心语义，哪些硬边角要放弃”，
而不是凭感觉。
**时间盒**：0.5–1 天（已完成）。**不写产品代码。**

### 工作包

- [x] **P0-1 语料**：旧 `docs/`、旧测试实际输入、CommonMark spec、VS Code 特有边角
      （CJK 强调、`2*3*4`、全角 URL、Setext、task list、heading id、front matter、
      data URI、raw HTML、`%xx` 路径）。
- [x] **P0-2 Oracle**：Node 22 + `markdown-it@14.3.2` + `js-yaml`；
      选项 `html:true`、`linkify:true`、`fuzzyLink:false`、`typographer:false`、
      `breaks:false`；front matter 按 VS Code 表格规则。
- [x] **P0-3 comrak 探针**：comrak 0.56，开启 table/strikethrough，关闭
      tasklist/math/footnote，`unsafe` 透传 HTML；自定义 `validateLink` + sourcepos
      回退；autolink 的差异单独分类。
- [x] **P0-4 规范化 diff**：DOM 规范化；保留 `pre/code` 内空白；忽略 VS Code 私有
      `data-line`/`code-line`/`data-vscode-context` 与纯序列化差异。
- [x] **P0-5 性能检查**：1 MB/10 MB、URL 密集、256 KB 长行；未发现平方级退化。
- [x] **P0-6 报告**：[`docs/spikes/comrak-vs-markdown-it.md`](../spikes/comrak-vs-markdown-it.md)；
      1015/1035 精确匹配，0 未解释差异，Gate A = 黄。

### 决策门

| 结果 | 条件 | 动作 |
|---|---|---|
| 绿 | 差异只剩已知自定义层/序列化噪声 | 继续 P1/P2 |
| **黄（本次）** | 有解析差异，但可在渲染器或薄后处理修 | 带差异清单进 P2，golden 钉住 |
| 红 | 核心解析/HTML block/列表紧凑度大面积不一致 | 停；重新评估 markdown-it-rs、pulldown-cmark、内嵌 markdown-it；更新 ADR 0005/0007 |

**验收**：报告已明确回答“剩余差异是否可修”；P0 代码保留在 `tools/spike/` 以便复现。

## 3. P1：Rust 骨架与静态服务器

**目标**：一个能起服务、能浏览/下载/信任配置的二进制；Markdown 渲染暂用源码页占位。
**可与 P0 并行。**

### 工作包

- [x] **P1-1 工程骨架**：Cargo 项目、模块边界（server/render/assets/trust）、
      `cargo fmt`/`clippy`、`Cargo.lock` 入库。
- [x] **P1-2 CLI**：`--host`、`--port`、`--port-tries`、`--root`、`--safe`、
      `--max-preview`、`--no-search`、`--trust`、`--untrusted`、`--security-level`、
      `--version`；启动横幅、端口回退、Ctrl-C。
- [x] **P1-3 路径与安全**：HTTP 路径解一次百分号；`..` 夹紧；根规范化；
      symlink 越界拒绝；301/404/403；`X-Content-Type-Options: nosniff`。
- [x] **P1-4 类型判定**：白名单 → MIME 表 → 前 512 字节 NUL 嗅探；文本/二进制；
      `--safe` 只放行 `.md` + 图片。*（常用白名单已落；P4 按旧清单补齐。）*
- [x] **P1-5 静态服务**：目录索引（面包屑、大小、mtime、下载按钮、搜索框）、
      二进制原样发送、`?download=1`（RFC 6266/5987）、`HEAD`、缓存头、流式文件、
      `/search?q=` 全文搜索。
- [x] **P1-7 测试骨架**：Rust 单元/集成 + `tests/selftest-rust.sh`（后续扩到 110 项）
      black-box；CI 骨架留到 P6。
- [x] **P1-6 Trust/CSP**：用户配置目录、TOML、启动询问、非 TTY 默认未信任、
      `--trust/--untrusted`、4 档 CSP、nonce；未信任 `.md` 拦截面与一次性令牌
      已有 Rust + black-box 测试。

### 验收

- `cargo test` 28 项全绿；真实二进制冒烟通过（渲染/源码页/下载/搜索/301/HEAD/CSP）。
- 路径穿越、`--safe`、下载文件名、301、HEAD、端口回退有断言。
- Trust 配置可读写；非交互默认未信任；一次性令牌复用拒绝已测。
- `.md` 正常 URL 已走 Markdown 渲染；`?raw=1` 仍是源码页。

## 4. P2：Markdown 渲染管线

**目标**：VS Code 核心语义 + comrak 硬边角（ADR 0007）；golden 差分收敛。
**入口**：P0 绿/黄。

### 工作包

- [x] **P2-1 comrak 配置**：`unsafe` HTML、table/strikethrough/autolink、
      `front_matter_delimiter = Some("---")`；关闭 tasklist/footnote/math；
      确认不生成 heading id。
- [x] **P2-2 自定义渲染器（只保留安全/服务端语义层）**：
  - `validateLink`：拒 `javascript:`/`vbscript:`/`file:`/非法 `data:`；
    **任意 `data:image/*;…` 在链接与图片位置都放行**（VS Code 1.142 实际覆盖逻辑）；
    `vscode:`/`vscode-insiders:` 拒绝（服务器偏差）。这是安全例外，
    不交给 comrak `render.unsafe`。
  - 被拒目标：简化为渲染标签文本、不生成锚点/图片；不做 markdown-it 的
    sourcepos/raw-tail 回退。绝不产出危险 `href`/`src`。
  - URL 重写：切 `?`/`#` → 解码两次 → 相对解析 → 编码一次 → 根相对 URL。
  - 表格单元格：`style="text-align:…"`（不是 `align=`）。
  - 代码块：`<pre><code class="language-…">`，不在服务端高亮；
    `~~x~~` 输出 `<s>`。
  - 裸 HTML 透传；任务列表/标题 id 不生成。
- [x] **P2-3 Golden 测试**：`tests/golden/cases.jsonl` 27 条 curated 输入 +
      `expected/*.html` 逐字节输出；`cargo run --example golden -- --update`
      重新生成。`render::tests::golden_outputs_are_frozen` 保留 14 条内部输出。
      P0 的完整差分语料仍在 `tools/spike/`（markdown-it oracle）。
      **P0 的 28 条：25 条 accepted（23 comrak + 2 vscode），3 条表格对齐按 VS Code 修。**
- [x] **P2-4 差异收敛**：P0 的 accepted deviations 已按 ADR 0007 固定，
      由 `render_compat` 正反断言 + `golden` 的 `note` 字段覆盖。
- [x] **P2-5 渲染缓存**：`(path, mtime, size)` 键；外部编辑自动失效；
      渲染页 `no-store`；缓存上限 128 条。
- [x] **P2-6 单元/性能测试**：URL/协议/表格对齐/URL 重写/1 MB 大输入
      （5 秒上限）已有覆盖；45 项单元测试 + 134 项渲染集成测试全绿。

### 验收

- Golden 语料：3 条表格对齐 + 安全/URL 断言通过；25 条 accepted 差异有固定夹具。
- 旧 217 项渲染断言已审阅/移植，冲突处按 ADR 0005/0007 更新。
- 协议白名单、data URI、双重解码、表格对齐均有正反断言。
- **Gate B**：出现新的解析器级差异时，先修或明确记录，不能沉默带过。

## 5. P3：视觉、highlight.js、源码查看页

**目标**：页面看起来像 VS Code；所有文本文件有统一源码查看页；资产全部内嵌。

### 工作包

- [x] **P3-1 VS Code CSS**：`markdown.css` / `highlight.css` 已 vendored；
      `--vscode-*` 变量映射到明暗变量；正文排版由 VS Code CSS 接管；
      `prefers-color-scheme` 由 `mdview.js` 切换。
- [x] **P3-2 highlight.js**：完整语言集浏览器 bundle（1.0 MB）；构建脚本
      `tools/build-assets/`；语言映射常用项已接；产物入库。
- [x] **P3-3 资产嵌入**：`include_bytes!`/`include_str!`；`/_assets/…?v=<内容哈希>`
      + `immutable` 缓存；CSP nonce 集成；无外部请求。
- [x] **P3-4 源码查看页**：服务端行号 gutter + `id="L<n>"`；语言映射；highlight.js；
      无 JS 降级为纯文本；下载/复制/回顶/面包屑；`--max-preview` 超限下载。
- [x] **P3-5 `mdview.js`**：highlight 初始化、复制按钮、图片放大 `<dialog>`、
      回到顶部；无 JS 时不出现死按钮；修饰键不劫持、Esc/背景关闭、焦点归还。
- [x] **P3-6 文档站 chrome**：顶部栏、可折叠 sticky 侧栏、面包屑、主题三态；
      Markdown 页 ≥1360px 为 240/780/220 三列，右侧 TOC 支持 scroll-spy 与独立收起；
      代码语言条、分组搜索页与错误/Trust 页统一（ADR 0008/0009/0010）。
- [x] **P3-7 浏览器探针**：`tests/browser-probe.mjs` 在 headless Chrome 里跑
      58 项：三列/sticky/侧栏底部贴底、TOC scroll-spy/开关、搜索提交、语言条、
      高亮、复制、放大/焦点、修饰键、主题三态、移动抽屉、目录/源码回顶、
      无 JS 基线、无外部请求。

### 验收

- 已做：VS Code `markdown.css`/`highlight.css` vendored 并截图确认；
  亮/暗、代码块 highlight、源码页行号与语言高亮、CSP nonce 加载外部脚本；
  无外部网络请求。
- 待补：复制/缩放交互探针、无 JS 探针。
- 源码页行锚点与搜索跳转已可用；无 JS 仍可阅读。
- 单二进制搬到空目录仍能运行（资产全部嵌入）。

## 6. P4：测试迁移与安全验收

**目标**：旧能力有对应断言；新安全模型有独立测试。

### 工作包

- [x] **P4-1 移植 217 项渲染测试**：`tests/render_compat.rs` 134 项，按
      ADR 0005/0007 更新期望；纯 JS/CSS 旧断言（复制按钮、遮罩动画）属于
      被重写的客户端资产，不再逐条迁移。
- [x] **P4-2 重写 345 项 HTTP 断言**：`tests/selftest-rust.sh` 110 项黑盒 +
      `src/` 45 项单元测试（server 22）覆盖目录/源码/下载/搜索/301/404/HEAD/
      MIME/嗅探/上限/端口回退/Trust/CSP/文件系统边界。旧 Python 特有断言
      （标题 id、任务列表 checkbox、服务端高亮、raw HTML 转义、Python 压缩器）
      按 ADR 0005/0006/0007 明确废弃，不逐条复制。
- [x] **P4-3 Trust 测试**：配置读写、优先级、非交互默认、一次性令牌复用拒绝、
      raw/download 绕过均有断言；`tests/trust-tty.sh` 用 expect 在真实 pty 里
      回答 `y`，验证提示、配置落盘与第二次免询问（9 项）。
- [x] **P4-4 CSP 测试**：4 档头、nonce 每响应不同、无 `'self'`、
      `X-Content-Type-Options`、level 2 无 CSP 均已断言。
- [x] **P4-5 安全测试**：协议白名单、data URI 正反例、路径穿越、symlink
      逃逸/根内放行、`--safe`、下载头注入/文件名编码。
- [x] **P4-6 性能/跨平台**：长行、畸形括号、定界符、链接+裸 URL 混合、
      1 MB 输入已有上界断言；Windows 风格路径/Unicode 文件名测试；CI 三平台
      矩阵（macOS 14 / Ubuntu / Windows）全绿。

### 验收

- `cargo test --locked` + `bash tests/selftest-rust.sh` 在 macOS/Linux/Windows 全绿。
- **Gate C**：旧功能要么有断言，要么在 ADR/README 明确列为移除。
- 安全测试独立成组，失败不能被功能测试掩盖。

## 7. P5：迁移与文档收尾

**目标**：仓库只剩 Rust 实现；文档与测试一致。

### 工作包

- [x] **P5-1 示例语料**：`docs/index.md`、`guide/install.md`、`guide/advanced.md`、
      `guide/code-blocks.md`、`preview/index.md`、`preview/binary-test.md` 已改为
      VS Code 核心 + comrak 硬边角（task list 字面量、无 heading id、全角 URL、
      `%xx`、data URI、accepted deviations）。
- [x] **P5-2 文档重写**：README、AGENT、tests/README、GLOSSARY、SELFTEST 已重写；
      含 Trust/CSP/构建/CI/测试说明。
- [x] **P5-3 归档旧台账**：旧 `SELFTEST.md` → `docs/legacy/SELFTEST-python.md`；
      新 `SELFTEST.md` 记录 Rust 验证结果。
- [x] **P5-4 删除 Python**：`mdview.py`、`dist/`、`tools/minify.py`、Python 测试、
      `__pycache__` 已删除；`docs/preview/make_preview_samples.py` 作为夹具生成器保留。
- [x] **P5-5 许可证**：MIT `LICENSE` 已加入；`THIRD-PARTY-NOTICES` 列内嵌资产与直接依赖。
- [x] **P5-6 ADR 回填**：ADR 0001/0003 加了新实现说明；ADR 0004 验收命令更新；
      ADR 0007 记录 comrak 硬边角。

### 验收

- 新读者只读 README/AGENT 就能构建、测试、运行。
- 文档不再声称旧行为（零依赖、转义裸 HTML、只解一次、任务列表）。
- 仓库根只有 Rust 可交付源码与文档。

## 8. P6：全平台构建与发布

**目标**：4 个目标平台的可运行单文件 artifact。

### 工作包

- [x] **P6-1 Cargo profile**：LTO、`codegen-units=1`、`strip` 已启用；
      release 二进制约 **3.3 MB**（含 1 MB highlight.js bundle）。
- [x] **P6-2 CI matrix**：4 个目标全部构建成功（GitHub Actions run
      39274836191）；`.cargo/config.toml` 打开 Windows static CRT。
- [~] **P6-3 打包**：CI 已产出 4 个 `.tar.gz`/`.zip`（含二进制、README、
      LICENSE、THIRD-PARTY-NOTICES）；`release.yml` 的 SHA256SUMS 与
      GitHub Release 仍需一个 tag 验证。
- [x] **P6-4 依赖审计**：本机 `cargo audit` 无漏洞；`cargo deny check
      advisories licenses bans sources` 全 ok；CI 同样运行两者。
- [x] **P6-5 artifact 烟测**：`tests/smoke-artifact.sh` 在 CI 中对 macOS arm64、
      Linux x86_64 musl、Windows x86_64 产物执行并通过；arm64 musl 只构建。
- [x] **P6-6 发布说明**：`CHANGELOG.md` 记录 2.0.0 功能、破坏性变更、
      已知后果与测试计数。

### 验收

- 4 个 artifact 在目标平台或 CI 中通过烟测。
- 单文件搬到空目录可运行；所有页面零外部请求。
- 发布包不含 Python/Node 运行时。

## 9. 关键路径与并行

```text
P0 ──Gate A──> P2 ──Gate B──> P4 ──Gate C──> P5 ──> P6
       │                       ▲
       └── P1 ────────────────┘
                               │
                    P3 ────────┘
```

- **Track A（解析器）**：P0 → P2。最高风险，优先。
- **Track B（服务器）**：P1；与 P0 并行。
- **Track C（前端资产）**：P3；P2 期间可以先做 CSS 变量、highlight.js bundle、
  源码页模板。
- **Track D（测试/文档）**：P4 → P5；P4 可以提前写安全/Trust 测试骨架。

## 10. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| comrak 与 markdown-it 核心差异大 | 架构返工 | P0 决策门；红色时重选解析器 |
| comrak 边角无限长尾 | 工期失控 | golden 语料固定；每条差异分类；设 Gate B |
| Trust/CSP 漏防 | XSS/脚本执行 | 独立安全测试；script-src 只 nonce；4 档逐条断言 |
| 完整 highlight.js 体积/构建 | 二进制过大/构建复杂 | 固定 bundle 构建脚本；测量体积；必要时压缩/裁剪但需改 ADR |
| Front matter YAML 行为差异 | 渲染不一致 | 用成熟 YAML crate；golden 覆盖 null/数组/对象/日期/错误 |
| 双重解码边角 | 链接 404/可达性 | 专门测试 `%20`/`%2520`/`%23`/`%3F`；与 golden 对齐 |
| Windows 路径/编码 | 跨平台失败 | CI matrix；路径/Unicode 测试；配置目录用 `directories` |
| 性能退化 | 大文件卡死 | 长行/大输入测试；linkify/URL 重写保持线性 |
| 旧测试被盲目保留 | 与 ADR 冲突 | 移植时逐条审阅；冲突按 VS Code 改 |

## 11. 完成定义（DoD）

- [x] `cargo fmt --check`、`cargo clippy -- -D warnings`、`cargo test --locked` 全绿。
- [x] `bash tests/selftest-rust.sh` 在 macOS/Linux/Windows 全绿（CI 矩阵）。
- [ ] Golden 语料 100% 规范化匹配；剩余差异有记录。
- [ ] Trust/CSP/协议/路径安全测试独立通过。
- [ ] 4 个平台 artifact 烟测通过；单文件运行、零外部请求。
- [ ] README/AGENT/GLOSSARY/ADR 与实现一致；旧 Python 代码与测试已删除；
      旧 SELFTEST 已归档。
- [ ] 发布说明列出 ADR 0005/0007 的已知后果（25 条 accepted deviations + 安全边界）。

## 12. 立即开始的第一步

1. 建 `tools/spike/comrak-vs-markdown-it/`（临时 Node + Rust 探针）。
2. 按 P0-1 收语料，P0-2/P0-3 跑两阶段对比。
3. 写 `docs/spikes/comrak-vs-markdown-it.md`，给出绿/黄/红结论。
4. 同时起 P1-1/P1-2（Cargo 骨架 + CLI），不与 P0 抢同一批文件。

**在 P0 报告出来之前，不写产品渲染器，也不删旧 Python。**
