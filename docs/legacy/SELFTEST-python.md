# SELFTEST —— 端到端验证结果（旧 Python 实现，已归档）

> **历史文档**：本文件描述 2.0 之前的 Python 单文件实现，其中的命令、计数与行为
> 不再适用于当前 Rust 实现。保留它仅为追溯缺陷与修复过程；当前测试见
> [`tests/README.md`](../../tests/README.md) 与根目录 `SELFTEST.md`。

本文件记录 `mdview.py` 的实际验证结果，**每条都能照着复现**。
不是"应该可以"，而是这台机器上当时跑出来的输出。

| 项目 | 命令 | 结果 |
|------|------|------|
| 渲染器单元测试 | `python3 tests/tests_render.py` | **217 项全部通过**（`Ran 217 tests ... OK`） |
| 端到端 HTTP 验证 | `bash tests/selftest.sh` | **345 项断言全部通过**（`PASS=345 FAIL=0`） |
| 语法兼容性 | `ast` 扫描 | 无 walrus / `match` / 3.9+ 独有语法 → 3.6+ 可运行 |
| `--safe` | 见下 §3 | 只放行 `.md` 与图片，其余 404 |
| `--no-search` | 见下 §3 | 路由与界面搜索框同时消失 |
| 端口占用 | 见下 §3 | 自动 +1 回退并打印真实 URL |
| 视觉确认 | Chrome headless 截图 | 暗色模式、高亮、表格、任务列表、中文排版正常（截图见 §3.1） |
| 代码块专项 | `docs/guide/code-blocks.md` | 20 种语言 + 全部围栏变体 + 16 条验收清单，自检覆盖每种语言 |

环境：macOS，`Python 3.14.7`（代码按 3.6+ 写，未用新语法）。

---

## 1. 渲染器单元测试

```console
$ python3 tests/tests_render.py
...
----------------------------------------------------------------------
Ran 217 tests in 0.721s

OK
```

覆盖：强调 flanking 规则（含中文/词内/三连/相邻/未配对）、**转义与行内码混排的占位符泄漏**
（回归测试）、裸 HTML 转义、实体、引用式链接、引用嵌套、列表嵌套与松紧、任务列表、
有序 `start`、表格对齐、围栏与高亮、链接与图片重写、路径夹紧、slug、搜索。

---

## 2. 端到端 HTTP 验证（`bash tests/selftest.sh`，198 项）

脚本自己在 `127.0.0.1:8731` 起临时实例，跑完自动关闭。关键断言与实测：

```console
== 目录索引 / ==
  ok   列出 index.md
  ok   列出 guide/ 子目录
  ok   带搜索框
  ok   带返回上级

== Markdown 渲染 /index.md ==
  ok   h1 生成锚点 id                    <h1 id="mdview-示例文档">
  ok   粗体 / 斜体 / 粗斜 *** / 删除线 ~~
  ok   行内代码
  ok   文档间链接                        href="/guide/install.md"
  ok   带锚点链接                        href="/guide/install.md#安装步骤"
  ok   同页锚点                          href="#表格与对齐"
  ok   外链
  ok   表格 thead / 表格对齐属性          style="text-align:center"
  ok   任务列表已勾选 / 未勾选
  ok   嵌套列表 / 引用块
  ok   代码高亮关键字                    <span class="kw">import</span>
  ok   代码高亮字符串                    <span class="str">`hello ${name}`</span>
  ok   代码高亮注释                      <span class="com">
  ok   分隔线 / 引用式链接标题 / HTML 实体
  ok   裸 HTML 被转义                    &lt;script&gt;
  ok   无未转义 script
  ok   样式内联
  ok   无外部样式表请求
  ok   无外部脚本请求

== ?raw=1 原文 ==
  ok   Content-Type 为 text/markdown
  ok   返回原始 Markdown                 # mdview 示例文档
  ok   原文不含渲染标签

== 子目录与图片 ==
  ok   子目录文档渲染                    <h2 id="安装步骤">
  ok   上级相对链接                      href="/index.md"
  ok   同级相对链接                      href="/guide/advanced.md"
  ok   图片相对路径                      src="/media/logo.svg"
  ok   svg Content-Type                  image/svg+xml

== 目录跳转与深度树 ==
  ok   目录补斜杠 301
  ok   301 Location                      Location: /guide/
  ok   树含深层文件 / 树含图片

== 全文搜索 ==
  ok   正文命中分区 / 命中高亮            <mark>标准库</mark>
  ok   结果带行号锚点                    #L
  ok   大小写不敏感                      <mark>mdview</mark>
  ok   文件名命中分区
  ok   无结果提示 / 空查询提示
  ok   搜索结果指向 .md                  href="/index.md#L51"

== 错误处理与安全 ==
  ok   不存在返回 404
  ok   404 页面友好
  ok   越界路径不泄漏                    /etc/passwd -> 404
  ok   不返回 passwd 内容
  ok   HEAD 可用
  ok   非 md 文件也可读

== 站内链接与图片（断链检查） ==
  ok   站内链接全部可解析（共 15 个）
  ok   code-blocks: python / javascript / typescript / go / rust / java / c / cpp /
                    bash / sql / json / yaml / toml / ini / makefile /
                    dockerfile / docker-compose / brainfuck / text / markdown 块
  ok   code-blocks: Dockerfile 指令着色（含小写 run）
  ok   code-blocks: Compose 键着色 / 语言标签
  ok   code-blocks: UTF-8 未切数字
  ok   code-blocks: 无语言块无空标题栏
  ok   code-blocks: 围栏内 HTML 被转义
  ok   code-blocks: 围栏内 div 未被当标签
  ok   code-blocks: 行内码保护星号
  ok   code-blocks: 转义反引号

== 参数开关（另起临时实例） ==
  ok   safe: .md 仍可读                 200
  ok   safe: 图片仍可读                 200
  ok   safe: 其他文件 404
  ok   no-search: /search 404
  ok   no-search: 无搜索框
  ok   no-search: 文档页也无
  ok   端口占用自动回退                  "端口 8739 不可用（Address already in use），尝试 8740…"
  ok   回退后端口可用                    http://127.0.0.1:8740/ -> 200

PASS=274 FAIL=0
全部通过 ✔
```

---

## 3. 手工复核（截图与原始输出）

### 3.1 视觉确认

用 Chrome headless 对实际服务截图：暗色主题生效，代码块按语言着色（关键字红、函数紫、
注释灰、字符串蓝），表格有表头底色，任务列表显示禁用复选框，嵌套列表缩进正确，
中文标点后强调正常闭合。

截图存档（可直接打开核对）：

- [`docs/media/screenshot-render.png`](docs/media/screenshot-render.png) —— `guide/advanced.md`：
  边界表格、转义写法、中文强调
- [`docs/media/screenshot-index.png`](docs/media/screenshot-index.png) —— `index.md`：
  目录、任务列表、嵌套列表、代码高亮

代码块专项页（`docs/guide/code-blocks.md`）也用同样方式逐一核对过：12 种语言的
标签与配色、未知语言退化、无语言块无空标题栏、围栏内 Markdown 完全不解析。

### 3.2 转义与裸 HTML

```console
$ python3 -c "import mdview; print(mdview.render_markdown(r'\*不是斜体\*'))"
<p><span class="esc">*</span>不是斜体<span class="esc">*</span></p>

$ python3 -c "import mdview; print(mdview.render_markdown('<script>alert(1)</script>'))"
<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>
```

被转义的字符包在 `.esc` 里（虚线底边标记），**不会**被二次解析成强调；
裸 HTML 全部转义，`.md` 无法作为脚本载体。

### 3.3 安全边界

```console
$ curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8731/../../../../etc/passwd'
404
$ curl -s 'http://127.0.0.1:8731/../../../../etc/passwd' | grep -c 'root:'
0
```

`..` 段在服务端被夹紧在 `--root` 内，不可能读到根外文件（`--root docs` 时该请求解析为
`docs/etc/passwd`，不存在 → 404）。

---

## 4. 本轮验证中发现并修复的真实缺陷

验证不是走过场，下面每一条都是本轮实际抓出来并改掉的：

| # | 现象 | 根因 | 修复 |
|---|------|------|------|
| 1 | `**粗体**` 渲染成 `<em>*粗体</em>` | 强调正则的 flanking 用 `\w`，中文被当词字符 | 重写为显式 flanking：ASCII 词内不成对，CJK 按标点处理 |
| 2 | `***粗斜***` 配成 `<strong>*粗斜</strong>*` | 长 run 被定界符正则贪婪切成 `***`+`*` | 先取完整 run，再按 2/2 切块；三连走预处理直接产出嵌套标签 |
| 3 | `**粗体**和**又粗体**` 关错位置 | 配对用「最远 closer」而非最近 | 改为从右往左的最近配对，并要求 closer 未被认领 |
| 4 | 嵌套列表被当成松列表（多出 `<p>`） | dedent 用固定宽度，深层条目的相对缩进丢失 | 按父条目内容列 dedent，保留相对层级 |
| 5 | 缩进的嵌套列表标记被段落吞掉 | `_starts_block` 没跳过前导空格 | 用 `lstrip` 后的文本判块起始 |
| 6 | 文档间链接点击 404 | 链接重写成 `.html`，但服务端只认 `.md` | 保留 `.md` URL（与 `?raw=1` 一致，刷新/收藏可靠） |
| 7 | 图片/相对链接解析到 `docs/a.md/img/...` | 基准目录误用了文档全路径 | `RenderContext.base = dirname(rel_path)` |
| 8 | 越界链接被强行改成 `.html`；绝对路径拼出 `//` | 重写与扩展名改写未绑定；前导斜杠未去 | 重写失败即保留原文；绝对路径按根内归一化 |
| 9 | `文字` + `---` 被当二级标题 | Setext 与 hr 判定冲突 | 只支持 `===` 形式；`---` 一律分隔线（已写入 README §4） |
| 10 | `--no-search` 只关了路由，页面搜索框还在 | 模板参数 `show_search` 未从配置透传 | 目录页与文档页都传 `CFG.search` |
| 11 | 无语言代码块渲染出**空标题栏** | 无条件输出 `.codehdr` | 无语言时不输出该元素 |
| 12 | 跑完测试残留 mdview 孤儿进程 | `$!` 取到的是子 shell 的 PID，`kill` 杀不到 python；EXIT trap 也未登记后起的三个实例 | 去掉多余子 shell 让 `$!` 直指 python，并把所有实例 PID 登记进 cleanup trap |
| 13 | 表格里出现字面量 **`MK0`/`MK1`** | 转义被放进 token 池，而行内码内容里也含 token → 还原时下标错位 | 转义改用私有区标记、不进 token 池；行内码匹配期间屏蔽 NUL 与标记内反引号 |
| 14 | `\*x\*` 渲染成 `<em>x</em>` 且页面上留下不可见标记 | 强调扫描器把转义标记当"词内字符"，`**` 拒绝打开、标记泄漏 | 被转义的定界符标为字面量节点，不参与配对（用 `continue` 跳过会打乱文本切片、造成重复输出，已避开） |
| 15 | 转义还原把 `<em>` 整段吞掉 | 还原正则用 `(.)`，会跨越标记匹配 | 中间只允许一个非标记字符 `[^\ue000\ue001]` |
| 16 | **代码块里的 `<script>` 原样输出（可用 XSS）** | 高亮器虽然会转义，但 `parse_inline` 的 `_TAG_RE` 把代码内容里形如 `<div>` 的片段当成「受保护的裸 HTML」放行 | 高亮前把 `<` `>` 换成私有区占位符，高亮后还原为 `&lt;` `&gt;`；并加回归测试覆盖 4 种载荷 |
| 17 | **不支持 Dockerfile 高亮**（只有碰巧重合的 `FROM`/`AS` 亮） | `dockerfile` 不在 `LANG_KEYWORDS`，走通用规则 | 新增 Dockerfile / Containerfile / Docker Compose 关键字表与显示名；并支持按语言大小写不敏感（`RUN` 与 `run` 都着色）；顺带补 TOML / INI / Makefile，共 17 种 |
| 18 | `C.UTF-8` 的 `8`、`v1.2.3` 的 `2.3`、`192.168.1.1` 被切成数字 | 数字正则的边界只排除 `\w` 和 `.`，没排除 `-`，也没排除前面紧跟字母/点的情形 | 改为 `(?<![\w.\-])…(?![\w.\-])`，并加跨语言回归用例 |
| 20 | 带行内码的标题锚点粘连（`pythonpython`） | `slugify` 直接把 HTML 标签删掉，`Python` 与 `<code>python</code>` 粘成一个词 | 标签替换为分隔符，锚点变为 `11-python-python-py` |
| 19 | 文档里的 `/media/xxx` 在「默认根」启动时 404 | 根相对路径按服务根解析，只有 `--root` 恰好等于文档库根才对 | 不改语义（同一 URL 必须指向同一文件），改为启动时检测「根下无 .md 但子目录有」并提示该用的 `--root`；文档补前置条件说明；自检新增断链检查 |

配套：`tests/tests_render.py` 的期望值也按 CommonMark 规则逐条复核过，
原先写错的期望（`中文__粗__中文`、`中*插*文`、`**粗体 **内**`、多测试用例）已改正，
而不是让实现去迁就错误的断言。

---

## 5. 复现方式

```bash
cd /Users/hpy/Documents/deepseek-harness/md-preview
python3 tests/tests_render.py      # 111 项
bash tests/selftest.sh             # 198 项（自动起停临时服务）
```

`tests/selftest.sh` 支持 `PORT=9000 bash tests/selftest.sh` 换端口；结束时打印
`PASS=.. FAIL=..`，非零退出码表示有失败项及失败清单。测试与开发工具全部隔离在
[`tests/`](tests/README.md) 目录，仓库根只留 `mdview.py` 与文档。

---

## 6. 一轮正式代码评审后的修复（19 条全部处理）

以**空树为固定点**做过一次双轴评审（Standards：文档化标准 + smell 基线；Spec：立项时
锁定的 23 条决定 + 3 条追加需求）。评审发现 19 条，全部修完；下表是它们与本轮的对应关系。

### 6.1 Standards 轴（11 条）

| # | 发现 | 处理 |
|---|------|------|
| S1 | `SECTION 8` 分隔带不存在，而 README 与代码注释都声称有 10 段 | 在目录/搜索代码真正起点补上分隔带，现为 10 段 |
| S2 | README 称"行号级导航"，代码注释却写"行号会漂移、请用关键字搜索" | 改为**不写行号的 section 唯一标识**（如搜 `SECTION 5`），两份自述统一；后续按用户要求删掉了临时的 `sync_nav.py` 生成器 |
| S3 | README 的测试计数陈旧（98 项 vs 实测） | 全量修正为实测值 |
| S4 | `SELFTEST.md` 残留"39 项" | 修正 |
| S5 | 死代码：`_DELIM_RE_CACHE`、`parse_emphasis_inner`、`_restore`、`_find_md_root`、`Config.raw_ok`、`--no-wait`、恒真的 `same_slot` | 全部删除 |
| S6 | `SKIP_DIRS` 语义三份拷贝且已漂移 | 统一引用模块常量 `SKIP_DIRS` |
| S7 | href 拼装 5 处、`depth_nav` 3 处重复 | 抽出 `url_for_rel()` 与 `depth_nav_html()` |
| S8 | `Handler._dir_page` 一函数多职责 | 拆为 `_dir_page` / `_resolve_depth` / `_tree_view` / `_list_view` / `_parent_link` / `_index_title` |
| S9 | `--no-wait` 是空转开关 | 删除（同 S5） |
| S10 | `tests/selftest.sh` 起服务循环复制 5 份、缺 `local`、头部硬编码绝对路径 | 抽出 `serve_temp()` / `wait_ready()`，补 `local`，去掉硬编码路径 |
| S11 | 魔法数：缓存上限、端口重试次数、资源目录名 | 提升为 `RENDER_CACHE_MAX` / `PORT_TRIES` / `ASSET_DIRS`；端口重试并暴露为 `--port-tries N` |

