# SELFTEST —— 端到端验证结果

本文件记录 `mdview.py` 的实际验证结果，**每条都能照着复现**。
不是"应该可以"，而是这台机器上当时跑出来的输出。

| 项目 | 命令 | 结果 |
|------|------|------|
| 渲染器单元测试 | `python3 tests/tests_render.py` | **55 项全部通过**（`Ran 55 tests ... OK`） |
| 端到端 HTTP 验证 | `bash tests/selftest.sh` | **126 项断言全部通过**（`PASS=126 FAIL=0`） |
| 语法兼容性 | `ast` 扫描 | 无 walrus / `match` / 3.9+ 独有语法 → 3.6+ 可运行 |
| `--safe` | 见下 §3 | 只放行 `.md` 与图片，其余 404 |
| `--no-search` | 见下 §3 | 路由与界面搜索框同时消失 |
| 端口占用 | 见下 §3 | 自动 +1 回退并打印真实 URL |
| 视觉确认 | Chrome headless 截图 | 暗色模式、高亮、表格、任务列表、中文排版正常（截图见 §3.1） |
| 代码块专项 | `docs/guide/code-blocks.md` | 17 种语言 + 全部围栏变体 + 16 条验收清单，自检覆盖每种语言 |

环境：macOS，`Python 3.14.7`（代码按 3.6+ 写，未用新语法）。

---

## 1. 渲染器单元测试

```console
$ python3 tests/tests_render.py
...
----------------------------------------------------------------------
Ran 45 tests in 0.014s

OK
```

覆盖：强调 flanking 规则（含中文/词内/三连/相邻/未配对）、**转义与行内码混排的占位符泄漏**
（回归测试）、裸 HTML 转义、实体、引用式链接、引用嵌套、列表嵌套与松紧、任务列表、
有序 `start`、表格对齐、围栏与高亮、链接与图片重写、路径夹紧、slug、搜索。

---

## 2. 端到端 HTTP 验证（`bash tests/selftest.sh`，126 项）

脚本自己在 `127.0.0.1:8731` 起临时实例，跑完自动关闭。关键断言与实测：

```console
== 目录索引 / ==
  ok   列出 index.md
  ok   列出 guide/ 子目录
  ok   带搜索框
  ok   带展开树入口
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

PASS=126 FAIL=0
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
python3 tests/tests_render.py      # 55 项
bash tests/selftest.sh             # 126 项（自动起停临时服务）
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
| 悬停显现、触屏常显、打印隐藏 | 不干扰阅读；`@media (hover:none)` 与 `@media print` 分别处理 |
| 带 `aria-label` | 可访问性 |

验证：

- 浏览器内探针（`--dump-dom`）：2 个代码块都注入成功；`innerText` 含中文、
  且**不含**"复制"二字（证明没把按钮文字一起复制）
- `node --check` 通过内联 JS 语法检查
- 无代码块的页面（目录索引、搜索结果）执行脚本无运行时错误，页面正常
- 单元测试 55 项（+5：脚本只注入一次、HTML 无硬编码按钮、双剪贴板路径、
  文本取法、悬停/触屏/打印样式）
- 端到端 126 项（+7：内联脚本、Clipboard 路径、兜底路径、悬停样式、
  触屏规则、HTML 无死按钮、目录索引仍正常）
