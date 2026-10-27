# 浏览器验收：文件编码（2026-10-27）

**被测版本**：mdview 2.1.0 工作树 + 文件编码检测分支
**验收方式**：headless Chrome 自动探针 + 实际页面截图
**结论**：GBK Markdown/源码页正确解码并显示编码标签；UTF-16LE BOM 可预览；
GBK 正文可搜索；HTML 原文保持原字节。自动探针 `PASS=210 FAIL=0`。

## 证据

| 编号 | 页面 | 预期 | 结果 | 证据 |
|---|---|---|---|---|
| V1 | GBK Markdown | 正文“中文标题”正常；页头显示 `GBK` | 通过 | [截图](evidence/2026-10-27/encoding-gbk-markdown.png) |
| V2 | GBK 源码页 | 正文正常；标签显示 `GBK` | 通过 | [截图](evidence/2026-10-27/encoding-gbk-source.png) |
| V3 | UTF-16LE BOM 源码页 | 正文正常；标签显示 `UTF-16LE BOM` | 通过（自动） | `tests/browser-probe.mjs` |
| V4 | GBK 搜索 | 搜索“中文”命中 `/gbk.md#L1` | 通过（自动） | `tests/browser-probe.mjs` |
| V5 | HTML 原文/下载 | 原文不转码；下载 `text/html` 不带 charset | 通过（黑盒） | `tests/selftest-rust.sh` |

## 自动断言

- `node tests/browser-probe.mjs`：**PASS=210 FAIL=0**，新增 GBK Markdown 文本/标签、
  GBK 源码文本/标签、UTF-16LE 标签、GBK 搜索命中 7 项。
- `bash tests/selftest-rust.sh`：**PASS=238 FAIL=0**，覆盖 GBK/UTF-16/UTF-32、
  下载/raw charset、HTML 下载无 charset。

## 已知边界

- 检测是启发式的；短小 legacy 文件可能误判（例如短 GBK 片段判成 EUC-KR/Big5）。
- 无 BOM 且以非 ASCII 为主的中文 UTF-16 可能识别失败；UTF-32 按二进制下载。
- 本轮不提供手动编码覆盖；HTML 原文没有 mdview 外壳，因此不显示编码标签。