### 6.2 Spec 轴（8 条）

| # | 发现 | 处理 |
|---|------|------|
| P1 | 搜索的 `#L51` 是死链（渲染页没有行锚点） | `?raw=1` 改为**源码视图，每行带 `id="L<n>"`**，搜索链接指向它；自检核对"第 5 行内容与源文件一致" |
| P2 | 仅文件名命中的文件整个消失（与决定 11 矛盾） | `search_markdown` 改为返回 `(body_hits, name_hits, …)` 两栏并集；新增单元测试与端到端断言 |
| P3 | install.md 的根路径图片在默认根下 404 | 保留标准语义（同一 URL 指向同一文件），改文档写清前置条件 + 启动横幅提示该用的 `--root` |
| P4 | 决定 5 说 6–8 种语言，实为 17 种 | 保留（Dockerfile 是你要求的），在 README 明确列出并说明 |
| P5 | 启动自动探测文档根属未被要求的新功能 | 保留（你在"全部修复"里确认了它的价值），此处登记为已授权范围 |
| P6 | 决定 5 说"只高亮带语言标识的围栏"，实现却给无标识块也着色 | 无标识围栏改为**整块素色**；`text`/`plaintext`/`txt`/`none`/`raw` 同样素色（此前 `text` 与 `plaintext` 行为还不一致） |
| P7 | CJK 强调偏离 GFM 常用子集 | 保留行为（中文可用性优先），在 README §4 新增**偏离对照表**并给出改回严格 GFM 的方法 |
| P8 | `bind_server(tries=10)` 是未声明的隐藏上限 | 暴露为 `--port-tries N`（默认 10） |

### 6.3 本轮新增/变更的验证

- 单元测试 45 项（新增：仅文件名命中、无语言围栏素色）
- 端到端 108 项（新增：源码视图行锚点与内容一致性、搜索分栏计数、仅文件名命中）
- 导航改为 section 唯一标识（搜索定位，无行号），因此不需要生成器

---

## 7. 目录整理：测试与源码分离

早期版本把 `mdview.py`、两份测试、一个维护脚本、两份文档、示例语料与截图全部平铺在
仓库根，交付物与开发物料混在一起。现已分离：

```
md-preview/
├─ mdview.py          # 唯一可交付源码
├─ README.md
├─ SELFTEST.md
├─ tests/             # 测试 + 开发工具（含自己的 README）
│  ├─ tests_render.py   selftest.sh
└─ docs/              # 示例语料（含 media/）
```

脚本都改为**从自身位置推出仓库根**（`selftest.sh` 新增 `ROOT`，
`tests_render.py` 的 `sys.path` 指向上一层），因此从任何目录执行都可以 ——
已实测在仓库根与 `/tmp` 下分别执行 `tests/selftest.sh`，结果一致。

按用户要求删除了临时的 `sync_nav.py`：导航改为 **section 唯一标识**（搜索定位），
不写行号也就不需要生成器维护。

---

## 10. 源码类文件中文乱码（真实用户报告）

用户现象：**打开 `.py` 文件，里面的中文变成错误文字**。定位结果是撤销掉的
`8f0859c` 引入的：

| 项 | 撤销前（手写 MIME 表） | `8f0859c` 之后（stdlib mimetypes） |
|----|----------------------|-----------------------------------|
| `.py` | `text/plain; charset=utf-8` | `text/x-python`（**无 charset**）→ 浏览器猜编码 → 中文乱码 |
| `.ts` | 未收录 | `video/mp2t`（MPEG 传输流）→ TypeScript 被当视频 |
| `.sh/.c/.cpp/.go/.rs/.java/.sql/.ini/.log` 等 17 种 | 未收录 | 未收录 → `application/octet-stream` → 点开即下载 |

修法（**不碰 Markdown 路径，也不动图片/PDF 等二进制表项**）：新增
`TEXT_EXT` / `TEXT_FILENAMES` 两张表，命中即按 `text/plain; charset=utf-8` 发送，
优先级高于 mimetypes：

- `.ts` 刻意当 TypeScript（覆盖 stdlib 的 `video/mp2t`）
- `Makefile` / `Dockerfile` / `.gitignore` 等无扩展名文件按文件名判定
- 图片（`.png/.svg/.jpg`）、`.pdf`、压缩包等仍走原 MIME 表，行为不变

验证：单元测试 50 项（+5：源码扩展名判定、`.ts` 非视频、无扩展名文件名、
二进制仍为二进制、二进制表项未被影响）；端到端 119 项（+11：
7 种源码文件的 charset、`.ts` 非视频、图片类型、字节 sha256 原样）。

---

## 11. 代码块复制按钮

需求：给代码块加复制按钮。约束是**不破坏已有承诺**——零第三方依赖、禁用 JS 也能阅读。

实现要点：

| 设计 | 理由 |
|------|------|
| 按钮**由 JS 注入**，HTML 里没有 `.copybtn` | 禁用 JS 时不会出现"点了没反应"的死按钮（有断言盯住这一点） |
| 纯原生 JS，内联进页面 | 不引外部文件、不发额外请求，符合零依赖 |
| 文本取自 `pre > code` 的 `innerText` | 复制的是渲染后文本：不带高亮标签，也不含按钮自身文字（浏览器实测确认） |
| `navigator.clipboard` + `execCommand` 双路径 | 内网多为 `http://`，非安全上下文没有 Clipboard API，必须兜底 |
| **一直显示**，打印隐藏 | 不做悬停隐藏（用户要求）；只有悬停变色的轻反馈，`@media print` 下隐藏 |
| 语言条 + 代码区**两段叠放**（对齐 DSH 的 code block 形态） | 顶部条 flex 两端布局：左语言名、右复制按钮；顶部条只有上方圆角，视觉上像叠在代码区之上 |
| 带 `aria-label` | 可访问性 |

验证：

- 浏览器内探针（`--dump-dom`）：2 个代码块都注入成功；`innerText` 含中文、
  且**不含**"复制"二字（证明没把按钮文字一起复制）
- `node --check` 通过内联 JS 语法检查
- 无代码块的页面（目录索引、搜索结果）执行脚本无运行时错误，页面正常
- 单元测试 55 项（+5：脚本只注入一次、HTML 无硬编码按钮、双剪贴板路径、
  文本取法、常显与打印样式）
- 端到端 129 项（+10：内联脚本、Clipboard 路径、兜底路径、常显样式、
  触屏规则、HTML 无死按钮、目录索引仍正常、顶部条 flex 两端布局、
  按钮注入到顶部条、语言名在左侧）

### 样式调整（用户要求对齐 DSH）

用户要求把按钮改成"两个块叠在一起"的形态。我**没有凭印象画**，而是从
`/Applications/DeepSeek Harness.app/.../app.asar` 里解出 DSH 的实际样式：

    dsh-client-ui-primitives/lib/markdown/MarkdownText.module.css
    dsh-web-frontend/dist/assets/index-BPHePDI_.css

其中 `._block_7gxqk_4` / `._banner_7gxqk_24` / `._copyButton_1fs6g_139` 三条规则
给出了确切参数：容器圆角 + 底色、顶部条 `display:flex; justify-content:space-between;
padding:9px 14px`、复制按钮无边框、继承字色、悬停变蓝。本实现按此对齐，
按钮改为**一直显示**（DSH 默认是悬停显现，按用户要求简化）。
并使用自己的 CSS 变量（`--banner`）而非 DSH 的设计 token。

---

## 12. 移除「展开 3 层目录树」

用户要求移除该功能。涉及面比看上去广，一并清理：

| 位置 | 处理 |
|------|------|
| `--depth N` 参数 | 删除（它只服务于展开树） |
| `/` 首页的「展开 3 层树」入口 | 删除 |
| `?depth=N` 处理 | 删除；该查询参数现在被**无害忽略**，仍返回 200 的普通列表 |
| `Handler._tree_view` / `_resolve_depth` | 删除 |
| `render_tree()` | 删除 |
| `.tree ul / .tree>ul / .tree li` 样式 | 删除 |
| `Config.depth` | 删除 |
| `_dir_page(abs_dir, rel, qs)` | 参数 `qs` 随之无用，一并去掉 |
| README 的 `--depth` 用法/参数表/路由表 | 删除，路由表注明"无递归展开树" |

**故意保留的 `depth`**（与 UI 无关，别被名字骗到）：
`_docs_root_candidates.walk(rel, depth)` 与 `_has_md(path, depth)` 里的 depth 是
**文件探测的递归上限**（限深 3 层，避免全盘扫描）；`_page(depth_nav=...)` 与
`depth_nav_html()` 是**顶栏的当前路径标签**，都不是展开树功能。

验证：单元测试 61 项全绿；端到端 136 项（把原「带展开树入口」断言改为
「首页无展开树入口」+「无 .tree 样式」+「?depth= 无害忽略」+「忽略时仍是普通列表」）。

---

## 13. 搜索跳转落点居中

用户报告：点搜索结果跳转后，高亮行"在页面顶部太靠上"，希望居中。

定位：搜索结果是 `/index.md?raw=1#L51`，浏览器处理 `#L51` 时**默认把目标元素贴到
视口最上沿**（y=0），上方零留白。页面里既没有 `scroll-margin` 也没有 `scroll-padding`。

修法（两层，排序有讲究）：

1. **JS 居中**：自己算坐标 `window.scrollTo(0, rect.top + rect.height/2 - innerHeight/2)`，
   并夹紧到 `[0, scrollHeight - innerHeight]`
2. **CSS 兜底**：`scroll-margin-top:20vh; scroll-margin-bottom:70vh`
   —— 禁用 JS 时靠它保留偏移，不会顶到边

为什么不用 `scrollIntoView({block:"center"})`：**实测无效**。带 hash 首次加载时它会被
浏览器的原生锚点滚动盖掉，目标仍停在视口上方（实测偏差 −157px）。
改用显式 `scrollTo` 后实测**偏差 = 0**（目标行中心与视口中心重合）。

实测数据（Chrome headless，视口 557px 高）：

    改前：range.top=114  偏差=-157   ← 目标在视口上方
    改后：range.top=271  偏差=0      ← 正中（视口中心 278.5）

只在 `#L*` 锚点上生效，普通标题锚点（如 `#列表`）保持浏览器默认行为，不受干扰。
另有 `replaceState` 标记，避免"点同一链接两次"时重复滚动。

验证：单元测试 61 项（+4：scroll-margin 兜底、显式 scrollTo、只在 L 锚点生效、
上下夹紧与防重复滚动、源码视图确实每行带 id）；端到端 135 项（+6）。

---

## 14. 渲染样例总览（docs/preview）

用户要求：把「当前支持在浏览器里渲染的所有文件」放进 docs 目录，看实际效果。

新增 `docs/preview/`：一个总览页 + 55 个样例文件，覆盖三条内联路径：

| 路径 | 样例 |
|------|------|
| `TEXT_EXT`（源码/配置） | .py .sh .c .cpp .h .java .go .rs .ts .jsx .sql .ini .properties .env |
| MIME 表 | .yaml .toml .json .xml .txt .csv .tsv .rst .log .diff .patch |
| 文件名判定 | Makefile / Dockerfile / .gitignore / README |
| 图片 | png / bmp / gif（两帧动图）/ ico / svg |

外加两个**边界样例**：`text/empty.txt`（0 字节）与 `text/gbk-encoded.txt`
（故意非 UTF-8，用来验证编码兜底）。

### 图片是纯标准库构造的真文件

不提交"看起来像图片"的占位文本：`make_preview_samples.py` 用 struct/zlib 直接
拼出合法 PNG（IHDR+IDAT+IEND+CRC）、24 位 BMP、两帧 LZW 动画 GIF、含 AND 掩码的 ICO。
**已在 Chrome 里验证解码**（`naturalWidth/naturalHeight` 全部正确：120×120、64×64），
单元测试另校验魔数，端到端校验可访问性与 Content-Type。

`.jpg/.webp/.avif` 在支持列表里但**没有样例**：有损/复杂格式纯标准库造不出有意义的内容，
已在总览页注明。

验证：单元测试 66 项（+5：目录存在、索引链接全部可解析、图片魔数、
GBK 文件确实非 UTF-8、两条文本路径都覆盖）；端到端 153 项（+17：
38 个样例全部 200、逐类型 Content-Type、PNG/GIF 魔数、空文件、GBK 声明）。

---

## 15. `.csv` 无法预览

用户报告：`docs/preview/text/sample.csv` 点了没显示。

### 定位：不是本服务的问题，是浏览器的硬行为

先分层排除：

| 检查 | 结果 |
|------|------|
| 服务响应 | `200`，`Content-Type: text/csv; charset=utf-8`，字节与磁盘 sha256 一致 |
| 纯 `python3 -m http.server` | 同样发 `text/csv`，Chrome **同样下载**（DOM 0 字节） |
| 浏览器行为 | `.txt`/`.tsv`/`.json`/`.xml` 都内联，只有 `.csv` 不显示 |

然后做了对照实验，确认"到底什么决定内联还是下载"：

| 端口 | Content-Type | Content-Disposition | 结果 |
|------|--------------|---------------------|------|
| 9311 | `text/csv` | 无 | ❌ 下载 |
| 9312 | `text/csv` | `inline` | ❌ **仍下载** |
| 9313 | `text/plain` | `inline` | ✅ 内联 |

**结论：`Content-Disposition: inline` 完全无效，决定权只在 Content-Type。**

再扫一遍哪些类型会被强制下载：

    text/plain                      ✅ 内联
    text/javascript / text/css      ✅ 内联
    application/json / xml          ✅ 内联
    text/csv                        ❌ 下载
    text/tab-separated-values       ❌ 下载

### 处理

把 `MIME[".csv"]` 从 `text/csv` 改为 `text/plain; charset=utf-8`：
**文件内容与字节完全不变**（有 sha256 断言），只是换个声明让浏览器肯显示。
`.tsv` 本来就走 `TEXT_EXT` → `text/plain`，无需改动。

代价：`.csv` 的语义类型（`text/csv`）被放弃，换回"能在浏览器里看"。
标准库会发 `text/csv`，所以这一条**比 stdlib 更偏离**，但符合"能预览"的诉求。

验证：单元测试 69 项（+3：csv 不能是 text/csv、表里不得再有会下载的文本类型、
内联类型都要带 charset）；端到端 156 项（+3）；浏览器实测 DOM 233 字节、
内容渲染正确、字节 sha256 未变。

---

## 16. 预览上限（20 MiB）与无扩展名嗅探

用户需求：**没有扩展名时也要预览**；**文件过大时拒绝预览、直接下载**。

### 16.1 最终规则

