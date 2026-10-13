# AGENT.md —— mdview 改动指南

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
2. **服务端渲染**：正文 HTML 在 Python 侧生成，禁用 JS 也要能正常阅读。全站唯一的 JS
   是代码块复制按钮，且**由脚本注入**（不写死按钮元素）。
3. **两条 XSS 防线缺一不可**：正文与**代码块内**的裸 HTML 一律转义；链接/图片目标过协议
   白名单（`javascript:`/`data:` 不产出属性）。两条各漏过一次，都是真实漏洞。
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
- 类型判定三层（白名单 → MIME 表 → 内容嗅探），所以没登记过的文本也能预览；代价是前
  512 字节无 NUL 的二进制会显示乱码 —— 个例不要靠"往白名单加一条"来修。

## 实现层的坑

- **`?raw=1` 不是原始字节**：它返回带行锚点的源码视图页（仍是 HTML），专供搜索跳转；
  要磁盘原文用 `?download=1`。源码视图里刻意不渲染 Markdown，那里没有链接不是缺陷。
- **`parse_inline` 的步骤顺序是承重的**：裸 URL 自动链接必须落在 `html.escape` 之前、
  `_ENTITY_RE` 之前、引用式展开之前、`_AUTOLINK_RE` 之后；四条约束各有对应的坏 HTML
  反例，见 SELFTEST §24。挪动任何一步之前先读那段注释。
- **压缩器只做三件语义安全的事**（删注释 / docstring / 空行），用 `tokenize` 定位，
  **字符串字面量里的空行必须保留**（`COPY_JS` 里有一个）。不要改成正则实现。
- **警惕平方级退化**：配对扫描与"每次匹配回退找行首"都踩过。新增的正则或扫描要对长行
  保持线性（定界符有 `MAX_DELIM_RUNS` 封顶，行首用前进式指针维护）。

## 变更记录怎么留

`SELFTEST.md` 是**缺陷与验证台账**，按编号章节追加：现象 → 根因 → 修法 → 验证，
并写明"旧期望值一行未改"这类约束。修掉一个真实缺陷、或做一次需要论证的取舍时，
在这里加一节；决策性内容进 `docs/adr/`，新术语进 `GLOSSARY.md`。
