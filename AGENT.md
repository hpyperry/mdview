# AGENT.md —— mdview 改动指南

> **注意（分支 `refactor/new-md-view-server`）**
>
> 仓库正在从 Python 单文件重写为 **Rust 单文件可执行程序**。下方“硬约束”中的
> 零第三方依赖、Python 3.6 语法、`tools/minify.py` 流程只适用于**旧实现**，
> 不要套到新代码上。新实现允许成熟 crate，产物仍是单文件，Markdown 语义与视觉
> 严格对齐 VS Code 1.142.0。新设计见
> [`docs/design/new-md-view-server.md`](docs/design/new-md-view-server.md)，
> 决策见 [`docs/adr/0004`](docs/adr/0004-rust-rewrite-and-dependencies.md)、
> [`0005`](docs/adr/0005-vscode-1.142-as-oracle.md)、
> [`0006`](docs/adr/0006-html-trust-and-csp.md)。新实现落地后本文件会整体重写。

给在这个仓库里干活的 agent。`README.md` 是规格与用户文档，这一页是**改动者的路线图**：
先读完它，再按指针去读细节。

## 这是什么

`mdview.py` 是**单文件、零第三方依赖的离线 Markdown 预览服务器**：起一个静态服务，
把目录里的 `.md` 在服务端渲染成网页，其余文件按类型判定后原样发送。
实现只有 Python 标准库，拿到就能跑（`dist/` 里的压缩版是派生产物，见下）。

```bash
python3 mdview.py --root docs --host 127.0.0.1   # 起服务（默认 0.0.0.0:8000，根=当前目录）
python3 tests/tests_render.py                    # 渲染层单元测试
bash tests/selftest.sh                           # 端到端 HTTP 断言
python3 tools/minify.py                          # 改完 mdview.py 必须重新生成 dist/
```

两套测试都必须绿。`PORT=9000 bash tests/selftest.sh` 可换端口；两套都支持指向替代实现
（`MDVIEW_FILE=` / `MDVIEW=`）来对压缩版跑同一批断言。

## 硬约束

1. **零第三方依赖，语法停在 Python 3.6**：只用 stdlib；可用 f-string，不用 walrus、
   不用 `list[str]` 这类 3.9 泛型。每隔一段时间就会有人提"引入一个小库"，已经被否过，
   理由记在 [`docs/adr/0001`](docs/adr/0001-markdown-target-encoding.md)。
2. **服务端渲染**：正文 HTML 在 Python 侧生成，禁用 JS 也要能正常阅读。全站只有**一段**
   内联 JS（`COPY_JS`），做三件事：代码块复制按钮、图片放大遮罩、"回到顶部"按钮（目录页/预览页/源码视图）；
   三者都**由脚本注入** —— 不写死按钮元素、也不写死 `<dialog>`（服务端最多留一个
   `data-totop` 标记，那不是元素；SELFTEST §26/§32 有断言钉着"基线里没有死元素"）。
3. **XSS 防线**（已经漏过三次，每次都是真实漏洞）：正文与**代码块内**的裸 HTML 一律转义；
   链接/图片目标过协议白名单（`javascript:`/`vbscript:`/链接位置的 `data:` 不产出属性；
   唯一的例外是图片 `src` 的 `data:image/<已登记类型>;base64,…`，见 ADR 0003）；
   **标签渲染必须区分
   "纯文本消费方"与"标记内容消费方"**（`read_tokens` vs `read_tokens_markup`，
   alt 是属性值所以必须 `quote=True`）—— 第三条漏过的是
   `![a" onerror=…](p.png)`（属性注入）与 `[<script>…](u.md)`（标签里裸 HTML 被反转义）。
4. **改完 `mdview.py` 的收尾动作**：两套测试 → `python3 tools/minify.py` 重新生成
   `dist/mdview.min.py`（它入库）→ 同步 README / tests/README.md / SELFTEST.md 里因此
   变化的计数与描述。
5. **测试放 `tests/`**，仓库根只留可交付源码。断言与实现冲突时**先核对规格**
   —— 历史上出现过"断言写错、实现被迫迁就"（SELFTEST §4）。
6. 文档与提交信息一律中文，前缀用 `feat:` / `fix:` / `docs:` / `refactor:` / `style:`。

## 在单文件里定位