| 顺序 | 条件 | 行为 |
|------|------|------|
| 1 | 超过 `--max-preview`（默认 20 MiB） | **准确类型 + `Content-Disposition: attachment`** → 下载（对 .md / 图片 / PDF 一切类型生效，`?raw=1` 也不例外） |
| 2 | 命中 `TEXT_EXT` / `TEXT_FILENAMES` | `text/plain; charset=utf-8` |
| 3 | 命中 `MIME` 表 | 按表（图片 / PDF / HTML…） |
| 4 | **无扩展名** | 嗅探开头 512 字节：有 NUL → `octet-stream`（下载）；无 NUL → `text/plain`（预览） |
| 5 | 其余 | `application/octet-stream`（下载） |

第 1 步在最前，所以"超大"优先于一切。第 4 步**只对无扩展名生效**——有扩展名的文件**不读内容**。

### 16.2 为什么是 20 MiB —— 实测数据（不是估计）

派子代理独立测量（Chrome 154，Apple Silicon，16 GiB）：

| 文本大小 | 加载+布局耗时 | Chrome 进程峰值内存 | 机器可用内存 |
|---------|--------------|-------------------|-------------|
| 1 MiB | 0.81 s | 0.24 GiB | — |
| 5 MiB | 3.17 s | 0.73 GiB | — |
| **20 MiB** | **13.73 s** | **2.48 GiB** | 4454 → 1539 MB |
| 50 MiB | 34.37 s（最高 135 s） | 5.90 GiB | 剩 41.5 MB |

- 内容**没有截断**（逐字节比对一致，DOM = 源 + 152 字节外壳）
- 耗时近似线性（约 0.68 s/MiB），**内存远差于线性**
- 20 MiB 纯 ASCII 便宜约 2.5 倍（≈5 s、1.7 GiB），所以开销跟内容相关
- **服务端完全不受影响**：TTFB 与文件大小无关（0.7-0.8 ms），内存只涨 0.1 MB

结论：**20 MiB 是"可用但很难受"的边界**，不是舒适区。测量者建议舒适阈值是 1-5 MiB。
`--max-preview` 可调，所以不想受限可设 `0`。

### 16.3 嗅探为什么只看 512 字节

来自 VS Code 的实测实现（反编译发行版 1.141.0）：**它也只扫前 512 字节的 NUL 字节**，
不验证编码，解码器非致命。我们跟着这个标准走，并明确承担它的漏洞：

| 情形 | 服务端判定 | Chrome 实际表现 |
|------|-----------|----------------|
| NUL 在开头 | 二进制 → 下载 | 下载 |
| NUL 在 511（前 512 内） | 二进制 → 下载 | 下载 |
| NUL 在 512（前 512 外） | **文本 → 预览** | **下载**（Chrome 自己的阈值更靠后） |
| NUL 在 5000 | **文本 → 预览** | 内联（NUL 渲染为不可见字符） |
| GBK 无 NUL | 文本 → 预览 | 内联（可能乱码但不下载） |

也就是：**前 512 字节干净、后面藏二进制的文件会被当文本**（VS Code 同样如此）。
危险情形都被拦住了——前 512 字节内出现 NUL 时两边都判二进制。

### 16.4 三个参照实现的结论

| 实现 | `.md` | 无扩展名 | 嗅探内容 | 大文件 |
|------|-------|---------|---------|--------|
| **nginx 1.31.5**（实测 + 源码） | 不在表里 → `text/plain` | `default_type` = **`text/plain`** | **从不** | 无上限（2 GiB 实测可发） |
| **Apache 2.4.67**（本机实测） | 不在表里 → **不发 Content-Type** | 不发 Content-Type | **从不** | 无上限 |
| **VS Code**（反编译） | — | 按内容（前 512 字节 NUL） | **只看 512 字节** | 20 MiB 只关高亮，不拒绝 |
| **本项目** | 渲染成 HTML | 嗅探 512 字节 | 只看 512 字节 | **20 MiB 改为下载** |

三点值得记下：
1. **ngix/Apache 都不嗅探内容**，纯查扩展名表。我们引入嗅探是**比它们更主动**的一步，
   理由只有一个：无扩展名文件（`.git/HEAD`）用扩展名无从判断。
2. **nginx 的 `default_type` 默认是 `text/plain` 而不是 `octet-stream`** —— 也就是它对
   未知类型**倾向内联显示**。这支持"无扩展名文本应当预览"的方向。
3. nginx 的 `.ts` 也是 `video/mp2t`（与 stdlib、Apache 一致）。我们把它当 TypeScript，
   是**刻意偏离**三个主流实现，理由写在第 §15 节。

### 16.5 测试样例（docs/preview/binary 与 large）

用户要求"要能自己测一下"，所以放了可直接点击的样例：

- `docs/preview/binary/` —— 8 个无扩展名文件（专测 512 字节边界，`nul_at_511` 与
  `nul_at_512` 只差一个字节）+ 真 PNG/PDF/ZIP + ELF/Mach-O 文件头
- `docs/preview/large/` —— 5 个超过 20 MiB 的文件，**是稀疏文件**：表观 21-25 MiB，
  磁盘与 git 只占几百 KB（实测 115 MiB 表观 -> git 约 500 KB）
- `docs/preview/binary-test.md` —— 逐个标注预期行为的测试清单页

### 16.6 验证

- 单元测试 77 项（+8：大小解析各种写法与非法输入、512 边界、
  无扩展名文本/二进制、超大保类型、优先级、有扩展名不受嗅探影响）
- 端到端 173 项（+20：嗅探四档边界、GBK 仍算文本、超限 .md/.bin/`?raw=1` 均下载、
  `Content-Disposition` 不写 filename、`--max-preview` 解析）
- 浏览器实测 13 项判定（12 项与预期一致；`noext_nul512` 服务端判文本而 Chrome 仍下载，
  已在 §16.3 记录为两套阈值不同）

---

## 17. 目录索引的下载按钮

用户要求：**每个文件后加一个下载按钮**。

### 实现

目录索引的每个文件行右侧加一个 `<a class="dl" href="<路径>?download=1">⬇ 下载</a>`，
**目录行不加**。服务端识别 `?download=1` 并强制发 `Content-Disposition: attachment`。

为什么走服务端参数，而不是 HTML5 的 `<a download>` 属性：

| 方案 | 问题 |
|------|------|
| `<a download>` 属性 | 依赖浏览器；对跨源/某些类型行为不一致；且**不改变响应头**，无法在服务端断言 |
| **`?download=1`（采用）** | 服务端发头，**对任何类型一致有效**，可被 curl 断言，也方便外部脚本直接复用 |

### 保留准确类型，不退化成 octet-stream

`resolve_ctype()` 的 `force_download` 参数只负责**附加强制下载头**，不改类型：

    /x.md?download=1     ->  text/markdown; charset=utf-8  + attachment
    /x.png?download=1    ->  image/png                     + attachment
    /x.py?download=1     ->  text/plain; charset=utf-8     + attachment
    /x.zip?download=1    ->  application/octet-stream      + attachment

`.md` 走下载时**返回服务器上的原始 Markdown 字节**，不是渲染后的 HTML（有断言）。
原先的 `too_big` 参数因此泛化为 `force_download`：超限与用户点按钮是同一条路径。

### 文件名：必须写 filename（原结论是错的，已更正）

**我最初的实现只发裸 `attachment`，理由是"浏览器用 URL 末段当文件名"。这个结论
对普通文件名成立，但用户报告 `.gitignore` 下载后变成了别的名字。**

复现：Chrome 把 `/preview/.gitignore?download=1` 存成 **`gitignore.txt`** ——
前导点被当成隐藏文件标记去掉，**又按类型硬加了 `.txt`**。

于是穷举实测所有写法（Chrome 落盘观察）：

| Content-Disposition | 落盘 | 评价 |
|---|---|---|
| 裸 `attachment` | `gitignore.txt` | ❌ 点没了**还加后缀** |
| `filename=".gitignore"` | `gitignore` | 点没了，无多余后缀 |
| `filename` + `filename*` 双写 | `gitignore` | 同上 |
| `filename="%2Egitignore"` | `gitignore` | 同上 |
| 只有 `filename*` | `gitignore` | 同上 |
| `filename="dot.gitignore"` | `dot.gitignore` | ✅ 不以点开头就完整保留 |

**结论：前导点任何写法都保不住** —— 浏览器拒绝把下载名设成隐藏文件，是安全策略。
所以最终实现是双写 `filename` + `filename*`，达到能做到的最好结果：

    binary-test.md  -> binary-test.md   （完全一致）
    big.md          -> big.md           （完全一致）
    .gitignore      -> gitignore        （丢前导点，但不再多加 .txt）
    测试 文件.md     -> 测试 文件.md      （中文靠 filename* 还原）

### 双写是必需的，且顺序有讲究

- `filename` **只能是 latin-1**（HTTP 头的限制）。把中文直接写进去会抛
  `UnicodeEncodeError`，**整个响应挂掉**（实测 HTTP 000，连接断开）。
  所以回退名必须把非 ASCII 与危险字符（引号/分号/换行）替换成 `_`。
- `filename*`（RFC 5987 的 `UTF-8''` 百分号编码）负责还原真实名字；现代浏览器优先用它。
- 有断言校验：回退名里的引号必须成对（否则伪造出的头会破坏解析）、整行必须能按
  latin-1 编码、空文件名也要给出可用回退名。

### 验证

- 单元测试 81 项（+4：文件行有按钮而目录行没有、title/aria-label、
  force_download 保留准确类型、默认不下载）
- 端到端 214 项（+16：索引含链接、目录行无按钮、6 种类型的下载头、
  3 种类型不退化、`.md` 返回原文且不含 HTML、不带参数仍是预览）
- 浏览器实测：加 `?download=1` 三个类型全部下载（DOM 0 字节）；
  不加参数三个类型全部内联预览（对照）
- 截图确认按钮位置（在文件大小/mtime 右侧）、目录行无按钮

---

## 18. 第二轮评审：四个真实缺陷（含一个存储型 XSS）

用户要求"分析下有没有 bug"，三路独立审查 + 我自己的复现共找出 22 项。以下是
**已复现并修复**的部分。所有断言都对**修复前的版本**反向验证过检出能力。

### 18.1 B1 存储型 XSS（安全，最严重）

README 与 docstring 都写着"裸 HTML 全部转义，**100% 消除 .md 作为 XSS 载体**"。
这句话**不成立**：只挡住了原始 HTML，没挡链接目标。

| 输入 | 修复前渲染 | 后果 |
|------|-----------|------|
| `<foo@bar.com"onmouseover="x>` | `<a href="mailto:foo@bar.com"onmouseover="x">` | 引号闭合属性，**注入活的事件处理器** |
| `[x](javascript:a"onmouseover="x)` | `<a href="javascript:a"onmouseover="x">` | 同上 |
| `[x](javascript:alert(1))` | 可点击的 `javascript:` 链接 | 点击执行 |

审查者用真实 Chrome + CDP 验证：`typeof onmouseover === "function"`，派发
`mouseover` 后 `document.title` 变成攻击者设定的值 —— **确认执行**。

**根因**：`_autolink_sub` 的 mailto 分支既没转义 href 也没转义文本；
scheme 分支把未转义的原始 target 写进 `href`；且**全库没有任何协议白名单**。

**修法**：新增 `safe_href()`，两层防护 —— 协议白名单（`javascript:`/`data:`/
`vbscript:` 一律返回空串、不产出属性）+ 属性转义；自动链接两个分支都转义 href
与文本；引用式链接与图片共用同一条路径。

**核心断言**：按 HTML 的引号规则解析标签，属性名必须落在白名单内。
该断言对修复前版本能抓出 `{'onmouseover'}` / `{'onerror'}`（已反向验证）。

### 18.2 B2 `?raw=1` 一个请求写三个响应（协议破坏）

`_raw_page()` 自己发过响应又返回 `None`，调用处再交给 `_send(200, None)`
→ `len(None)` 抛 `TypeError` → 兜底逻辑再发一个 500。服务端日志一个 GET 三行：

    "GET /index.md?raw=1" 200 -
    "GET /index.md?raw=1" 200 -
    "GET /index.md?raw=1" 500 -

原始 socket 可见：完整 200 + **没有 Content-Length 的残缺 200** + 完整 500。
keep-alive 连接上同一连接的下一个请求会超时。**这是搜索结果与「源」按钮走的路径**。

**修法**：`_raw_page` / `_markdown_page` 统一改为返回 `(status, body)`，
由路由唯一发送响应。同源问题（`.md` 不可读时 404 + 残缺 200 + 500）一并修掉。

### 18.3 B3 `Location` 与「源」按钮双重百分号编码

`quote_seg_path(path)` 对**已经编码过**的路径再编码：`%` → `%25`。
`/my%20dir` → `Location: /my%2520dir/` → 跟随后 404；中文目录同样全挂，
且中文名文件的「源」按钮是坏的（`href="/my%2520note.md?raw=1"`）。
**修法**：改用已解码的 `rel` 重新编码。

### 18.4 B4 监听 backlog 默认 5

从未设置 `request_queue_size`，stdlib 默认 5。A/B 对照（只改这一个值）：
默认 backlog 下 30 并发有 9 个被内核直接拒连（ECONNREFUSED），改成 128 后 30/30 成功。
**浏览器打开一个页面就会并发 6 个连接**，所以这不是理论值。**修法**：设为 128。

### 18.5 B5 FIFO / 设备文件挂死线程

`open(path, "rb")` 对 FIFO **阻塞到有写者为止**（单独验证：线程 6 秒不返回），
每个请求永久吃掉一个线程（ThreadingHTTPServer 每连接一线程）。指向 `/dev/zero`
的链接更糟：`getsize()` 返回 0 却无限吐数据，`Content-Length` 与实际不符。
**修法**：新增 `_is_regular_file()`（`S_ISREG`），文件服务、嗅探、`_read_text`
三处入口全部先判类型；FIFO 现在立即 404（<1ms）。

### 18.6 B6 符号链接逃出 `--root`

`_resolve()` 只做字符串夹紧，**从不解析符号链接**。root 内一个指向 `/etc/passwd`
的链接就能把 9350 字节原样读出来；`--safe` 也挡不住。README 声称的
"路径穿越被夹紧在 root 内"对符号链接不成立。
**修法**：加 `realpath` 二次校验（解析后仍须在 root 内），越界返回 403。

### 18.7 B7 `/search` 无视 `--max-preview`

25 MB 的 `.md` 直接 GET 是下载，但 `/search` 照样整个读进内存 ——
小请求放大到"最大的那个 .md"，一个超大文件就能把服务端内存打满。
**修法**：搜索与预览共用同一条大小闸门，并跳过非常规文件。

### 18.8 B8 `--root /` 时全部 403

`root + os.sep` 拼成 `//`，`startswith` 永不成立。**修法**：抽 `_inside()`
处理根目录边界。

### 18.9 B9 客户端中断刷 traceback

标准库只捕 `TimeoutError`，keep-alive 期间的下一次 `readline` 遇到
ECONNRESET 会冒泡给 `socketserver.handle_error`，每个 RST 打一整段回溯。
**修法**：包一层 `handle_one_request`，只补捕这两种异常并静默关闭连接，
正常路径原样交回父类。

### 18.10 第三轮评审发现的其余缺陷

