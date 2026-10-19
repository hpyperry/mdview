# P0 差分报告：comrak 0.56 vs markdown-it 14.3.2

**Status**: P0 complete — **Gate A: Yellow（继续用 comrak）**
**Date**: 2026-10-19
**Branch**: `refactor/new-md-view-server`
**Harness**: [`tools/spike/comrak-vs-markdown-it/`](../../tools/spike/comrak-vs-markdown-it/)

## TL;DR

- 1030 条计分语料中 **1012 条精确匹配（98.25%）**，**0 条未解释差异**。
- 18 条是已归类的自定义层差异；另有 10 条 front matter 策略语料单独统计（2 匹配 / 8 预期差异）。
- comrak 的 CommonMark/GFM 核心没有问题；**不需要换解析器**。
- Gate A 判为 **Yellow**：核心解析可用，但 comrak 的 autolink 与 reference definition 行为不能直接当 VS Code 用，需要一层明确的自定义实现。P2 从 5–8 天上调到 **8–12 天**，整体从 4–6 周调整为 **5–7 周**。

## 方法与环境

| 项 | 值 |
|---|---|
| VS Code 基准 | 1.142.0（本机） |
| Oracle | Node 22.22.3 + `markdown-it@14.3.2` + `js-yaml@4.1.0` |
| Oracle 选项 | `html:true`、`linkify:true`、`fuzzyLink:false`、`typographer:false`、`breaks:false`、`langPrefix:"language-"` |
| Oracle front matter | 复刻 VS Code 的 `markdown-it-front-matter` 表格（`table.frontmatter`；数组/对象/日期/null/解析错误） |
| Probe | Rust 1.96 + comrak 0.56（table/strikethrough/autolink 开；tasklist/footnote/math 关；`render.unsafe = true`） |
| Probe 自定义 | `validateLink` + sourcepos 字面回退；`<s>` 删除线；拒绝目标的 raw tail |
| 规范化 | parse5 解析；忽略属性顺序、`data-line`/`data-vscode-context`、块间纯空白；保留 `pre/code` 内空白 |
| URL 重写 | 两边都不做；URL 重写是 P2 的独立层，不参与本报告的解析分 |

Oracle 是“VS Code 同款 markdown-it + 同款 front matter 规则”的复现，不是直接驱动 VS Code webview。
原始 HTML 只在字符串/DOM 层比较，没有进浏览器。

## 语料

| 来源 | 数量 | 说明 |
|---|---:|---|
| CommonMark spec 0.31.2 | 652 | 从 `spec.commonmark.org` 拉取并缓存 |
| 旧测试实际输入 | 268 semantic + 8 stress + 8 internal | 217 项旧测试在仓库根运行通过；monkeypatch `render_markdown` 记录 |
| curated | 101 semantic + 10 front_matter | 手工边角（协议/data URI/路径/表格/列表/引用/HTML…） |
| docs 真实文档 | 6 | `index.md`、`guide/*`、`preview/index.md`、`preview/binary-test.md` |
| selftest 内联夹具 | 3 | `bare.md` + B10 两个路径夹具 |

**计分语料 = 1030**：652 spec + 268 旧测试 + 101 curated + 6 docs + 3 selftest。
stress/internal 共 16 条不计分；front_matter 策略 10 条单独统计。

## 结果

### 总表

| 指标 | 数量 |
|---|---:|
| 计分语料 | 1030 |
| 精确匹配 | **1012（98.25%）** |
| 已归类自定义层差异 | 18 |
| 未解释差异 | **0** |
| front matter 策略：匹配 / 预期差异 | 2 / 8 |

### 按来源

| 来源 | 总数 | 匹配 | 预期差异 | 未解释 |
|---|---:|---:|---:|---:|
| CommonMark spec | 652 | 650 | 2 | 0 |
| curated | 111 | 99 | 12 | 0 |
| docs | 6 | 5 | 1 | 0 |
| 旧测试 | 268 | 257 | 11 | 0 |
| selftest | 3 | 3 | 0 | 0 |

CommonMark spec 的两个“预期差异”是 spec 96/98：输入以 `---` 开头，VS Code 的 front matter
插件会把它们当成 front matter；comrak 没有这层插件。这不是 comrak 的 CommonMark 解析错误。

### 已归类差异（26 条，含 front matter 策略的 8 条）