按 **section 标识**搜索，**不按行号**（文档也刻意不写行号，免得漂移）：
`SECTION 1 CONSTANTS` … `SECTION 10 CLI`，用途表见 README §7。
注意 `SECTION 2` 只有顶部导航那一行，CSS 块本身没有横幅，搜 `CSS = """`。

文件里的注释承载了"为什么"。改任何一段之前先读附近注释：多数坑都写在那里，
包括那些看起来多余的分支和顺序。

## 别改坏的两处耦合

**`docs/` 既是示例语料，也是测试夹具。** `tests/selftest.sh` 断言 `docs/index.md`
第 5 行的内容、该页「裸 URL 自动链接」小节的逐条行为，以及 `docs/preview/` 下每个样例
可访问、图片魔数正确。动示例文档会连带弄红测试。

**目标路径的编码管线只有一条路**：切 `?`/`#` → 只解一次百分号 → 相对解析 → 只编一次。
链接、图片、引用式链接/图片、目录索引四条路共用同一个函数，顺序错了就产出指向不存在
文件的 URL（`%20` 变 `%2520`）。术语与决策见 [`GLOSSARY.md`](GLOSSARY.md) 与
[`docs/adr/0001`](docs/adr/0001-markdown-target-encoding.md)。

## 看着像 bug 的刻意设计

这些是记录在案的取舍，不要顺手"修"；完整清单见 README §4「刻意不支持」与 §9：

- 裸 HTML 全部转义，`<br>` / `<details>` 按文本显示。
- `---` 只当分隔线，不当 Setext 二级标题下划线。
- `中文*强调*中文` **会**生效（严格 CommonMark 下不会）。
- 裸 URL 自动链接把全角 `。，、；：！？` 当句末标点（GFM 只认半角）。
- 文件名里字面的 `%xx` 要写 `%25xx`：这里**只解码一次**（VS Code 解两次）。
- 图片放大**不做**相册、滚轮缩放、双指手势、1:1 切换；禁用 JS 时点图片是**同标签**
  打开原图；带修饰键或中键的点击刻意**不劫持**（那是原图的唯一出口）。理由见 `docs/adr/0002`。
- 类型判定三层（白名单 → MIME 表 → 内容嗅探），所以没登记过的文本也能预览；代价是前
  512 字节无 NUL 的二进制会显示乱码 —— 个例不要靠"往白名单加一条"来修。

## 实现层的坑

- **`?raw=1` 不是原始字节**：它返回带行锚点的源码视图页（仍是 HTML），专供搜索跳转；
  要磁盘原文用 `?download=1`。源码视图里刻意不渲染 Markdown，那里没有链接不是缺陷。
- **`parse_inline` 的步骤顺序是承重的**：裸 URL 自动链接必须落在 `html.escape` 之前、
  `_ENTITY_RE` 之前、引用式展开之前、`_AUTOLINK_RE` 之后；四条约束各有对应的坏 HTML
  反例，见 SELFTEST §24。挪动任何一步之前先读那段注释。
- **token 表有两个读法，不许合并**：`read_tokens`（反转义，给 URL/title/alt 这类
  "取出来自己再转义一次"的消费方）与 `read_tokens_markup`（原样取出，给**标记内容**，
  比如链接标签）。合并的那一版就是 `[<script>alert(1)</script>](u.md)` 这个真漏洞，
  见 SELFTEST §25。
- **引用式展开产出的 HTML 必须 `stash` 成 token**（`_REF_DEF_LINK` / `_shortcut_ref`
  / `_render_ref` 收 `render_label` + `stash` 两个参数）：字面写回文本会被后面的
  `parse_emphasis` 再解析一遍，属性值里长出 `<em>`/`<strong>`（SELFTEST §25）。
- **目标装配只有 `_target_attrs` 一个出口**：行内式 / 引用式 × 链接 / 图片四条支路共用
  它（`safe_href` + `ctx.rewrite_target` 不许在别处再调一次）。曾经是四份各写一遍，
  其中两份在「协议分支写哪个串」上漂移了 —— 引用式写 `unquote` 后的串、行内式写原样串，
  于是同一个 `https://e.com/a%20b` 在两种写法下产出不同 href。协议判定是 XSS 白名单的
  第一道门，副本漂移就是漏洞；要加新的目标来源，接这个函数，别复制（SELFTEST §34）。