| 编号 | 问题 | 修法 |
|------|------|------|
| S4 | token 占位符泄漏到链接文本/URL/title/alt（`%00MK0%00`） | 新增 `read_tokens()`，统一 token 语义 |
| S5 | 链接里嵌图片（徽章）被转义成文本 | 新增单趟 `scan_inline()`，图片与链接一起处理 |
| S6 | 行内链接标签里的强调不生效（自己的文档就是受害者） | 标签递归解析 |
| S7 | `\>` 漏出私有区标记 `\ue000` | 转义整段做成 token（原来靠"标记夹一个字符"的正则，`&gt;` 有 4 个字符永远匹配不上） |
| S8 | 行内码里的转义反引号漏出 `\ue013` / `MK0` | 行内码内就地还原屏蔽字符与转义 token |
| S9 | 裸 NUL 直接进 HTML | 入口清除 NUL |
| S12 | URL 里的配对括号被截断 | 扫描器做括号配对 |
| S14 | `文字 \| 文字` + `---` 被当表格 | 分隔行必须自带竖线 |
| S15 | 围栏内的 `[r]:` 被当成引用定义 | 采集引用定义时跟踪围栏状态 |
| S16 | `a` / `a-1` / `a` 生成重复 id | 用"已用 id 集合"+最小可用后缀 |
| S17 | **链接正则平方级 DoS**：78 KB → 59 秒 | 手写单趟扫描器（栈配对），78 KB → 0.018 秒 |
| S18 | 强调配对平方级：31 KB → 9.4 秒 | 定界符数量封顶 `MAX_DELIM_RUNS` |
| S19 | `_parse_size("9"*309)` 抛 OverflowError | 改用 Decimal + 数值上界 |
| S20 | `_parse_size` 大整数丢精度 | 同上 |
| S21 | `_fmt_size` 定义两次（前一处是死代码） | 删除重复定义 |
| S2 | 深嵌套（`>`*1000）RecursionError → 500 | `MAX_BLOCK_DEPTH` + 入口兜底 |
| S3 | 文档里字面写 token 形式 → IndexError → 500 | 下标越界时当普通文本 |

### 18.11 验证

- 单元测试 111 项（+14 条针对本轮缺陷的回归，含核心安全断言）
- 端到端 239 项全绿；残留进程 0
- **反向验证**：核心安全断言对修复前版本能检出 `onmouseover` / `onerror` 注入
- 性能实测：链接 78 KB 从 **59 秒** 降到 **0.018 秒**

---

## 19. 根目录的「上级目录」链接跳到 about:blank#blocked

用户报告：把上层目录当根启动时，点「上级目录」会跳到 `about:blank#blocked`。

### 根因

一级子目录（如 `/lvl1/`）的上级是**根目录**，而 `url_for_rel("", trailing_slash=True)`
会拼出 **`//`**：

    url = "/" + "/".join([])   ->  "/"
    return url + "/"           ->  "//"      ← 问题在这里

浏览器把 `//` 当作**协议相对 URL**（`//host/path` 的简写），于是把它解释成
"空 host"，导航被安全策略拦成 `about:blank#blocked`。这解释了为什么只有
"上级是根"这一种情况会中招 —— 二级目录的上级是 `/lvl1/`，不经过这个分支。

### 修法

`url_for_rel` 在补尾斜杠前先判断是否已经以 `/` 结尾：

    return url if url.endswith("/") else url + "/"

对根返回 `/`，对其他路径行为不变（`/guide` -> `/guide/`）。

### 验证

- 单元 116 项（+5）：根的单斜杠、所有输入都不以 `//` 开头、
  一级子目录上级是 `/`、二级是 `/lvl1/`、根目录页没有上级链接
- 端到端 245 项（+6）：四种目录页的上级链接值、点上级能回到根、
  **全站目录页不出现 `href="//"`**
- 全库排查：98 个站内链接无一以 `//` 开头
- Chrome 实测：`/lvl1/` 页面里上级链接已是 `href="/"`，截图确认页面正常
- 压缩版同步重新生成并复跑两套测试（116 / 245 全绿）

---

## 20. 扩充白名单：前端 / Java / 包管理生态

用户要求"再支持一下代码中常见的文件类型，像前端包管理/java 包管理相关的"。

### 做法：先测量，再添加

先用 `resolve_ctype` 逐个跑候选（**不是凭印象**），找出真的会下载的 17 个：

    yarn.lock  bun.lock  bun.lockb  build.gradle.kts  settings.gradle.kts
    MANIFEST.MF  .mvn/jvm.config  Makefile.am  Pipfile.lock  poetry.lock
    go.sum  Cargo.lock  .terraform.lock.hcl  .pnpmfile.cjs
    Gemfile.lock  mix.lock  pubspec.lock

### 加入的内容

| 类别 | 新增 |
|------|------|
| 前端锁文件与配置 | `.lock`（yarn/bun/Pipfile/poetry/Cargo/Gemfile/mix/pubspec）· `.mjs` · `.cjs` · `.resolved` · `.browserslistrc` · `.stylelintrc` · `.lintstagedrc` · `.swcrc` · `.commitlintrc` · `.markdownlintrc` |
| Java / Gradle / Maven | `.kts`（`build.gradle.kts`）· `.mf`（`MANIFEST.MF`）· `.config`（`jvm.config`/`maven.config`）· `gradlew` · `mvnw` |
| Go / Rust | `.mod`（`go.mod`）· `.sum`（`go.sum`） |
| autotools / Xcode / Swift | `.in`（`Makefile.in`）· `.ac`（`configure.ac`）· `.am` · `.pbxproj` · `.hcl`（terraform lock） |
| .NET / NuGet | `.csproj` `.vbproj` `.fsproj` `.vcxproj` `.vcproj` `.xproj` `.sln` `.props` `.targets` `.resx` `.nuspec` `.ruleset` `.user` |

结果：`TEXT_EXT` 66 → **94**，`TEXT_FILENAMES` 29 → **55**。

### 两个有意的取舍（写在代码注释里）

1. **不收 `.lockb`** —— `bun.lockb` 是**二进制**锁文件（`bun.lock` 才是文本，
   由 `.lock` 覆盖）。已加断言：`bun.lockb` 必须仍是 `application/octet-stream`。
2. **`.mod` 当文本** —— `go.mod` 是文本，但音频领域的 `.mod`（Amiga 模块音乐）
   是二进制。本工具面向代码与文档预览，`go.mod` 的出现频率高得多，所以选前者；
   真有 `.mod` 音频，点开会是乱码而不是下载。

### 验证

- 单元 119 项（+3）：56 个生态文件全部预览、`bun.lockb` 仍二进制、
  11 种真二进制（`.zip/.png/.pdf/.mp4/.docx/.so/.dylib/.exe/.lockb/.wasm/.woff2`）
  不许被带成文本
- 端到端 249 项（+4）：26 个生态文件在真实服务上都是 `text/plain`、
  `bun.lockb` 仍下载、`package.json` 仍是 JSON、`pom.xml` 仍是 XML
- **基线回归**：把仓库现有 73 个文件的 `resolve_ctype` 结果做成快照，
  扩容前后**逐条比对，改变数 = 0**
- 压缩版已同步重新生成

---

## 21. 类型判定改为三层：白名单 + MIME 表 + 嗅探兜底

用户提议："已经有判断二进制文件的方法了，为什么还要搞白名单？不如全都按这个判断。"

### 先测量，再决定

**嗅探的规则极窄**：只读开头 512 字节、只看有没有 NUL。所以它有确定的盲区，
实测出来的反例：

| 文件 | 前 512 字节有 NUL？ | 单靠嗅探 |
|------|-------------------|---------|
| `real.pdf`（真实 PDF） | **没有** | 判成文本 → 无法内联显示 PDF |
| 纯 ASCII 头的 `backup.tar` | 没有 | 判成文本 |
| 改名成 `.bak` 的 PNG | 没有 | 判成文本 |

> **更正**：本节初版把 `docx`/`xlsx` 也列为"嗅探认不出的反例"，理由是"本质是 ZIP"。
> 实测**这个结论是错的** —— 真实 Office 文件的 ZIP 本地文件头在**偏移 4-5 就有 NUL**，
> 嗅探正确判为二进制。当时那个反例是我自己造的假样本
> （`b"PK\x03\x04" + b"text"*n`，纯 ASCII，不是真 ZIP 结构）。已加
> `test_real_office_files_are_binary` 钉住正确行为。

`real.pdf` 是关键证据：**PDF 能正确内联，靠的是 MIME 表那条显式声明，不是嗅探。**

反过来嗅探也能修正扩展名的错：`audio.mod`（音频）被判二进制、
`.plist`（XML 文本）能预览、任何没登记过的文本文件都能预览。

### 结论：三者不是替代关系

| 手段 | 管什么 | 单靠它漏什么 |
|------|--------|-------------|
| 白名单 | 源码/配置 → `text/plain`；**不读文件** | 要维护；但只是"默认值"问题 |
| MIME 表 | 已知格式的**准确类型** | 只认识 23 种 |
| 嗅探 | 前两层没意见时兜底 | 头 512 字节无 NUL 的二进制会显示乱码 |

### 最终实现（用户选的方案 A）

    def resolve_ctype(path):
        if _is_textual(path):          # 1. 白名单（不读文件）
            ctype = MIME.get(ext, TEXT_MIME_DEFAULT)
        elif ext in MIME:              # 2. MIME 表
            ctype = MIME[ext]
        elif not _is_binary(path):     # 3. 嗅探兜底
            ctype = TEXT_MIME_DEFAULT
        else:
            ctype = BINARY_MIME

**白名单继续维护**（用户明确要求）—— 它换来两件事：不读文件的零开销，
以及比嗅探更准的类型（`text/plain` 而不是猜出来的判定）。

### 新增能力与已知代价

新增：任何没登记过的文本文件都能预览（`weird.random`、`notes.xyz`、
文本 `.plist`、无扩展名文本）。

**已知代价（显式记录，不要当 bug 反复"修"）**：前 512 字节无 NUL 的二进制
会被判成文本、显示乱码而不是下载。测试里用 `test_known_tradeoff_*` 把这个
行为**钉住**，并断言这段说明必须留在 `resolve_ctype` 的 docstring 里。

### 验证

- 单元 127 项（+8）：未登记文本可预览、文本 `.plist`、含 NUL 的未登记文件仍下载、
  白名单优先（含 NUL 的 `.py` 仍按文本）、**MIME 表优先（PDF 无 NUL 仍内联）**、
  图片类型不变、已知代价三条、docstring 必须写明代价
- 端到端 274 项（+25）：真实服务上逐项核对第三层行为，
  外加 **17 项基线回归**（`.md/.py/.txt/.json/.xml/.csv/.yaml/.ini/.log/.png/`
  `.gif/.pdf/.svg/.css/.js/Makefile/Dockerfile` 的判定必须一字不变）
- 过程中发现并修掉一处**自己的问题**：我一度加了一条 do-nothing 的
  "基线回归占位"断言（循环体是空的），那等于假测试，已替换为真实断言

---

## 22. 嗅探算法对齐 VS Code：加 NUL 的**对齐**判定

用户问"VS Code 针对 docx 是如何处理"，我去**实测了本机安装的 VS Code**
（`/Applications/Visual Studio Code.app` 的 bundle，19.4 MB）而不是凭记忆。

### 找到的真实实现

    function oze({buffer: s, bytesRead: o}, e, t) {
      let i = rur(s, o), n = !1;
      if (i !== g8 && i !== f8 && s) {
        let r = !0, a = !0, c = !1;
        for (let l = 0; l < o && l < tur; l++) {          // tur = 512
          let u = l % 2 === 1, p = s.readUInt8(l) === 0;
          if (p && (c = !0),
              r && (u && !p || !u && p) && (r = !1),      // NUL 只在奇数位?
              a && (u && p || !u && !p) && (a = !1),      // NUL 只在偶数位?
              p && !r && !a) break;
        }
        c && (r ? i = f8 : a ? g8 : n = !0)               // 对不齐才算二进制
      }
      return {seemsBinary: n, encoding: i}
    }

常量 `tur = 512`、`iur = 512`、`our = 512*8`、`nur = 512*128` —— 与之前那份研究一致。

### 结论：VS Code 不只是"看有没有 NUL"

它还判断 NUL 的**偏移奇偶**：只出现在奇数位 -> UTF-16LE（文本）；只在偶数位 ->
UTF-16BE（文本）；**对不齐才是二进制**。我们原来的实现是"有 NUL 即二进制"，
会把 **ASCII 为主的 UTF-16 文本**判成二进制（每个字符后都跟 NUL）。

已按它的算法重写 `_is_binary`。实测对比：

| 文件 | 旧实现 | 新实现 |
|------|--------|--------|
| ASCII UTF-16LE / BE（无 BOM） | ❌ 二进制 | ✅ **文本** |
| 真 `.docx` / `.xlsx` / `.pptx` / `.odt` | 二进制 | 二进制（不变）|
| 真 PDF | 文本 | 文本（不变，靠 MIME 表内联）|
| PNG / ZIP / 空文件 / GBK | 同 | 同 |

**能力边界（如实记录）**：**CJK 开头的 UTF-16 认不出来** —— `中` 是 `2d 4e`，
高位字节非 NUL，对齐立刻被破坏。VS Code 的实现同样如此（我复刻它的 `oze()`
逐步验证过）。已加测试记录这个边界。

### 顺带纠正我上一轮的一个错误结论

上一轮我把 `.docx`/`.xlsx` 列为"嗅探会误判成文本"的例子，理由是"它们本质是 ZIP"。
**实测不成立**：真实 Office 文件的 ZIP 本地文件头在偏移 4-5 就有 NUL，嗅探判对。
那个"反例"是我自己造的假样本。已在 §21 与该测试里双重更正。

### 验证

- 单元 130 项（+3）：真实 Office/ODF 四种格式 × 两种压缩方式都必须判二进制、
  ASCII UTF-16LE/BE 必须判文本、CJK UTF-16 的边界行为
- 端到端 274 项全绿（`_is_binary` 改动未影响既有判定）
- 压缩版同步重新生成

---

## 23. markdown 目标路径的编码：对齐 VS Code 预览

### 现象

`![x](pics/my%20photo.png)` 渲染成 `src="/pics/my%2520photo.png"` —— `%` 被编成 `%25`，
图片 404（页面本身 200，只有图片子请求挂）。同一个目标写在链接里却是好的：
`[x](pics/my%20photo.md)` → `href="/pics/my%20photo.md"`。

### 找到的真实实现（VS Code 1.141.0 / markdown-it 14.3.2）

不猜，直接读它自己的代码并实测：

| 环节 | 实现 | 结论 |
|------|------|------|
| 解析 | markdown-it `parseLinkDestination` + `normalizeLink`（mdurl） | `%20` 原样保留；`<>` 里的裸空格编成 `%20` |
| 切分 | `Uri.parse`：`^(([^:/?#]+?):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?` | **先切 `?`/`#`，再对每段 percent-decode** |
| 解码 | vscode-uri 的 `ex()` → `decodeURIComponent` | path 解一次：`my%20photo.png` → `my photo.png` |
| 落地 | webview 资源宿主 `decodeURIComponent(g.path)` | 请求 `…/my%20photo.png` → 文件 `my photo.png` |

因此 **`%20` 就是空格**；`%23` 属于文件名（`a%23b.md` 能打开含 `#` 的文件）。

