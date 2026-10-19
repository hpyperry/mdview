# 执行计划：Rust 单文件 mdview

**Status**: P0 complete — **Gate A: Yellow**（2026-10-19）；P1/P2 ready
**Branch**: `refactor/new-md-view-server`
**依据**: [设计方案](new-md-view-server.md) · [ADR 0004](../adr/0004-rust-rewrite-and-dependencies.md) ·
[ADR 0005](../adr/0005-vscode-1.142-as-oracle.md) · [ADR 0006](../adr/0006-html-trust-and-csp.md)

这份计划把设计方案落成可执行的工作包。**P0 是决策门**：先量化 comrak 与
markdown-it 的差异，再决定是否全速实现。P0 不通过时，停下来重选解析器，
不要在错误的基础上建服务器。

> **P0 结果（2026-10-19）**：1030 条计分语料 **1012 条精确匹配（98.25%）**，
> **0 条未解释差异**；18 条计分差异全部归入已知自定义层。Gate A = **Yellow**：
> 继续用 comrak，但把 linkify pass 与 reference-definition 预扫描列为 P2 的
> 必做项。详见 [差分报告](../spikes/comrak-vs-markdown-it.md)。

## 0. 原则

1. **先验证最高风险，再写产品代码**：解析器一致性是唯一可能推翻架构的风险。
2. **每个阶段有可验收的产物**：不是“写完了”，而是“测试/报告/二进制能证明”。
3. **旧断言不是规格**：与 VS Code 冲突时按 ADR 0005 改期望，并记录原因。
4. **安全边界单独验收**：Trust/CSP/协议校验/路径夹紧不混在功能测试里“顺带看看”。
5. **单二进制是交付形态**：源码可以分模块，运行时不能依赖外部资产。
6. **代码在 P0 门通过后开始**；P0 的探针是临时代码，不进入发布物。

## 1. 阶段总览

| 阶段 | 目标 | 粗估 | 依赖 |
|---|---|---|---|
| P0 | comrak vs markdown-it 差分探针 + 决策门 | **完成（黄）** | 无 |
| P1 | Rust 骨架、CLI、静态服务、Trust/CSP、测试骨架 | 3–4 天 | 可与 P0 并行 |
| P2 | Markdown 渲染管线 + golden 差分收敛 | **8–12 天** | P0 绿/黄 |
| P3 | VS Code CSS + 完整 highlight.js + 源码查看页 + 前端 | 3–4 天 | P1、P2 |
| P4 | 移植旧测试、重写 selftest、安全/性能/跨平台 | 3–5 天 | P2、P3 |
| P5 | 删除 Python、更新示例与文档、归档旧台账 | 1–2 天 | P4 |
| P6 | 全平台构建、发布 artifact、许可证与烟测 | 1–2 天 | P4、P5 |

**总量级**：单人全职约 **5–7 周**（含测试；P0 后上调）。最大变量是 P2 的 linkify
与 reference-definition 自定义层；P0 的红色结果会让估算重新开始。P1 可以在
P2 之前先落骨架，P3 的资产准备可以在 P2 期间做。

## 2. P0：解析器差分探针（决策门）

**目标**：回答“comrak + 自定义渲染器能否达到严格 VS Code 语义”，而不是凭感觉。
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
      1012/1030 精确匹配，0 未解释差异，Gate A = 黄。

### 决策门

| 结果 | 条件 | 动作 |
|---|---|---|
| 绿 | 差异只剩已知自定义层/序列化噪声 | 继续 P1/P2 |
| **黄（本次）** | 有解析差异，但可在渲染器或薄后处理修 | 带差异清单进 P2，golden 钉住 |
| 红 | 核心解析/HTML block/列表紧凑度大面积不一致 | 停；重新评估 markdown-it-rs、pulldown-cmark、内嵌 markdown-it；更新 ADR 0005 |

**验收**：报告已明确回答“剩余差异是否可修”；P0 代码保留在 `tools/spike/` 以便复现。

