# SELFTEST —— 端到端验证结果

本文件记录 `mdview.py` 的实际验证结果，**每条都能照着复现**。
不是"应该可以"，而是这台机器上当时跑出来的输出。

| 项目 | 命令 | 结果 |
|------|------|------|
| 渲染器单元测试 | `python3 tests/tests_render.py` | **85 项全部通过**（`Ran 85 tests ... OK`） |
| 端到端 HTTP 验证 | `bash tests/selftest.sh` | **198 项断言全部通过**（`PASS=198 FAIL=0`） |
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

PASS=198 FAIL=0
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
python3 tests/tests_render.py      # 85 项
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

新增 `docs/preview/`：一个总览页 + 36 个样例文件，覆盖三条内联路径：

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