**拖拽插入写的是 `<裸空格>`，不是 `%20`** —— `Qq()`/`oce()` 只要路径里有空白就包成
`<...>`，全程不做百分号编码（`ice()` 用的是已解码的 `fsPath`）。`%20` 只出现在
「粘贴的字符串本身带 %20」与 `uri.toString()` 兜底这两条路上。所以真实文档里
**两种形态都会出现**，而 `<...>` 恰好是我们完全没支持的那种。

### 根因（三个独立缺陷，都在渲染期）

1. **图片目标被编码两次**：`render_image` 把原始目标直接交给 `quote_seg_path`，
   而链接在 `render_link` 里先 `unquote` 过一次 —— 两条路分叉，图片的 `%20` 被当成
   字面 `%` 编成 `%2520`（与 §18.3 的 B3 同类）。
2. **先解码后切分**：链接虽然不双重编码，但它在切 `?`/`#` **之前**就解了码，于是
   `a%23b.md` 被劈成「路径 a + 片段 #b.md」，文件名含 `#`/`?` 的文件永远链不到。
3. **`<>` 目标完全不支持**，三处叠在一起：`parse_inline` 先做 HTML 转义（`<` 变 `&lt;`）、
   `_TAG_RE` 把 `<a b.md>` 当 HTML 标签 stash 掉、`_scan_link_spans` 在 `<>` 内的 `)`
   处提前收尾。附带发现 `_REF_LINK_RE` 带着 `(?<!!)`，**引用式图片从未生效**，
   而 README §4 一直声称支持。

### 修法

- 合并为唯一的 `RenderContext.rewrite_target`，固定顺序 **先切 `?`/`#` → 只解 path 段一次
  → 相对解析 → 编码一次**；链接 / 图片 / 引用式 / 目录索引四条路共用。协议白名单判定仍在
  **解码后**的串上做（B1 的修复点不动）。
- `parse_inline` 在「标签 stash 之前、行内码之后」加 `_ANGLE_DEST_RE` 预处理，把
  `](<a b.png> "t")` 规约成 `](a%20b.png "t")`；内部编码与 mdurl.encode 收敛（保留
  defaultChars 与既有 `%xx`，额外编码圆括号，否则区间扫描会在 `<>` 内的 `)` 处提前收尾）。
  引用式定义 `[r]: <a b.png>` 走同一套编码。
- `_split_link_tail` 增加「尾部是否合法」判定：目标之后只允许空白或一个合法 title，
  否则整条链接不成立、按字面文本输出 —— 裸空格 `[x](a b.md)` 从「截断成 `/a`」变成
  字面文本（CommonMark 与 VS Code 同判）。
- 引用式图片：`_REF_LINK_RE` 第一组捕获 `!`，与链接共用同一条目标重写与协议白名单；
  `_REF_SHORT_RE` 加 `(?<!\])`，免得把完整式引用的后半截再当简写匹配一遍。

### 请求路径解码复核（本次顺带做掉）

这次动的正是编解码语义，所以对**请求侧解码**做了一次针对性复核。结论：**无需改动**。

| 探测 | 结果 |
|------|------|
| `/..%2f<root 外真实文件>`、`/%2e%2e%2f…`、`/../…` | 404 |
| `/%252e%252e%252f…`（双重编码） | 404 |
| `//etc/passwd` | 404 |
| root 内指向 `/etc/passwd` 的符号链接 | 403 |
| `/%00` | 403（`_resolve` 显式拒绝 NUL） |
| `/a+b.png` | 只命中 `a+b.png` —— **没有** `unquote_plus`，`+` 不当空格 |
| `/a%2Bb.png` | 同样命中 `a+b.png`（`+` / 空格 / `%2B` 三者语义不串味） |
| `/a%20b.png` | 命中 `a b.png` |
| `/sub%2fdir%2fx.txt` | 200 —— 编码斜杠只当分隔符（与 VS Code 的 `Uri.parse`+join 同义），`..` 仍在字符串层与 realpath 层被夹紧 |
| `/x%2520y.png` | 命中字面 `x%20y.png`（只解一次） |

Windows 的盘符逃逸（`/%43%3a/Windows/win.ini` → `rel="C:/Windows/win.ini"`）也走查了一遍：
`os.path.join(root, "C:\\Windows\\win.ini")` 在 Windows 上会丢掉 root，但随后的
`_inside()` 字符串夹紧立刻否掉（404），不依赖 realpath 层。**这类回归以后有测试盯着**：
B10 的断言里包含「渲染结果里没有 `%25`」，谁把解码改成 `unquote_plus` 或再加一次编码都会变红。

### 验证

- 单元 **153 项**（138 旧 + 15 新，旧期望值一行未改）：新增 `TestTargetEncoding`
  （`%20` / `%2520` / `%23` / `%3F` / `%25` / `<>` / 裸空格 / `+` / query / fragment，
  以及「链接与图片同一目标必须逐字节相同」）与 `TestReferenceImages`
  （完整式 / 折叠式 / 简写 / 尖括号定义 / title / 协议被拒仍按原文）
- 端到端 **289 项**（284 旧 + 5 新，旧期望值一行未改）：B10 真 HTTP 往返
  （`mktemp -d` 造 `带 空格.png`、`img dir/nested pic.png`、`a#b.md`、`x%20y.png`，
  断言三种写法渲染出同一个 `src`、逐个 200、页面里不出现 `%25`），B11 断言示例页
  真的用两种写法引用了带空格图片
- 示例语料新增 `docs/media/带 空格.png`（180×56 真 PNG），`guide/install.md` 用尖括号与
  `%20` 各引用一次 —— 该页已被既有断链巡检覆盖
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

### 一处有意偏离 VS Code

它的相对路径实际解码**两次**（`Uri.parse` 一次、资源宿主一次），因此文件名里真含 `%20`
的文件在 VS Code 里用相对路径**打不开**。我们只解一次：`a%2520b.png` 命中字面
`a%20b.png`。跟了它就是丢能力，所以不跟 —— 理由与其余边角记在
[`docs/adr/0001`](docs/adr/0001-markdown-target-encoding.md) 与 README §9。

---

## 24. 裸 URL 点击化（GFM autolink literal）

**需求**：正文里手写的 `https://…` 要能点，不必先写成 `[](…)` 或 `<>`。

**改前实测**（`render_markdown("访问 https://example.com/a 看看。")`）：

```
<p>访问 https://example.com/a 看看。</p>          ← 纯文本，点不了
```

`_AUTOLINK_RE` 只匹配尖括号形式 `<https://…>`，裸 URL 在正文里没有任何处理器。
（`?raw=1` 源码视图按设计就是把每一行当纯文本发，所以那里**不会**有链接，不是缺陷。）

### 落点：卡在「实体之前、引用式展开之前」

四步顺序都试过，只有现在这个落点同时满足四个约束（`parse_inline` 内有同款注释）：

| 约束 | 违反后的现象 |
|------|--------------|
| 在 `html.escape` **之前** | 放之后则 `?a=1&b=2` 被再转义一次，href 变成 `&amp;amp;` |
| 在 `_ENTITY_RE` **之前** | 放之后则 `&` 已成 token，URL 被截断在 `&` |
| 在 `_REF_DEF_LINK` **之前** | 放之后则引用式图片定义已在 `<img src="…">` 内部，替换会把 `src` 写成 `<a href=…>` |
| 在 `_AUTOLINK_RE` **之后** | 放之前则尖括号自动链接会被重复处理 |

**实测过的两个坏落点**（都真实产出过坏 HTML，记录以免回退）：

```
# 落点错误 1（在引用式展开之后）：src 被打坏
![a][r] + [r]: https://e.com/p.png
  → <img src="<a href="https://e.com/p.png" rel="noreferrer noopener">https://e.com/p.png</a>" alt="a">

# 落点错误 2（在 html.escape 之后）：双重转义
访问 https://e.com/x?a=1&b=2 结束
  → href="https://e.com/x?a=1&amp;amp;b=2"
```

### 边界规则（GFM autolink literal）

| 输入 | 输出 |
|------|------|
| `见 https://example.com/a 说明` | 可点，`href="https://example.com/a"` |
| `https://example.com/a. 结束` | 句号归句子 |
| `https://en.wikipedia.org/wiki/A_(b)` | 括号配平 -> 整个 URL |
| `https://en.wikipedia.org/wiki/A_(b))` | 多出的 `)` 归句子 |
| `(见 https://example.com/a)` | 收尾 `)` 归句子 |
| `https://e.com/x?a=1&b=2` | `href="…?a=1&amp;b=2"`（只转义一次） |
| `https://e.com/a&copy;` | 完整实体保留，页面不漏出 `&copy` |
| `` `https://e.com/a` `` / 围栏块 | 保持 `<code>`，不链接化 |
| `[x](https://e.com/a)` | 只有外层一个 `<a>`（目标是链接目标） |
| `[见 https://e.com/a 说明](other.md)` | 只有外层一个 `<a>`（HTML 不允许 `<a>` 嵌 `<a>`） |
| `www.example.com` / `a@b.com` | 不链接化 |

### 刻意偏离 GFM：全角句末标点

GFM 只认半角标点，于是中文文档里 `见 https://e.com/a。结束` 会把「。结束」整段吃进
链接。中文技术文档里 URL 后跟全角句号是常态，所以把 `。，、；：！？` 也算句末标点。

**没有连带损失**：URL 里的汉字照旧保留（`/wiki/中文条目` 完整命中）。实现上只有
「末尾汉字串的左边紧跟全角句末标点」才判为句子尾巴，`/` 开头的不在其列。

### 顺带修掉的历史缺陷

`<mailto:a@b.com>` 曾产出 `href="mailto:mailto:a@b.com"` 死链：`_autolink_sub` 见到
`@` 就无条件补 `mailto:`，而 `_AUTOLINK_RE` 只接受 `mailto://`，于是 `mailto:` 前缀
被当成正文又补了一次。现在补之前先看有没有 scheme。

### 安全

属性注入用例逐个走查（`href`/`src` 值里不得出现未转义引号）：`https://e.com/a"onmouseover="x`、
`https://e.com/a"&gt;`、`https://e.com/a<script>alert(1)</script>` 等全部只产出
转义后的属性值；`<` 会终止匹配，所以 `<script>` 落在链接外并被转义。
协议白名单（`safe_href`）对自动链接同样生效。

### 验证

- 单元 **173 项**（153 旧 + 20 新，旧期望值一行未改）：新增 `TestAutolinkLiteral`，
  覆盖正例、五种半角句末标点、全角句末标点、括号配平三例、引号、查询串单次转义、
  尾部实体、行内码/围栏块不链接化、标签不嵌套、图片 alt、引用式图片 `src` 不被写坏、
  紧跟 markdown 链接的裸 URL、标题与表格单元格、无 `://` 的快路径
- 端到端 **309 项**（289 旧 + 20 新）：`mktemp -d` 造 `bare.md` 真 HTTP 往返，
  断言可点、查询串只转义一次、括号配平、全角标点归句子、中文 URL 保留、
  行内码与围栏块内无 `<a>`、尖括号自动链接仍在、标签里不嵌套 `<a>`；
  另有 7 项盯住示例页（`docs/index.md` 的「裸 URL 自动链接」小节）真的渲染出可点链接
- **示例语料内建演示**：`docs/index.md` 新增「裸 URL 自动链接」小节，把可点、
  句末标点（半角 + 全角）、括号配平、行内码不链接化、标签不嵌套五种行为
  用真实文本演示一遍 —— 它同时落进「站内链接全部可解析」的断链巡检
- **全库巡检**：渲染全部 12 个 `.md`，产出 HTML 里"可见文本形态的 http(s) URL"
  剩余 **0 个**（`docs/guide/code-blocks.md` 的 `http://127.0.0.1:8000/` 在 4 空格
  缩进块里、`README.md:7` 在围栏块里，都按代码显示，属预期）
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 25. 标签渲染的三个出口缺陷：alt 属性注入、裸 HTML 反转义、引用式属性被再解析

**发现方式**：做「放大视图显示 alt」时顺手量了一下 `alt` 到底装了什么 —— 发现它是
**活的 XSS**。顺着同一个出口又挖出另外两个同族缺陷。三处都在「标签渲染」这一个环节：
**没有区分「纯文本消费方」与「标记内容消费方」**。

### 现象（三条都能在 Chrome 里真的执行）

```
![a" onerror="alert(1)](p.png)
  -> <img src="/docs/p.png" alt="a" onerror="alert(1)">         ← 属性注入（行内式）

![a" onerror="alert(1)][r]   /   ![a" onerror="alert(1)]
  -> 同上                                                       ← 引用式、简写式一样中招

[<script>alert(1)</script>](u.md)
  -> <a href="/docs/u.md"><script>alert(1)</script></a>         ← 裸 HTML 变成真标记

[x][r]   +   [r]: _x_.png
  -> <a href="/docs/<em>x</em>.png">x</a>                       ← href 被强调解析插了标签
![i][r]  +   [r]: _x_.png
  -> <img src="/docs/<em>x</em>.png" alt="i">                   ← src 同样坏掉
![**粗**][r]
  -> <img src="/docs/p.png" alt="<strong>粗</strong>">          ← alt 又长出标记
```

README 与 SELFTEST §3.2 都写着「裸 HTML 全部转义」—— 在**段落文本**里成立，在
**链接标签**里不成立。

### 根因（三处，同一个病灶的三种形态）

1. **alt 是属性值，却塞进了标记内容。** `render_image` / `_ref_image_html` 把
   `render_label()` 的返回值（可能含 `<strong>`、嵌套时甚至含我们生成的 `<img>`）
   直接写进 `alt="…"`；而这一步之前只有 `html.escape(text, quote=False)` ——
   `quote=False` 不转义引号，于是一个手写的 `"` 就能闭合属性。
   （`title` 两条路都用了 `quote=True`，所以它是安全的：同一个函数里两种写法并存。）
2. **`read_tokens` 被用在了错的消费方向。** 它是给「取出来 -> 自己再转义一次」的
   消费方（URL / title / alt）设计的，会把文本 token 反转义成原始字符；
   而 `render_label` 需要的是**标记内容**。源文本里的 `<script>` 早已被 `_TAG_RE`
   转义成 `&lt;script&gt;` 存进 token，被它反转义回来就成了真标签。
3. **引用式展开把标记字面写回了文本。** `_REF_DEF_LINK` 在 `html.escape` 之后把
   `<a>`/`<img>` 字符串直接拼进文本流，后面的 `parse_emphasis` 于是把它们当 markdown
   又解析了一遍 —— 属性值里的 `_x_`、`**粗**` 都成了 `<em>`/`<strong>`。
   行内式从来没有这个问题：它的 `<a>`/`<img>` 一直是 token，后处理碰不到。

### 修法

| 出口 | 修法 |
|------|------|
| `alt` | 新增 `_alt_text()`：把标签的渲染结果拍成**纯文本**（先让嵌套图片贡献自己的 alt，再剥标签、解实体），调用方再 `html.escape(quote=True)`。两条路共用 |
| 标记内容 | 新增 `read_tokens_markup()`：与 `read_tokens` 并列的**第二种读法**，原样取出 token、不反转义；`render_label` 改用它。两个消费方向不再合并成同一个函数 |
| 引用式 | `_REF_DEF_LINK` / `_shortcut_ref` 收 `render_label` + `stash` 两个参数：标签内容走行内解析器，产出的 HTML 立刻变成 token；调用点移到嵌套函数定义之后、`scan_inline` 之前 |

