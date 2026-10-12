# tests/ —— 自测与开发工具

这个目录放**所有与测试相关的东西**，仓库根只留可交付的源码（`mdview.py`）与文档。
所有脚本都从自身位置推出仓库根，因此**在任何目录下执行都可以**。

| 文件 | 作用 | 命令 |
|------|------|------|
| `tests_render.py` | 渲染器回归测试（48 项，纯 `unittest`，不联网不起服务） | `python3 tests/tests_render.py` |
| `selftest.sh` | 端到端 HTTP 冒烟测试（113 项断言，自己起临时服务、跑完自清理） | `bash tests/selftest.sh` |
| `sync_nav.py` | 重新生成 `mdview.py` 顶部导航的**真实行号**（生成物，需可校验） | `python3 tests/sync_nav.py` |

## 一套跑完

```bash
# 在仓库根执行
python3 tests/tests_render.py      # 48 项单元测试
bash tests/selftest.sh             # 113 项端到端断言
python3 tests/sync_nav.py --check  # 导航行号与代码是否一致（不一致退出码 1）
```

三个命令都是零依赖、可重复执行的，不需要 `pip install`。

## 各自覆盖什么

**`tests_render.py`** —— 纯渲染层，不起服务：
强调 flanking 规则（中文/词内/三连/相邻/未配对）、转义与行内码混排的占位符泄漏、
代码块内 HTML 必须转义（XSS 回归）、Dockerfile/Compose 指令大小写、数字边界
（`C.UTF-8`、`v1.2.3` 不被切）、无语言围栏必须素色、链接与图片重写、路径夹紧、
列表嵌套与松紧、表格对齐、搜索文件名命中，等等。

**`selftest.sh`** —— 真起服务、真发 HTTP：
非 Markdown 文件的 `Content-Type` 与标准库 `mimetypes` 逐项比对、静态文件不发
`Content-Disposition`/`Cache-Control`、带 `Last-Modified`；
目录索引、渲染结果、`?raw=1` 源码视图的行锚点（并核对第 5 行内容与源文件一致）、
子目录与图片相对路径、301 补斜杠、深度树、全文搜索分栏、断链检查（页面里每个
`href`/`src` 逐个请求）、路径穿越不外泄、以及 `--safe` / `--no-search` /
端口占用回退三个参数开关。结束时打印 `PASS=n FAIL=n`，非零退出码表示有失败项。

可用 `PORT=9000 bash tests/selftest.sh` 换一组临时端口（脚本会用到 PORT..PORT+5）。

**`sync_nav.py`** —— 开发工具，不是测试：
`mdview.py` 顶部的 SECTION 导航写着每个 section 的起始行号，改代码后行号会漂移。
这个脚本重算它们，避免"文档说行号、代码说别信行号"的自相矛盾。
`--check` 适合放进提交前检查；它带守卫，块结构不符会**拒绝改写**而不是猜。

## 约定

- 新增测试请放在本目录；不要往仓库根加脚本。
- `tests_render.py` 里的断言若与实现冲突，**先核对规格**再改断言 —— 历史上出现过
  "断言写错、实现被逼着迁就"的情况（见 `../SELFTEST.md` §4）。
- 改动 `mdview.py` 后请跑：`sync_nav.py` → `tests_render.py` → `selftest.sh`。