| 类别 | 数量 | 说明 |
|---|---:|---|
| `front_matter_expected` | 10 | VS Code 把文档开头的 `---` 块渲染成表格；comrak 按 hr/Setext 解析 |
| `linkify_boundary_gap` | 6 | comrak autolink 与 markdown-it/linkify-it 的边界不同 |
| `protocol_reference_definition_expected` | 4 | markdown-it 把被拒协议的引用定义留成段落；comrak 移除了定义 |
| `table_alignment_expected` | 3 | markdown-it 用 `style="text-align:left"`；comrak 用 `align="left"` |
| `reference_angle_definition_gap` | 2 | `[r]: <a b.md>` 这种尖括号引用定义 comrak 解析不了 |
| `image_alt_text_gap` | 1 | markdown-it 在 alt 里跳过实体 token（`a&amp;b` → `ab`）；comrak 输出 `a&b` |

## 关键发现

### 1. 核心解析已经足够接近

已逐条验证匹配（或在本报告的探针修正后匹配）的关键行为：

- CJK 强调：`中文*强调*中文` → `<em>`；
- 词内强调：`2*3*4` → `2<em>3</em>4`；
- Setext：`文字\n---` → `<h2>`；
- 全角 URL：`https://e.com/a。结束` 整个进 URL；
- 任务列表：字面 `[x]`，无 checkbox；
- 标题：不自动生成 `id`；
- `data:image/(gif|png|jpeg|webp);…` 在链接与图片位置都放行；svg/bmp/avif 拒绝；
- 行内拒绝目标：`[**x**](javascript:…)` → `[<strong>x</strong>](javascript:…)`；
- raw HTML 透传；表格/列表/围栏/引用/实体与 CommonMark spec 基本一致；
- 268 条旧测试输入里，257 条精确匹配，其余全部落在上表的已知层。

### 2. comrak autolink 不能直接当 VS Code 用

6 条差异全部来自 autolink：

- `www.example.com`：comrak 会链成 `http://www.example.com`；markdown-it 在
  `fuzzyLink:false` 下**不链**。
- `https://e.com/a&copy;`：markdown-it 的 href/文本是 `https://e.com/a&copy`；
  comrak 停在 `&` 并把 `copy;` 当实体。
- `https://example.com/a:`：markdown-it 把尾部 `:` 算进 URL；comrak 停在 `:` 前。
- 两个病态邮箱边界（`<a"href="javascript:1@b.co>` / `<x"onerror="1@a.com>`）：
  两者都没有注入属性，但 `mailto:` 的文本范围不同；这是 linkify 邮箱边界的差异。

**结论**：生产实现应关闭 comrak 的 `extension.autolink`，用独立的 linkify pass
复刻 markdown-it/linkify-it 的边界；旧 Python 的裸 URL 扫描器可作为参考，但要按
VS Code 的“全角标点属于 URL、裸邮箱可链”重新校准。

### 3. 引用定义需要预扫描

两类问题都来自“markdown-it 在解析期就做协议/目标校验，comrak 不做”：

- **被拒协议**：`[r]: javascript:alert(1)` / `[r]: data:text/html,x` 在 markdown-it 里
  不是合法引用定义，定义行会作为段落留在输出里；comrak 会解析并移除它。
- **尖括号目标**：`[r]: <a b.md>` 在 markdown-it 里是合法定义（目标 `a b.md`）；
  comrak 解析失败，把定义行留成段落。

**结论**：在 comrak 之前做一次 reference-definition 预扫描：
合法尖括号目标归一化（例如编成 `%20` 或改写成 comrak 可解析的形式）；
被拒协议的整条定义**不注册**，让它按段落输出。两项都要有 golden 反例。

### 4. 图表对齐是渲染属性差异，不是解析差异

markdown-it 输出：

```html
<th style="text-align:left">…</th>
```

comrak 输出：

```html
<th align="left">…</th>
```

视觉上通常一样，但 HTML 不一致。生产自定义表格渲染器应输出 `style="text-align:…"`；
这是 0.5 天级修复。

### 5. 图像 alt 的 markdown-it 怪癖

`![a&amp;b](p.png)`：

- markdown-it：`alt="ab"`（`renderInlineAsText` 跳过实体 token）；
- comrak：`alt="a&b"`（实体已解码）。

严格 VS Code 需要复刻这个“跳过实体 token”的 alt 纯文本提取；1 条语料，0.5 天级修复。

### 6. 已经验证可行的探针修正

- `<s>`：comrak 默认 `~~x~~` 输出 `<del>`；VS Code/markdown-it 是 `<s>`。探针已改为 `<s>`。
- 拒绝目标的 raw tail：markdown-it 在 `html:true` 下会把被拒目标里的 `<script>` 当裸 HTML
  保留；探针已按 raw tail 输出。生产侧由 Trust/CSP 约束，不在解析器里 escape。