副作用是两条路**收敛**了：引用式图片的 alt 现在也是行内解析后的纯文本
（`![**粗**][r]` -> `alt="粗"`，与 markdown-it / VS Code 一致），README §9 里那条
「引用式图片的 alt 不跑行内解析」的偏差随之作废 —— 它不是设计，是这个 bug 的表象。

### 验证

- 单元 **187 项**（173 旧 + 14 新，**旧期望值一行未改**）：`TestLinkSafety` 的载荷
  清单加 6 条（三条 alt 注入、三条标签裸 HTML），新增
  `test_alt_cannot_escape_its_attribute`、`test_raw_html_in_label_stays_escaped`、
  `test_image_alt_is_plain_text`、`test_reference_attributes_are_not_reparsed_as_markdown`
- 端到端 **320 项**：断链巡检、示例语料、`?raw=1`、搜索等全部照旧通过
- `TestLinkSafety.test_no_unexpected_attributes_anywhere` 是这条防线的判据：
  渲染出的每个标签的属性名必须落在白名单内（`onerror` 这类直接判失败）

### 一处观察到、本次**不**修的既有缺陷

`[![i][r]](u.md)`（引用式图片嵌在引用式链接里）本来就产出坏标记，HEAD 上是
`<a href="/docs/p.png"><img src="/docs/u.md" alt="i</a>">` —— `_REF_LINK_RE` 用
`[^\]]*` 抓标签，会从外层的 `[` 开始匹配、把内层 `[i]` 当标签内容。本次改动后形态
变了（少了凭空造出的 `src`）但**仍是坏的**，属于同一个正则的老问题，未纳入本次范围。

## 26. 图片放大：服务端包裹链接 + 原生 `<dialog>` 遮罩

**需求**：正文图片点一下能放大看。禁用 JS 时也不能退化成「点了没反应」。

**形态**（都是定下来的，理由见 [`docs/adr/0002`](docs/adr/0002-image-zoom.md)）：
点开是一层遮罩、原图按视口缩放居中；Esc / 点遮罩空白 / 右上角 × 关闭；遮罩里显示
图片的 `alt` 作为说明。**不做**相册、滚轮缩放、双指手势、1:1 切换。

### 服务端：在 `parse_inline` 出口做一次锚点深度扫描

图片有两条产出路径（行内式在 `parse_inline` 内部、引用式在行内解析**之前**），所以
「生成 `<img>` 时顺手包一层」对引用式行不通 —— 那时外层链接还没解析，遇到
`[![x][r]](u)` 会产出嵌套 `<a>`，浏览器会把外层链接撕成两半。

落点改在 `parse_inline` 的**出口**：此刻源文本已全部转义，输出里任何
`<a` / `</a>` / `<img` 都只可能是我们自己生成的，于是可以线性地数锚点深度，
只包深度为 0 的图片。规则因此与上下文无关（标题、表格、列表、引用块自动覆盖），
徽章图片自动排除。

包裹链接的 `href` **逐字节复用** `<img>` 已有的 `src`：那条「只解码一次、只编码一次」
的管线不许被走第二遍（有专门断言钉住 href 与 src 同源）。

### 样式与脚本

- `.zoom{cursor:zoom-in}` + 悬停 `box-shadow` 描边（用 box-shadow 而不是 border，
  否则悬停时整段文字会抖一下）
- `dialog.zoomdlg` 只补视觉：top layer、`::backdrop`、Esc、背景 inert、隐式
  `aria-modal` 都是 `showModal()` 白送的；`html.zoomlock{overflow:hidden;
  scrollbar-gutter:stable}` 负责锁滚动且不让滚动条槽位消失
- 入场动画在 `@media (prefers-reduced-motion: no-preference)` 内，用
  `@starting-style` + `transition: display .15s allow-discrete`（2024 起 Baseline）
- 脚本并入现有 `COPY_JS`（与复制按钮同一条注入路径，仍然每页内联）。**遮罩、关闭
  按钮全部运行时创建**：禁 JS 的基线上不会出现点不动的死元素（有断言）

### 三处只有真浏览器才暴露的细节

| 细节 | 事实 | 处理 |
|------|------|------|
| 焦点归还 | `<img>` **默认不可聚焦**，`img.focus()` 是空操作（实测 `activeElement` 停在 `body`） | 记的是**包裹链接**，关闭时把焦点还给链接（探针实测 `focus_returned_to_link: true`） |
| 修饰键点击 | `preventDefault()` 会连同「Cmd/Ctrl+点击新标签打开」一起吃掉 —— 而包裹链接同时是原图的唯一出口 | `ev.button !== 0 || metaKey/ctrlKey/shiftKey/altKey` 时直接放行（探针实测未被 preventDefault、也没弹遮罩） |
| 缩放基准 | 图片按视口缩放要跟 `vh` 在移动端的地址栏问题上打交道 | 同时写 `calc(100vh - 5rem)` 与 `calc(100dvh - 5rem)`，后者覆盖前者 |

### 浏览器实测（Chrome headless）

本机 `--dump-dom` 会一直挂着不退出（`--headless` 与 `--headless=new` 都试过），
`--screenshot` 正常。所以探针把逐条状态渲染进页面再截图取回：
[`tools/zoom-probe.html`](tools/zoom-probe.html)（同源 iframe + 合成点击；用法写在文件头）。

在 `docs/preview/index.md`（新嵌入的 1600×900 大图）上跑一遍的观察值：

```
wrapped_count: 1            lazy_dialog: true        href_eq_src: true
href: /preview/media/sample-large.png                img_natural: 1600x900
modifier_click_not_prevented: true                   modifier_click_no_dialog: true
dialog_open: true           is_modal: true           big_src: /preview/media/sample-large.png
caption: "1600×900 网格大图（点击放大）"               labelledby: zoomcap    aria_label: null
zoomlock: true              focus_on_close: true     backdrop: rgba(0, 0, 0, 0.78)
fitted: 782x440 viewport=1200x520 natural=1600x900   fits_viewport: true
closed_by_button: true      unlocked: true           focus_returned_to_link: true
closed_by_backdrop: true    still_one_dialog: 1      active_element_after_close: A.zoom
```

`is_modal: true` 是「背景 inert + 进 top layer」的直接证据；`fitted` 那一行证明
1600×900 的图确实被压到视口内（正文里它被列宽缩成 860×484，放大视图给到 782×440 于
1200×520 视口 → 高度受限，见下）；`backdrop` 证明遮罩来自 `::backdrop` 而不是自绘 div。

真实页面上的放大视图（`docs/preview/index.md`，遮罩 + 按视口缩放 + alt 说明 + 右上角关闭键）：

![放大视图截图](docs/media/screenshot-zoom.png)

### 示例语料与测试

- **大样例图**：`docs/preview/media/sample-large.png`，1600×900 带网格（`write_png`
  加了矩形与网格参数）。单色方块看不出「缩过」，网格才看得出。端到端断言它的
  `Content-Type`、PNG 魔数，以及 IHDR 里的宽高字节（`0000064000000384`）
- 单元 **187 项**（173 旧 + 14 新）：新增 `TestImageZoom`（10 项）覆盖行内式/引用式
  包裹、href 与 src 逐字节同源、徽章不嵌套、标题/表格/列表/引用块、行内码与围栏块
  不包裹、被拒协议不产出包裹、title 留在 img 上、每图只包一次、基线里没有写死的
  `<dialog>`；另有 2 条旧断言的期望值随之更新（`<a ` 计数、`assertNotIn("<a")`）
- 端到端 **320 项**（309 旧 + 11 新）：包裹形态、href 与 src 同源、脚本与样式已内联、
  基线正文里没有写死的 dialog、示例页大图也包了链接、大图尺寸
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 27. 关闭按钮钉在视口右上角：抢走"点空白处"的点击，并盖住页面上的图片名

**现象**（用户报告）：
- 点右上角的关闭按钮 / Esc / 点空白处都能退出，但"右上角的关闭按钮那里会显示图片的名称"；
- 用 Esc 或点空白处退出时，右上角那颗小的关闭按钮"会被触发"。

**探针实测**（`tools/zoom-probe.html` 的同源 iframe + 合成点击；`window 1200x800`，
打开 `guide/install.md` 的 240×72 logo）：

| 判据 | 修复前 | 修复后 |
|------|--------|--------|
| 按钮矩形 | `{l:1154,t:10,r:1188,b:44}` —— 贴**视口**右上角 | `{l:678,t:171.5,r:712,b:205.5}` —— 在 dialog 盒内 |
| `按钮在 dialog 内` | **false** | **true** |
| `右上角命中的是按钮` | **true**（点"空白处"点的其实是按钮） | **false**（命中 dialog → 走 backdrop 关闭） |
| `× 的字号` | 13.3333px | 22px |

**根因（三条，都在样式里）**：

1. `.zoomclose` 写成 `position:fixed; top:10px; right:12px` —— 它属于**视口**，不属于图片。
   后果一是它永远飘在视口右上角那块**页面内容**上方：那里若是图片，或**裂图时浏览器
   画出来的 alt 文字（通常就是文件名）**，看上去就成了"关闭按钮上显示图片名称"
   （裂图那条用 `docs/preview/media/sample-large.png` 之外的假路径实测过：
   浏览器把 alt 画在图片位置上，dialog 里还会再重复一遍 caption）。
   后果二是那一小块"空白处"的点击命中的是按钮而不是 backdrop —— "点空白处关闭"
   实际是按钮在关闭，也就是"关闭按钮被触发"。
2. `font:20px/1 inherit` 是**非法声明**（`inherit` 不能出现在简写里），整条被丢弃，
   × 退回 UA 的 13.3px，又小又难看清。
3. 按钮一打开就命中 `:focus-visible`（探针：`打开即 :focus-visible: true`）——
   `showModal()` 会把焦点送给 dialog 里第一个可聚焦元素，也就是这颗按钮
   （去掉显式 `autofocus` 也一样，实测 activeElement 仍是它）。这条**不是缺陷**：
   键盘用户的焦点必须落在 modal 内。所以只把 outline 写成白色 + offset，
   让它看起来是"焦点"而不是默认控件的激活态。

**修法**：

- `.zoomclose` 改 `position:absolute; top:8px; right:8px`，并把 modal 定位显式写出来
  （`dialog.zoomdlg[open]{position:fixed;inset:0;margin:auto}`）—— absolute 的包含块
  因此就是 dialog 盒，按钮永远贴在**图片的右上角**，不再飘在页面内容/空白上方。
- 字号改 longhand（`font-size:22px;line-height:1;font-family:inherit`）。
- 删掉多余的 `btn.autofocus`（`showModal()` 自己就会把焦点送进来），
  并给 `:focus-visible` 写一圈白 outline。

**验证**：

- 探针新增三条几何/命中断言（`close_inside_dialog` / `close_font_size` /
  `topright_hit_is_close_btn`），修复前后各跑一遍，见上表
  （**§30 后 `close_font_size` 已换成 `close_icon` / `close_icon_centred`**：× 不再
  是字体字形，字号这条判据失去意义）
- 单元 **187 -> 189 项**：`test_close_button_is_anchored_to_the_dialog`（CSS 里必须是
  `position:absolute`，且 dialog 自己写明 modal 定位）、
  `test_close_button_font_is_not_an_invalid_shorthand`（不能有那条非法简写 ——
  注释里会引用它，所以先剥掉 CSS 注释再断言；**§30 后改写为
  `test_close_icon_is_a_centred_svg_not_a_font_glyph`**）
- 端到端 **320 -> 321 项**：新增「关闭按钮贴在图片上」
- 截图重新生成 [`docs/media/screenshot-zoom.png`](docs/media/screenshot-zoom.png)
  （按钮已贴在图片右上角，带那圈白色焦点环）
  （**§31 后再次重新生成**：初始焦点不再落在按钮上，白环只在按 Tab 走到它时出现）
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 28. 关闭动画把遮罩重排成一行：× 飞到视口右缘、图片名挤成右侧一列

**现象**（用户报告）：图片放大预览后，**每次关闭**都能看到"右上角冒出那颗关闭按钮，
同时还显示出图片名"。

§27 修的是**稳定态**里按钮钉在视口右上角；这一条是**关闭过渡期**里同一个症状的漏网
形态 —— 打开时一切正常，只有点掉（× / Esc / 点空白）那一瞬间露出来。

**探针实测**（[`tools/zoom-probe.html`](tools/zoom-probe.html) 的同源 iframe + 合成点击；
`window 1200x520`，`docs/preview/index.md` 的 1600×900 大图）。注意**不能**加
`--force-prefers-reduced-motion`：那条会连同 `transition:display` 一起关掉，正好把本
缺陷藏起来（文档里 §27 的跑法带了它，所以当时没照出这一帧）：

| 判据（close 的首帧） | 修复前 | 修复后 |
|---|---|---|
| `flexDirection / alignItems` | `row / normal` | `column / center` |
| `close_btn_pos_stable`（× 盒位置不动） | **false**（`l:1138 -> 1185`） | **true** |
| `close_caption_pos_stable`（caption 不重排） | **false**（`l:495,w:211 -> l:1160,w:67`） | **true** |

**根因**：`display:flex;flex-direction:column;align-items:center;gap:10px` 全写在
`dialog.zoomdlg[open]` 里。`close()` 会**立刻**摘掉 `[open]`，而
`transition:display .15s allow-discrete` 还要把盒子显示约半程（离散属性到过渡中点才翻转）。
这半程里凡是留在 `[open]` 中的属性都退回初始值 —— `flex-direction:row`、
`align-items:normal` —— 三个子元素于是按行排开：图片在左，caption 被挤成右侧一条窄列，
× 被挪到盒子最右缘（也就是视口右侧）。图片自身的 `transform:scale(.97)` 是出场动画、
**不参与布局**，所以动的是盒位置 —— 肉眼看到的就是"一关就冒出右上角的关闭按钮 + 图片名"。

**修法**：定位与排版挪进**基础规则**，`[open]` 只留 `display`：

```css
dialog.zoomdlg{…;position:fixed;inset:0;margin:auto;
  flex-direction:column;align-items:center;gap:10px;…}
dialog.zoomdlg[open]{display:flex}
```

基础规则里的 `position`/`inset`/`margin` 与 flex 属性在关闭态（`display:none`）没有副作用，
却让几何不随可见性开关变化。`display` 仍留给 `[open]`，UA 的
`dialog:not([open]){display:none}` 才管得住隐藏（写进基础规则会让遮罩常驻）。
（§29 把退场改成瞬时之后，这条搬家成了**结构保险** —— 将来谁再加回出场过渡也不会重演。）

**验证**：

- 探针新增三条"关闭首帧"断言（`close_keeps_column` / `close_btn_pos_stable` /
  `close_caption_pos_stable`），修复前后各跑一遍，见上表
  （**§29 后已替换**：退场改成瞬时，那三条几何断言不再可能为假，探针改为断言
  `close_is_instant`；本条的结构约束由单元测试继续钉着）
- 单元 **189 -> 190 项**：新增 `test_overlay_layout_survives_the_close_animation`
  （基础规则必须含定位与 flex 排版，`[open]` 里不许再出现它们），
  并改写 `test_close_button_is_anchored_to_the_dialog`（modal 定位的落点随之下移到基础规则）