## 3. P1：Rust 骨架与静态服务器

**目标**：一个能起服务、能浏览/下载/信任配置的二进制；Markdown 渲染暂用源码页占位。
**可与 P0 并行。**

### 工作包

- [ ] **P1-1 工程骨架**：Cargo 项目、模块边界（server/render/assets/trust）、
      `cargo fmt`/`clippy`、`Cargo.lock` 入库。
- [ ] **P1-2 CLI**：`--host`、`--port`、`--port-tries`、`--root`、`--safe`、
      `--max-preview`、`--no-search`、`--trust`、`--untrusted`、`--security-level`、
      `--version`；启动横幅（真实地址、根绝对路径、信任状态、级别警告）；
      端口回退；Ctrl-C 干净退出。
- [ ] **P1-3 路径与安全**：HTTP 路径解一次百分号；`..` 夹紧；根规范化；
      symlink 策略；301/404/403；`X-Content-Type-Options: nosniff`。
- [ ] **P1-4 类型判定**：白名单 → MIME 表 → 前 512 字节 NUL 嗅探；文本/二进制；
      `--safe` 只放行 `.md` + 图片。
- [ ] **P1-5 静态服务**：目录索引（面包屑、大小、mtime、下载按钮）、二进制原样发送、
      `?download=1`（RFC 6266/5987）、`HEAD`、缓存头、流式大文件。
- [ ] **P1-6 Trust/CSP**：用户配置目录、TOML、启动询问、非 TTY 默认未信任、
      `--trust/--untrusted`、一次性令牌、拦截面、4 档 CSP、nonce。
- [ ] **P1-7 测试骨架**：Rust 集成测试 + `tests/selftest.sh` 壳；CI 骨架。

### 验收

- `cargo test` 与基础 `tests/selftest.sh` 全绿。
- 路径穿越、`--safe`、下载文件名、301、HEAD、端口回退有断言。
- Trust 配置可读写；非交互默认未信任；一次性令牌不可复用。
- `.md` 此时可以临时走源码页，不阻塞服务器验收。

## 4. P2：Markdown 渲染管线

**目标**：严格 VS Code 语义；golden 差分收敛。
**入口**：P0 绿/黄。

### 工作包

- [ ] **P2-1 comrak 配置**：`unsafe` HTML、table/strikethrough；关闭 autolink
      （由自定义 linkify pass 取代）、tasklist/footnote/math；确认不生成 heading id。
- [ ] **P2-2 自定义渲染器**：
  - `validateLink`：拒 `javascript:`/`vbscript:`/`file:`/非法 `data:`；
    `data:image/(gif|png|jpeg|webp);…` 在链接与图片位置都放行；被拒目标按
    markdown-it 的字面/raw tail 回退（生产侧由 CSP 约束）。
  - **linkify pass**：关闭 comrak autolink；复刻 markdown-it/linkify-it 的
    http/https、裸邮箱与边界（`www.` 不链、实体/冒号/引号边界）。
  - **reference-definition 预扫描**：合法尖括号目标归一化；被拒协议的整条定义
    不注册，保留为段落。
  - URL 重写：切 `?`/`#` → 解码两次 → 相对解析 → 编码一次 → 根相对 URL。
  - Front matter：表格 + 值渲染规则（null/数组/对象/日期）。
  - 表格单元格：`style="text-align:…"`（不是 `align=`）。
  - 图像 alt：复刻 markdown-it 的纯文本提取（跳过实体 token）。
  - 代码块：`<pre><code class="language-…">`，不在服务端高亮。
  - 裸 HTML 透传；任务列表/标题 id 不生成；`~~x~~` 输出 `<s>`。
- [ ] **P2-3 Golden 测试**：`tests/golden/` 生成器（Node 22 + 锁定依赖）、语料、
      Rust 对比器；忽略规则写死并注释；golden 入库。**P0 的 26 条已知差异必须逐条有回归夹具。**