- **`data:` 的放行口只有 `_target_attrs(..., is_image=True)`**：`safe_href` 默认仍拒绝
  一切 `data:`，只有 `render_image` / `_ref_image_html` 传 `is_image=True`；链接路径
  都不传。不要把 `data:image/…` 的允许规则挪进 `safe_href` 的无条件分支 —— 同一段串
  进 `<a href>` 就是攻击面（ADR 0003）。类型集合 `DATA_IMAGE_MIME` 由 `MIME[IMAGE_EXT]`
  生成，加图片扩展名时自动跟上。
- **服务端包裹图片的落点在 `parse_inline` 出口**（`wrap_zoom_images`）：那时源文本已转义，
  输出里的 `<a`/`<img` 只可能是我们自己生成的，锚点深度才数得准；href 一律复用 img 的 src。
- **遮罩只做入场动画，退场必须瞬时**：不要给 `dialog.zoomdlg` 写
  `transition:display … allow-discrete` —— 它会把退场也拖成 150ms，图片与遮罩在淡出，
  而 × 与 caption 没有 opacity 过渡，会原地原样亮着直到 `display:none`（SELFTEST §29）。
  定位与排版同时放在基础规则里、`[open]` 只切 `display`：几何不随可见性开关变化，
  将来谁再加回出场过渡也不会按 row 重排（§28）。改这段务必跑
  `tools/zoom-probe.html`，且**不要**加 `--force-prefers-reduced-motion` —— 它会把整段
  动画一起关掉，正好藏住这些缺陷。
- **关闭按钮的 × 用现画的内联 SVG，别用字体字形**：U+00D7 的墨迹在 em 盒里本来就不
  居中，且各字体偏得还不一样（22px 下 macOS 系统字体差 ~2.3px，Arial 几乎为零），
  写死任何 px 校正值都会在别的平台偏回去。两条对角线对称于 viewBox 中心，按钮 flex
  居中即可；`stroke` 走 `currentColor`，强制色彩模式下也不会被压没（SELFTEST §30）。
- **遮罩的初始焦点落在遮罩自己，不要落在 × 上**：`showModal()` 会聚焦 dialog 里第一个
  可聚焦元素（那颗 ×），而"上一轮交互是键盘"（比如刚用 Esc 关过）时，程序化聚焦会命中
  `:focus-visible` —— 再打开就带一圈白边。写法是 `d.tabIndex = -1` +
  `showModal()` 之后 `zoom.focus()`（顺序不能反），遮罩自身 `outline:none`；× 的
  `:focus-visible` 白环要留着，那是键盘用户的焦点指示（SELFTEST §31）。
- **压缩器只做三件语义安全的事**（删注释 / docstring / 空行），用 `tokenize` 定位，
  **字符串字面量里的空行必须保留**（`COPY_JS` 里有一个）。不要改成正则实现。
- **浏览器侧验证用 `tools/zoom-probe.html`**：本机 Chrome 跑 `--dump-dom` 会挂着不退出，
  用 `--headless --screenshot` 取回探针渲染出的逐条状态（用法写在文件头）。
- **警惕平方级退化**：配对扫描、「每次匹配回退找行首」、**正则回溯**都踩过 —— SELFTEST
  §34 一次抓出三个，其中 `[` 串 40 KB 要 4.4 秒（默认 20 MiB 上限下以天计）。新增的正则
  或扫描要对长行保持线性，且要能一眼看出不会回溯：`_REF_LINK_RE` 前面那句
  `if "][" not in text` 就是为此存在的守卫。另外三条经验：配对用 `closer`/`claimed` 这类
  O(1) 成员测试，**别写 `x in some_dict.values()`**；区间查询先合并再 `bisect`；
  `MAX_DELIM_RUNS` 只封定界符 **run 的个数**，单个超长 run 封不住（64000 个 `*`
  只是 1 个 run，切出 32000 个节点）。行首仍用前进式指针维护。

## 变更记录怎么留

`SELFTEST.md` 是**缺陷与验证台账**，按编号章节追加：现象 → 根因 → 修法 → 验证，
并写明"旧期望值一行未改"这类约束。修掉一个真实缺陷、或做一次需要论证的取舍时，
在这里加一节；决策性内容进 `docs/adr/`，新术语进 `GLOSSARY.md`。