- 端到端 **321 -> 324 项**：新增「遮罩定位在基础规则 / 遮罩排版在基础规则 /
  `[open]` 只切 display」（先把文档页压掉空白再比对）
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 29. 退场过渡让 × 与 caption 原地停留：关闭必须瞬时

**现象**（用户报告）："关闭图片后，关闭按钮会停留在原位置很短的时间，不符合要求。"
点掉遮罩后图片与遮罩在淡出，但那颗 × 与图片名却**原地原样亮着**，直到
`display:none` 才一起消失。§28 修的是"退场期间排版被打乱"，这一条是同一个出场过渡的
另一半 —— 本就不该有出场过渡。

**探针实测**（[`tools/zoom-probe.html`](tools/zoom-probe.html)；`window 1200x520`，
`docs/preview/index.md` 的 1600×900 大图；**必须去掉** `--force-prefers-reduced-motion`，
否则 `transition` 与 `@starting-style` 整段被关掉，两个判据都失去意义）：

| 判据 | 修复前 | 修复后 |
|---|---|---|
| `close_is_instant`（close 首帧 display 已是 `none`、按钮盒子已归零） | **false** | **true** |
| `entrance_animates`（打开首帧图片 opacity ≠ 1） | true | **true**（入场必须保住） |
| 关闭后 0 / 20 / 50 / 100ms 的 `display` | `flex`，图片 opacity `1 → 1 → 0.65 → 0.26` | 一律 `none` |

时间线（Chromium 实测，150ms 过渡）：点关闭后图片与遮罩一路淡出，而 × 全程
`btnVisible: true`、位置不动 —— 因为它没有 opacity 过渡，只能等 ~150ms 时
`display` 翻成 `none` 才"啪"地消失。

**根因**：`dialog.zoomdlg{transition:display .15s allow-discrete,overlay .15s allow-discrete}`
把**退场**也做成了 150ms 过渡：`allow-discrete` 让 `display:none` 推迟到过渡中点，
元素因此多渲染约半程。`img` / `::backdrop` 有 opacity 过渡、`×` 与 `caption` 没有 ——
看上去就是"关掉之后关闭按钮还停留一下"。ADR 0002 写的本来就只有**入场**动画。

**修法**：只做入场动画，退场瞬时。删掉 dialog 上那条 `transition:display … allow-discrete`
与 `overlay …`，`::backdrop` 的过渡只留 `opacity`；入场那条 `@starting-style` 路径原样保留：

```css
@media (prefers-reduced-motion: no-preference){
  dialog.zoomdlg img{opacity:0;transform:scale(.97);
    transition:opacity .15s ease,transform .15s ease}
  dialog.zoomdlg[open] img{opacity:1;transform:none}
  @starting-style{dialog.zoomdlg[open] img{opacity:0;transform:scale(.97)}}
  dialog.zoomdlg::backdrop{opacity:0;transition:opacity .15s ease}
  …
}
```

`display` 不写过渡也照样有入场动画：`@starting-style` 在元素**首次渲染**时提供起始值；
摘掉 `[open]` 则立刻 `display:none`（实测打开首帧 `opacity:0`、逐帧升到 1）。

**验证**：

- 探针把 §28 的三条关闭几何断言换成 `close_is_instant`，并新增 `entrance_animates`
  —— 防止"为了瞬时关闭把入场动画一起删掉"，修复前后各跑一遍，见上表
- 单元 **190 -> 191 项**：`test_close_is_instant_not_an_exit_animation`（全文不许出现
  `allow-discrete` / `transition:display`，入场三件套一件不能少）；§28 那条改为结构保险
- 端到端 **324 -> 328 项**：新增「退场不做过渡」两条（`allow-discrete`、`transition:display`）
  与「入场动画仍在」两条（图片 `@starting-style`、`::backdrop` 只过渡 opacity）
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 30. 关闭按钮的 × 不居中：改用几何绘制的 SVG 图标

**现象**（用户报告）："关闭按钮的图标有问题，❌不居中。"

**实测**（Chromium，`docs/preview/index.md`；把按钮那 34×34 剪下来放大 12 倍量像素，
并以按钮盒中心为原点）：

| 判据 | 字体字形 U+00D7 | 内联 SVG |
|---|---|---|
| 墨迹盒（CSS px） | 10.08 × 10.50 | 10.33 × 10.33 |
| 墨迹中心相对按钮中心 | (0, **+1.46**) —— 偏低 | (-0.04, -0.29)（半像素栅格/抗锯齿误差） |
| 探针 `close_icon_centred` / `close_icon` | — | **true** / `24x24 offset=0,0` |

**根因**：字形 U+00D7 的墨迹在 em 盒里**本来就不居中** —— 它画在数学轴附近，墨迹中心
比 em 中心低一截；按钮能把行盒（≈ em 盒）居中，却管不到字形自己偏。而且各字体偏得
还不一样，canvas `measureText` 量 22px 下需要的抬升量：

```
macOS 系统字体 2.31px   system-ui 1.74px   Helvetica 1.89px   serif 1.30px
Menlo 0.61px            Times 0.19px       Arial -0.28px      Hiragino Sans GB -0.30px
```

跨度超过 2.5px —— 写死任何 `transform` / `padding` 校正值都必然在别的平台偏回去。
第 27 节那条"字号必须 longhand 写 22px"的规格只在字号层面兜底（字形别退回 UA 的 13px），
管不了基线与 em 盒的错位。

**修法**：× 改成 `COPY_JS` 里**现画的内联 SVG**（两条对角线），按钮只负责把它摆正 ——
`display:flex;align-items:center;justify-content:center`，图标固定 `24×24`：

```css
dialog.zoomdlg .zoomclose{…;display:flex;align-items:center;justify-content:center}
dialog.zoomdlg .zoomclose svg{display:block;width:24px;height:24px}
```

```js
var NS = "http://www.w3.org/2000/svg";
var icon = document.createElementNS(NS, "svg"), line = document.createElementNS(NS, "path");
icon.setAttribute("viewBox", "0 0 24 24");
icon.setAttribute("aria-hidden", "true");     // 可访问名由按钮的 aria-label 给
line.setAttribute("d", "M7.5 7.5 16.5 16.5M16.5 7.5 7.5 16.5");
line.setAttribute("fill", "none");
line.setAttribute("stroke", "currentColor");  // 强制色彩模式下图标也不会被压没
line.setAttribute("stroke-width", "2");
```

两条对角线对称于 viewBox 中心（墨迹盒 ≈ 10.4px，与原字形 10.1×10.5 相仿），按钮 flex
居中即可，与字体度量彻底脱钩 —— 换字体、换平台都不动。按钮里不再有文字，可访问名
一直由 `aria-label="关闭放大视图"` 提供。

**验证**：

- 探针新增 `close_icon` / `close_icon_centred`（量 svg 盒中心相对按钮中心的偏移，
  必须 < 0.5px），并删掉只对字形有意义的 `close_font_size`
- 单元 **191 项（不增）**：`test_close_button_font_is_not_an_invalid_shorthand` 改写为
  `test_close_icon_is_a_centred_svg_not_a_font_glyph`（CSS 必须 flex 居中 + `svg{24×24}`；
  `COPY_JS` 必须画 SVG、`fill:none`、`stroke:currentColor`，且不再往按钮里写字形文本）
- 端到端 **328 -> 332 项**：新增「关闭图标由 SVG 绘制 / 图标描边用 currentColor /
  关闭按钮 flex 居中 / 关闭图标 24×24」
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 31. Esc 关过之后再打开，右上角的 × 带着白边：初始焦点不该落在按钮上

**现象**（用户报告）："图片放大后，使用 ESC 关闭，再次打开后，右上角的关闭按钮竟然是有
白边的选中状态。"

**实测**（Chromium + CDP 派发**真实**鼠标/键盘事件，`docs/preview/index.md`）：

| 步骤 | 修复前 | 修复后 |
|---|---|---|
| 鼠标点图打开 | `activeElement=BUTTON.zoomclose`，无白边 | `activeElement=DIALOG.zoomdlg`，无白边 |
| Esc 关闭 | `A.zoom`（焦点还给包裹链接） | `A.zoom` |
| **再点图打开** | `BUTTON.zoomclose`，**`:focus-visible` 命中 → 白边** | `DIALOG.zoomdlg`，**无白边** |
| 再按 Tab | 焦点溜到 `BODY`（遮罩里没有别的可聚焦元素） | 焦点进 `BUTTON.zoomclose`，白环出现（键盘用户该看见的） |

**根因**：`showModal()` 的 dialog focusing steps 会把焦点送给 dialog 里第一个可聚焦
元素 —— 那颗 ×。而 `:focus-visible` 的判定看的是**最近一次交互是不是键盘**：刚用 Esc
关过，模态就是键盘，于是这次**程序化**聚焦被算作键盘聚焦，CSS 里那圈
`outline:2px solid #fff` 就画出来了。第一次用鼠标点开时模态还是指针，所以看不到 ——
这也是为什么它只在"Esc 关过之后再打开"这条路径上暴露。

**修法**：给遮罩 `tabindex="-1"`，并在 `showModal()` 之后把焦点收回遮罩自己：

```js
d.tabIndex = -1;      // buildZoom()：遮罩作焦点落脚点，但不进 Tab 顺序
…
zoom.showModal();
zoom.focus();         // "打开"这个动作本身不画任何环
```

```css
dialog.zoomdlg:focus{outline:none}   /* 遮罩是容器不是控件，别套一圈焦点框 */
```

焦点仍在 modal 内、Tab 第一步照样落到 × 上并显示键盘焦点环 —— 没有拿无障碍换观感；
而且初始化时屏幕阅读器宣布的是这个 dialog 而不是那颗按钮，读起来更准确。修复前 Tab
反而会从 × 溜到 `BODY`，这一并理顺了。

**验证**：

- 探针把 `focus_on_close`（旧代码里它其实是在断言"焦点落在 × 上"）换成
  `open_focus_is_dialog` / `open_dialog_outline` / `dlg_tabindex`；上表那两步"Esc 关过
  再打开"的真实键鼠路径由 CDP 脚本跑出来
- 单元 **191 -> 192 项**：`test_open_focus_lands_on_the_dialog_not_the_button`
  （`tabIndex = -1`；`zoom.focus()` 必须排在 `zoom.showModal()` **之后**，否则会被自动
  聚焦盖回去；遮罩自身 `outline:none`；同时钉住 × 的 `:focus-visible` 白环不许被删）
- 端到端 **332 -> 336 项**：新增「遮罩可作焦点落脚点 / 打开后焦点收回遮罩 /
  遮罩自身不画焦点环」，另加一条反向断言「键盘焦点环没被删掉」
- 截图 [`docs/media/screenshot-zoom.png`](docs/media/screenshot-zoom.png) 重新生成 ——
  旧图里那颗 × 正带着白圈，而现在是"打开不画环"，同框同尺寸（1200×820）
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 32. 新增「回到顶部」：固定在右下角，目录页 / 预览页 / 源码视图都有

**需求**（两条，后者是补充）："增加一个回到顶部的按钮的功能，固定在右下角，点击后可以
回到页面的顶部。主要针对主页面，点击文件跳转的预览不处理。" → 随后："markdown 的预览
和源码页也加上这个功能吧。"

**形态**：**目录页**（`/`、`/guide/` 这类列表页）、**Markdown 预览页**、**源码视图**
（`?raw=1`）右下角固定一颗 40×40 的圆形 ↑ 按钮，距视口右/下各 20px；点一下回到页面
顶部。**搜索页与错误页不装**。动效听系统的：`prefers-reduced-motion: reduce` 时直接跳，
不做平滑滚动。

**服务端只留一个标记，按钮由脚本创建**：`_page()` 多了 `to_top=False`，为真时给
`<body>` 加 `data-totop="1"`；三个出口各传一次 —— `_list_view()`（目录页）、
`_markdown_page()`（预览页）、`_raw_page()`（源码视图），其余调用点（搜索页、错误页）
一律走默认值。`COPY_JS` 里 `document.body.hasAttribute("data-totop")` 命中才注入按钮
—— 与复制按钮、放大遮罩同一哲学：**禁用 JS 的基线里没有点不动的死按钮**（标记不是
元素，所以 `<body data-totop>` 不算破坏这条）。

**实测**（探针两只 iframe：第一只 `?src=` 是预览页，第二只 `?dir=` 默认 `/preview/` 是
目录页，`window 1200x240`，故意压矮以保证页面可滚动）：

```
totop_on_dirlist:              1          ← 目录页有
totop_on_preview:              1          ← Markdown 预览页也有
totop_css:                     fixed right=20 bottom=20
totop_fixed_bottom_right:      true
totop_scrolls_to_top:          587 -> 0 ok=true
```

**验证**：

- 探针新增 `totop_on_dirlist` / `totop_on_preview` / `totop_css` /
  `totop_fixed_bottom_right` / `totop_scrolls_to_top`（第二只 iframe + 合成点击 +
  等 700ms 读回），见上表；源码视图只在服务端多一个标记，由端到端断言覆盖
- 单元 **192 -> 197 项**：新增 `TestBackToTop`（5 项）——三个出口各查一遍标记
  （目录页 / 预览页 / 源码视图，用只挂 `_read_text` 等静态方法的壳直接调 Handler 的
  实例方法）、搜索页与错误页没有标记、基线里没有写死的 `.totop`、CSS 必须是
  `position:fixed` + `right/bottom:20px`、点击必须滚到顶部且带 reduced-motion 分支
- 端到端 **336 -> 345 项**：主页 / 子目录列表 / 预览页 / 源码视图都带标记，搜索页不带；
  按钮与样式确实进了页面；主页与预览页正文里都没有写死的按钮
- 压缩版同步重新生成，两套检查对 `dist/mdview.min.py` 各跑一遍

## 33. 整体评审后的一轮收敛：两个真 bug + 去重 + 测试加固

**背景**："review 优化下代码，感觉劣化的有点严重。" 于是按三路并行评审（成文标准 + smell
基线 / 结构重复 / 测试与文档）把**全仓**过了一遍，这一节只记落地的那部分。

### 修掉的两个真 bug

1. **属性值漏出内部标记**。`render_image` 的 title 少了「取真值」那一步：
   `![a](p.png "x &amp; y")` 把实体保护区的 NUL 哨兵直接写进属性；`![a](p.png "`c`")`
   更糟 —— 行内码走的是**另一套**保护标记（`_CODE_OPEN`/`_CODE_CLOSE` + `code_spans`），
   要到 `parse_inline` 末尾才展开成 `<code>`，落进属性后又被 `wrap_zoom_images` 的标签
   扫描在 `>` 处截断，产出 `title="<code></a>c</code>"` 这种**撕坏的标签**（链接那条
   同样在属性里露出一段标签源码，只是没撕开）。
   修法：新增 `attr_text()` —— 摊平行内码标记 → 解 token → 剥标签 → 反转义，title 与
   alt 共用同一条「属性值是纯文本」的管线。CommonMark 的 title 本来也不做行内解析。
2. **`--no-search` 下错误页仍渲染搜索框**：`_error_page` 调 `_page` 时没传
   `show_search`，默认值是 `True`。修法：`_page(show_search=None)` ⇔「跟随 `CFG.search`」
   —— 搜索框是全局开关，不该由每个调用点各记一遍。