- [ ] **P2-4 差异收敛**：逐条修 comrak/markdown-it 边角；每条差异要么修，要么
      归类为“有意忽略”并写原因。
- [ ] **P2-5 渲染缓存**：`(path, mtime_ns, size)` 键；外部编辑自动失效；
      渲染页 `no-store`。
- [ ] **P2-6 单元/性能测试**：URL/协议/linkify/front matter；长行与大输入无平方级退化。

### 验收

- Golden 语料规范化后 100% 匹配；任何剩余差异都被显式分类。
- 旧 217 项渲染断言已审阅/移植，冲突处按 ADR 0005 更新。
- 协议白名单、data URI、双重解码、front matter 均有正反断言。
- **Gate B**：出现新的解析器级差异时，先修或明确记录，不能沉默带过。

## 5. P3：视觉、highlight.js、源码查看页

**目标**：页面看起来像 VS Code；所有文本文件有统一源码查看页；资产全部内嵌。

### 工作包

- [ ] **P3-1 VS Code CSS**：vendored `markdown.css`/`highlight.css`；提取
      Light+/Dark+ `--vscode-*` 变量；`prefers-color-scheme` 自动切换；打印样式。
- [ ] **P3-2 highlight.js**：完整语言集浏览器 bundle；构建脚本 + 版本固定；
      语言别名映射照 VS Code；产物入库；许可证。
- [ ] **P3-3 资产嵌入**：`include_bytes!`/`include_str!`；`/_assets/<hash>/…`；
      `immutable` 缓存；CSP nonce 集成；无外部请求。
- [ ] **P3-4 源码查看页**：服务端行号 gutter + `id="L<n>"`；语言映射；highlight.js；
      无 JS 降级；下载/复制/回顶/面包屑；`--max-preview` 超限下载。
- [ ] **P3-5 `mdview.js`**：highlight 初始化、复制按钮、图片放大 `<dialog>`、
      回到顶部；无 JS 时不出现死按钮；焦点/Esc/修饰键行为沿用旧版约束。
- [ ] **P3-6 Markdown 页 chrome**：面包屑、下载、回顶；内容 `.markdown-body`；
      代码复制按钮按 VS Code 外观。
- [ ] **P3-7 浏览器探针**：亮/暗、高亮、复制、缩放、回顶、无 JS；与 VS Code
      预览并排截图；确认无外部网络请求。

### 验收

- 浏览器探针全绿；CSP 4 档下页面正常；无 `'self'` 脚本放行。
- 源码页行锚点与搜索跳转可用；无 JS 仍可阅读。
- 资产 URL 带哈希且长缓存；单二进制搬到空目录仍能运行。

## 6. P4：测试迁移与安全验收

**目标**：旧能力有对应断言；新安全模型有独立测试。

### 工作包

- [ ] **P4-1 移植 217 项渲染测试**：Rust 单元/集成；按 ADR 0005 更新期望。
- [ ] **P4-2 重写 345 项 HTTP 断言**：`tests/selftest.sh` 跑新二进制；更新
      非 md 源码页、`?raw=1`、`?download=1`、搜索、301/404/HEAD。
- [ ] **P4-3 Trust 测试**：配置读写、非交互默认、`--trust/--untrusted`、
      每次打开拦截面、一次性令牌复用拒绝、raw/download 绕过。
- [ ] **P4-4 CSP 测试**：4 档头逐条断言、nonce 每响应不同、无 `'self'`、
      `X-Content-Type-Options`、level 2 无 CSP。
- [ ] **P4-5 安全测试**：协议白名单、data URI 正反例、路径穿越、symlink、
      `--safe`、下载头注入/文件名编码。
- [ ] **P4-6 性能/跨平台**：大文件、长行、搜索、目录；Windows 路径分隔符、
      Unicode 文件名；CI matrix 跑测试。

### 验收