- sourcepos 回退：comrak 的 `end.column` 是 1-based 最后一字节位置，用作 0-based 排他末尾；
  行内标签的回退可以保留标签里的强调/行内码。

## 性能

`syntect` 关闭、release 构建；comrak 计时含 parse + format，markdown-it 计时只含 render。
`elapsed_ms` 取自单条输入，不是完整进程时间。

| 用例 | 输入 | markdown-it | comrak | 比值（md-it/comrak） |
|---|---:|---:|---:|---:|
| plain-1mb | 1024 KiB | 149.9 ms | 36.9 ms | 4.07× |
| plain-10mb | 10240 KiB | 1315.1 ms | 299.8 ms | 4.39× |
| url-dense-1mb | 1024 KiB | 245.9 ms | 21.6 ms | 11.39× |
| fences-1mb | 1024 KiB | 98.1 ms | 24.5 ms | 4.00× |
| brackets-256k | 256 KiB | 434.3 ms | 9.8 ms | 44.24× |
| stars-256k | 256 KiB | 6.4 ms | 0.5 ms | 12.93× |

10 MB + 6 个 perf 用例的完整探针进程 `real 1.21s`。comrak 在 256 KB 长行上 9.8 ms，
没有观察到旧 Python 实现那种平方级退化；生产加 linkify pass 后需要重新测这一项。

## Gate A 结论

**Yellow — 继续使用 comrak，不换解析器。**

- 通过：核心 CommonMark/GFM、CJK/词内强调、Setext、全角 URL、data URI、raw HTML、
  表格/列表/围栏/引用；0 未解释差异。
- 不通过为 Green 的原因：autolink 与 reference definition 是**解析级**差异，
  不能靠改一个属性解决；需要 linkify pass 与 reference 预扫描。
- 不通过为 Red 的原因：差异有明确边界和修复路径，不需要 fork comrak 或重写解析器。

### 必须补的自定义层（按顺序）

| 顺序 | 工作 | 粗估 | 验收 |
|---|---|---|---:|
| 1 | 关闭 comrak autolink；实现 linkify pass（http/https + 裸邮箱 + 边界规则） | 2–3 天 | 6 条 autolink 语料全匹配；新增边界 golden |
| 2 | reference-definition 预扫描（尖括号归一化 + 被拒协议不注册） | 1–1.5 天 | 6 条引用差异全匹配 |
| 3 | front matter 预扫描 + YAML 表格 | 0.5–1 天 | 10 条 front matter 语料 |
| 4 | 表格单元格 `style="text-align:…"` 自定义渲染 | 0.5 天 | 3 条表格语料 |
| 5 | 图像 alt 纯文本提取（跳过实体 token） | 0.5 天 | `![a&amp;b]` 用例 |
| 6 | `<s>` 删除线、拒绝目标 raw tail、sourcepos 回退（探针已验证） | 已验 | 纳入生产自定义渲染器 |

**P2 工作量由 5–8 天上调到 8–12 天**；整体执行计划由 4–6 周调整为 **5–7 周**。
如果 linkify pass 超过 3 天仍无法覆盖边界，再回来评估 markdown-it-rs / 内嵌 markdown-it；
目前没有触发这个条件。

## 复现

```bash
cd tools/spike/comrak-vs-markdown-it
./run.sh                 # extract -> oracle -> comrak -> compare
node perf.mjs            # 生成 perf 语料并测 markdown-it
./target/release/comrak-probe results/perf-corpus.jsonl results/perf-comrak.jsonl
```

生成物在 `corpus/corpus.jsonl` 与 `results/`，均不入库；`corpus/curated.json`、
探针源码、锁文件与报告入库。

## 局限

- Oracle 是 VS Code 同款 markdown-it 的复现，不是直接驱动 VS Code webview；
  front matter 表格按 VS Code 的默认 `table` 模式复刻。
- GFM spec 未单独拉取；GFM 覆盖来自旧测试与 curated。CommonMark spec 652 条已全量跑。
- `docs/preview/large/big.md`（21 MiB 全 NUL）未进解析语料。
- 探针不实现 front matter/表格样式/alt 提取/linkify 自定义层；这些是本报告归类的
  “预期差异”，不是 comrak 核心解析错误。
- 拒绝目标的 raw tail 是 markdown-it `html:true` 的真实行为；生产安全依赖
  [ADR 0006](../../docs/adr/0006-html-trust-and-csp.md) 的 Trust/CSP，不依赖解析器转义。