### 去重与收敛（不加功能，行为不变）

| 动作 | 之前 | 之后 |
|---|---|---|
| 协议判定 | **5 处**各抄一份同一个正则（XSS 白名单第一道判据，漂移即漏洞） | 统一 `_has_scheme()` |
| 图标绘制 | 关闭 × 与回到顶部 ↑ 各抄一遍 `createElementNS` + 6 条 `setAttribute` | 共用 `svgIcon(d, roundCaps)` |
| 内容页模板 | 三处重复 `show_search=CFG.search, depth_nav=…, to_top=True` | `Handler._render_page()` 一处 |
| `@media print` | 散在 4 处；其中 dialog 那条因特异度不足**从来没生效** | 合并成一处，改 `dialog.zoomdlg[open]` 让它真生效 |
| 死代码 | `_IMAGE_RE` / `_LINK_RE` / `_T3` / `_T3U` / `_is_punct` / `.op` + `--t-op` / `var(--bg2)` 回退链 / `_dir_page` 转发层 | 全删 |
| `_has_md(path, depth)` | 唯一调用点传 `depth=0`，递归进去立刻 `-1 < 0` 返回 —— 那个分支从未执行 | 去掉参数与分支，行为不变 |
| 分块导航 | 文件头与 README §10 都让人"搜 SECTION 2"，但 CSS 块没有横幅 | 在字符串**外面**加 Python 横幅（不占每页 CSS 字节） |

### 测试加固

- **计数断言不再当字符串比**：`chk "$(… | grep -c …)" '0'` 在计数 10 时会假通过
  （`10` 含 `0`）、计数 2 也满足 `nchk … '1'` —— 25 处改成 `chk_num` / `nchk_num` 的数值比较。
- **断言落在正确的位置**：脚本类只扫 `<script>` 段（`script_of`），样式类先剥注释再压空白
  （`flat_of`）。`chk "放大脚本用 showModal" "$G" 'showModal'` 曾经能被 **CSS 注释**里的
  `showModal()` 满足 —— 与 §32 那次误命中同源。
- **死断言**：`nchk "无 .tree 样式" "$IDX" '\.tree'` 用的是 `grep -qF`（字面匹配），
  `\.tree` 永远不可能命中，改成 `'.tree'`。

### 评审提到、但这轮刻意没动的

- `_bare_url_sub.covered` 每个 URL 线性扫全部保护区间的平方级退化：区间数与 URL 数同级，
  要修得换数据结构，收益不抵风险（AGENT.md 的"警惕平方级退化"针对的是长行）；
- `parse_inline`（246 行）/ `render_blocks`（133 行）的体量：拆分要先立一层渲染上下文，
  属于独立一轮；
- README 里"21 条路径逐路径差分"的旧声明：仓库并不带那个脚本，已改成不声称结果。

### 验证

- 单元 **197 -> 199 项**（新增 `TestAttributeTitles` 两条：图片/链接的 title 必须是纯文本，
  且不允许出现 `\x00`、`<code>`、`</a>c`）；端到端 **345 项**（含新加的数值断言写法）
- 源码与 `dist/mdview.min.py` 各跑一遍全绿；压缩版由 `tools/minify.py` 重新生成
- 探针实测与改动前**逐字节一致**（截图 sha256 相同）：`close_icon 24x24 offset=0,0`、
  `totop_on_dirlist/preview 1`、`totop_scrolls_to_top 587 -> 0` —— 说明这轮全是行为保持的重构
- 文档同步：README 体积表 / 计数 / `?raw=1` 说明 / §10 交叉引用、SELFTEST 首表计数、
  ADR 0002 的 `allow-discrete` 描述（退场已经是瞬时的）、`selftest.sh` 里"12 种语言"的旧注释

## 34. 第二轮「能不能简化优化」评审：三个平方级热点 + 目标装配收敛

**背景**：「`mdview.py` 单文件已经有几千行了，查看代码是否能够简化优化？」先把文件按
AST 量了一遍：3349 行里内联 CSS/JS 占 738 行、关键字与 MIME 数据表 164 行、注释 270 行、
空行 360 行 —— 真正的逻辑约 1850 行；全文件只有 **3 处 ≥4 行的完全重复块**，其中一处
还是硬约束 3 明令不许合并的 `read_tokens` 双读法。

所以结论不是「删重复」，而是 **「没什么可删的重复，但有三个平方级热点」**：这轮只做热点
与几处小收敛，不做结构重排。

### 三个平方级热点（全部实测复现，不是推测）

1. **一长串 `[` 把线程钉死**。`_REF_LINK_RE` = `(!?)\[...\]\[...\]` 在**没有 `]`** 的
   输入上，每个起点都要把 `[^\]]*` 回溯到底 —— 是干净的 O(n²)：实测 0.070 / 0.274 /
   1.099 / 4.399 秒，每翻倍正好 4 倍。40 KB 的 `.md` 要 4.4 秒；按默认 `--max-preview`
   20 MiB 外推是**以天计**，而默认绑定 `0.0.0.0` —— 一个请求占死一个线程。
   修法：该正则必须含字面 `][`，加一行 `if "][" not in text: return text` 守卫。

   **为什么既有断言没拦住**：`test_link_scan_is_linear`（S17）的输入是 `"[x](" * 20000`，
   走的是 `_scan_link_spans` 的栈配对（本来就是线性），触发点根本不同。教训是
   「线性断言」必须钉在**每个**正则/扫描的具体退化形态上，光有一条「链接解析线性」不够。

2. **单个超长定界符 run 实际是 O(n³)**。配对循环里的 `if j in closer.values()` 每次都是
   O(已配对数)，而它位于「逐 opener × 向右找 closer」的双层循环内。实测 `*`×32000
   1.56 秒、×64000 6.26 秒。
   注意 **`MAX_DELIM_RUNS` 挡不住它**：那道闸门数的是定界符 run 的**个数**，而 64000 个
   `*` 只是**一个** run（切出 32000 个节点），闸门完全没生效 —— 也就是说这份护栏的作用
   与注释宣称的不一致。
   修法：把「已认领的 closer」单独维护成一个 `set`。

3. **`_bare_url_sub.covered()` 逐个比较 protected 区间**，复杂度是
   O(URL 匹配数 × 区间数)：8000 条链接 + 8000 条裸 URL（203 KB）2.57 秒，×20000
   （508 KB）17.7 秒。

   **这一条是上一轮 §33 明确评估过、并决定不修的**，原文理由是「区间数与 URL 数同级，
   要修得换数据结构，收益不抵风险」。这轮改判，理由两条：
   (a) 规模上它已经进入无法忽略的量级 —— 17.7 秒不是常数因子问题，是平方级的证据；
   (b) 修法并不需要「换数据结构」，合并区间 + `bisect` 就够，而且能写出改前全红、
   改后全绿的回归断言 —— §33 的判断前提是「风险」，风险被测试覆盖后该判断不再成立。

   ⚠️ 原型第一版把判据写成「包含 s」而不是「与 [s, e) **严格重叠**」，被 5 条既有断言
   当场打回（既有实现是 `s < pe and e > ps`，区间可以嵌套、可以只擦到右半段）。
   这正说明这套测试在起作用；最终实现保留了「左边那个的右端越界」或「右边那个的左端
   未及 e」两个分支。

### 去重与收敛（除第 4 条外行为不变）

| 动作 | 之前 | 之后 |
|---|---|---|
| 目标装配 | 行内/引用 × 链接/图片**四份**各写一遍 | 收进 `_target_attrs()` 一份 |
| title 属性 | 三处重复 | `_title_attr()` |
| 引用式产出 | `_REF_DEF_LINK.sub` 与 `_shortcut_ref` 尾部同构 | `_render_ref()` 四条支路共用 |
| title 判定 | `_parse_link_title` / `_tail_is_blank_or_title` 各跑一遍同一张表 | `_quoted_inner()` |
| 查询参数布尔 | `raw` / `download` 各抄一遍字面量 | `Handler._flag()` |
| 死代码 | `_delim_re()`（纯转发）、`_DELIM_SYMBOLS`、`_PUNCT` | 删 |
| 零碎 | `LANG_LABEL` 重复键 `toml`；`_route` 里 `splitext` 算两遍；`render_dir_listing` 的 `cls` 三个分支同值；两处缺空行（E302） | 逐个清掉 |

4. **唯一的行为变化，且是修 bug**：引用式的目标装配原先把 `unquote` 之后的串写进属性，
   行内式写作者原样串。于是 `[x][r]` + `[r]: https://e.com/a%20b` 产出
   `href="https://e.com/a b"`，而行内式 `[x](https://e.com/a%20b)` 产出 `%20` 那一版
   （VS Code 与 markdown-it 都是后者，`test_angle_destination_with_scheme` 与
   `test_obfuscated_scheme_never_executes` 分别钉住了 `%20` 与混淆协议两端的期望）。
   这正是硬约束 3 说的「副本漂移」，收敛到 `_target_attrs` 后两条路逐字节一致。

### 验证

- 单元 **199 → 203 项**（新增 S17b/S17c/S17d/S17e 四条）；端到端 **345 项**不变
- 四条新断言**在改前实现上全部失败、在改后实现上全部通过**（逐条跑过；`[` 那条在改前
  报 `4.48 not less than 1.0`）
- 源码与 `dist/mdview.min.py` 各跑两套，全绿；压缩版由 `tools/minify.py` 重新生成
- **行为保持性**：11 组样例（强调 / 引用式 / 尖括号目标 / 混淆协议 / 列表 / 表格 /
  徽章嵌套）与改前逐字节比对，只有上面第 4 条那一处差异，且它是本轮刻意修的
- 实测（同机计时，`parse_inline` 或 `render_markdown`）：

  | 输入 | 改前 | 改后 | 加速 |
  |---|---|---|---|
  | `"[" * 40000`（40 KB） | 4.53 s | 0.007 s | 622× |
  | `"*" * 32000 + "x"`（32 KB） | 1.56 s | 0.032 s | 49× |
  | `"*" * 64000 + "x"`（64 KB） | 6.26 s | 0.076 s | 82× |
  | 链接 + 裸 URL ×8000（203 KB） | 2.57 s | 0.183 s | 14× |
  | 链接 + 裸 URL ×20000（508 KB） | 17.72 s | 0.524 s | 34× |

  加速比随规模增大而增大，正是「平方级被拿掉」的指纹（若只是常数优化，倍率应收敛）。

### 评审提到、但这轮刻意没动的

- **拆 `parse_inline`（266 行）/ `parse_emphasis`（147 行）**：复杂度是固有的，且
  `parse_inline` 的步骤顺序承重（四条约束各有坏 HTML 反例，§24/§25 钉着），12 个嵌套
  闭包共享 `tokens` / `code_spans` / `ctx`；改成类只是换个写法、长度相当、风险大。
- **合并 `read_tokens` / `read_tokens_markup`**：硬约束 3 明令不许 —— 合并的那一版就是
  真漏洞。
- **`resolve_ctype` 的第二个返回值**：它就是把入参 `bool()` 回显，调用点已经持有该值；
  但 `tests_render` 把它钉成了二元组接口（多处 `resolve_ctype(...)[1]`），改它要连着
  测试一起动，收益为零 —— 记为已知冗余。

### 这轮发现、但**没有**修的真实缺陷（已记录，未处理）

- **`_mark` 会把 HTML 实体劈开**：搜索页的高亮是在**已转义**的文本上做子串匹配并插入
  `<mark>`，命中字母落在实体内部时就把实体切断。实测源码 `a < b`、查询 `lt` 产出
  `a &<mark>lt</mark>; b`，浏览器显示成 `a &lt; b`（应显示 `a < b`）。同一原因还有
  假阳性：查询 `amp` 会命中只含 `&` 的行。
  更麻烦的是它的 docstring 声称「避开 HTML 实体边界」，而实现并没有 —— **文档与实现
  不符**，正是本仓库最在意的那类问题。修法要改成「在源文本上定位命中区间，再映射到
  转义文本上插标记」，属于匹配逻辑的行为修复，与这轮的「简化 + 性能」不同类，故单列。

## 35. base64 内嵌图片不渲染：`data:` 被协议白名单整类拒绝

**现象**：`![x](data:image/png;base64,…)` 显示成字面文本；引用式
`![x][r]` + `[r]: data:image/png;base64,…` 显示成 `![x][r]`；尖括号写法同样退化。

**根因**：解析器认识这条语法，是协议闸门把它挡掉了。`SAFE_SCHEMES` 只列了
http/https/mailto 等协议，`safe_href()` 对 `data:` 返回空串，`render_image()` /
`_ref_image_html()` 于是返回 `None`，整条图片按字面文本退化。这条拒绝是 §18.1
修存储型 XSS 时加上的，README 与 AGENT.md 都把它写成硬约束 —— 所以本轮是
**安全策略的有意变更**（ADR 0003），不是补一个解析分支。

**修法**：把 `data:` 的放行收在**消费方**，而不是全局协议表：

- `safe_href(url, allow_data_image=False)` 默认行为不变；只有 `render_image` /
  `_ref_image_html` 经 `_target_attrs(..., is_image=True)` 传 `True`。
- 只接受 `data:<图片 MIME>[...];base64,<数据>`，且 `;base64` 必须是媒体类型部分的
  最后一个参数（浏览器只认这个位置）；类型集合 `DATA_IMAGE_MIME` 由
  `MIME[IMAGE_EXT]` 生成，与服务端已有图片类型自动对齐（含 `image/svg+xml`）。
- 链接、引用式链接、裸 URL、尖括号自动链接都不传这个开关，同一段 `data:` 文本进
  `<a href>` 仍然不产属性。
- 非 base64、非图片 MIME、缺逗号的 data URI 一律按字面文本退化；payload 里手写的
  引号由 `safe_href` 的 `quote=True` 兜住。
- 数据 URI 图片照常包 `class="zoom"`；禁用 JS 时浏览器拦截 `data:` 顶层跳转，
  点击无反应（图片已内联显示）。

**验证**：

- 新增 `TestDataURIImages` 14 项：行内 / 引用式 / 尖括号 / 尖括号定义 + title、
  `IMAGE_EXT` 全类型、大小写、`;charset;base64`、链接目标仍拒绝、非图片/非 base64
  拒绝、`%64ata:` 混淆保持相对路径、payload 引号转义、裸 HTML 仍转义、zoom href
  与 src 逐字节相同、徽章不嵌套。
- **反向验证**：14 项里有 10 项在修改前的实现上失败（全部是放行类）；另外 4 项是
  边界/拒绝类，改前改后都通过，用于防止放宽过头。
- 旧断言 `test_rejected_protocol_stays_literal`（`data:text/html` 图片）一行未改，
  仍然通过。
- 单元 **203 → 217 项**；端到端 **345 项不变**。源码与 `dist/mdview.min.py` 各跑
  两套全绿（压缩版因 docstring 被删，`test_known_tradeoff_documented_in_module`
  按既有约定 skip 1 项）。

**刻意不做的**：

- 裸 HTML `<img src="data:…">` 仍整体转义 —— 「正文裸 HTML 一律转义」是另一条硬约束，
  本次只放开 Markdown 图片目标。
- 非 base64 的文本 data URI 不支持。
- 单张 data URI 不设上限；整份 `.md` 仍受 `--max-preview`（默认 20 MiB）约束。