- `cargo test --locked` + `bash tests/selftest.sh` 在 macOS/Linux/Windows 全绿。
- **Gate C**：旧功能要么有断言，要么在 ADR/README 明确列为移除。
- 安全测试独立成组，失败不能被功能测试掩盖。

## 7. P5：迁移与文档收尾

**目标**：仓库只剩 Rust 实现；文档与测试一致。

### 工作包

- [ ] **P5-1 示例语料**：更新 `docs/`，反映严格 VS Code（task list 字面量、
      无 heading id、全角 URL、`%xx`、data URI 类型）。
- [ ] **P5-2 文档重写**：README、AGENT、tests/README、GLOSSARY 最终一致性；
      加入 Trust/CSP/构建/发布说明。
- [ ] **P5-3 归档旧台账**：旧 `SELFTEST.md` 移到 `docs/legacy/SELFTEST-python.md`；
      新 SELFTEST 从零记录。
- [ ] **P5-4 删除 Python**：`mdview.py`、`dist/`、`tools/minify.py`、
      `__pycache__`、Python 测试；`git grep` 确认无悬空引用。
- [ ] **P5-5 许可证**：`LICENSE`、`THIRD-PARTY-NOTICES`（VS Code CSS、highlight.js、
      Rust crates）。
- [ ] **P5-6 ADR 回填**：实现中产生的偏离/新决策补 ADR；旧 ADR 状态保持准确。

### 验收

- 新读者只读 README/AGENT 就能构建、测试、运行。
- 文档不再声称旧行为（零依赖、转义裸 HTML、只解一次、任务列表）。
- 仓库根只有 Rust 可交付源码与文档。

## 8. P6：全平台构建与发布

**目标**：4 个目标平台的可运行单文件 artifact。

### 工作包

- [ ] **P6-1 Cargo profile**：LTO、`codegen-units=1`、`strip`；测量二进制体积。
- [ ] **P6-2 CI matrix**：`aarch64-apple-darwin`、
      `x86_64-unknown-linux-musl`、`aarch64-unknown-linux-musl`、
      `x86_64-pc-windows-msvc`（`+crt-static`）；`--locked`。
- [ ] **P6-3 打包**：`.tar.gz`/`.zip`，含二进制、README、LICENSE、NOTICES、校验和。
- [ ] **P6-4 依赖审计**：`cargo audit`/`cargo deny`；许可证清单；无禁用依赖。
- [ ] **P6-5 artifact 烟测**：每个平台起服务，请求目录、Markdown、资产、下载、
      CSP 头；确认无运行时外部依赖。
- [ ] **P6-6 发布说明**：版本 2.0.0、已知后果（ADR 0005）、构建/运行方式。

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

- [ ] `cargo fmt --check`、`cargo clippy -- -D warnings`、`cargo test --locked` 全绿。
- [ ] `bash tests/selftest.sh` 在 macOS/Linux/Windows 全绿。
- [ ] Golden 语料 100% 规范化匹配；剩余差异有记录。
- [ ] Trust/CSP/协议/路径安全测试独立通过。
- [ ] 4 个平台 artifact 烟测通过；单文件运行、零外部请求。
- [ ] README/AGENT/GLOSSARY/ADR 与实现一致；旧 Python 代码与测试已删除；
      旧 SELFTEST 已归档。
- [ ] 发布说明列出严格 VS Code 的已知后果（ADR 0005 §后果）。

## 12. 立即开始的第一步

1. 建 `tools/spike/comrak-vs-markdown-it/`（临时 Node + Rust 探针）。
2. 按 P0-1 收语料，P0-2/P0-3 跑两阶段对比。
3. 写 `docs/spikes/comrak-vs-markdown-it.md`，给出绿/黄/红结论。
4. 同时起 P1-1/P1-2（Cargo 骨架 + CLI），不与 P0 抢同一批文件。

**在 P0 报告出来之前，不写产品渲染器，也不删旧 Python。**
