# 二进制 / 超大文件测试

这一页是**可点击的测试清单**。每个文件都标了「预期行为」，你点开对照即可。

判定规则（实现细节见 [SELFTEST.md §16](../../SELFTEST.md)）：

| 顺序 | 条件 | 结果 |
|---|---|---|
| 1 | 超过 `--max-preview`（默认 **20 MiB**） | 准确类型 + `Content-Disposition: attachment` → **下载** |
| 2 | 命中源码/配置扩展名表 | `text/plain; charset=utf-8` → 预览 |
| 3 | 命中内置 MIME 表 | 按表（图片/PDF…） |
| 4 | **无扩展名** | 看开头 **512 字节**有无 NUL：有→下载，无→按文本预览 |
| 5 | 其余 | `application/octet-stream` → 下载 |

---

## 1. 无扩展名：512 字节嗅探边界

这一组是**核心测试**。`nul_at_511` 与 `nul_at_512` 只差一个字节的位置，结果应当**不同**。

| 文件 | 内容特征 | 预期 |
|---|---|---|
| [noext_text](binary/noext_text) | 纯中文文本，无 NUL | ✅ 预览 |
| [noext_empty](binary/noext_empty) | 0 字节 | ✅ 预览（空白页，不报错） |
| [noext_gbk](binary/noext_gbk) | GBK 编码，无 NUL | ✅ 预览（**可能乱码**，但不下载）|
| [noext_nul_at_0](binary/noext_nul_at_0) | NUL 在第 0 字节 | ⬇️ 下载 |
| [**noext_nul_at_511**](binary/noext_nul_at_511) | NUL 在第 511 字节（**512 内**）| ⬇️ **下载** |
| [**noext_nul_at_512**](binary/noext_nul_at_512) | NUL 在第 512 字节（**512 外**）| ⚠️ 服务端判**预览**，但 Chrome 自己也会下载 |
| [noext_nul_at_5000](binary/noext_nul_at_5000) | NUL 在第 5000 字节 | ✅ 预览（NUL 显示为不可见字符）|
| [noext_random](binary/noext_random) | 4096 字节随机数据 | ⬇️ 下载 |

> `nul_at_512` 这条是**两套阈值不同**的体现：我们的嗅探只看前 512 字节，Chrome 自己的检测范围更靠后一点。前 512 字节内出现 NUL 时两边一致判二进制，所以危险情形都被拦住了。

## 2. 有扩展名的真二进制格式

| 文件 | 真实格式 | 预期 |
|---|---|---|
| [real.png](binary/real.png) | 合法 PNG（纯标准库构造）| ✅ **内联显示图片** |
| [real.pdf](binary/real.pdf) | 合法最小 PDF | ✅ **内联显示**（浏览器 PDF 阅读器）|
| [real.zip](binary/real.zip) | 真 ZIP（含中文条目）| ⬇️ 下载 |
| [fake.elf](binary/fake.elf) | ELF 文件头 | ⬇️ 下载 |
| [fake.macho](binary/fake.macho) | Mach-O 文件头 | ⬇️ 下载 |

## 3. 超过 20 MiB 的文件（每种类型一个）

**这些是稀疏文件** —— 表观大小真的有 21-25 MiB，但磁盘与 git 只占几百 KB。所以你可以放心点。

| 文件 | 表观大小 | 预期 |
|---|---|---|
| [big.md](large/big.md) | 21 MiB | ⬇️ 下载（**注意：不渲染**）|
| [big.txt](large/big.txt) | 22 MiB | ⬇️ 下载 |
| [big.bin](large/big.bin) | 23 MiB | ⬇️ 下载 |
| [big.png](large/big.png) | 24 MiB | ⬇️ 下载（**超限的图片也不显示**）|
| [noext_big](large/noext_big) | 25 MiB | ⬇️ 下载（先撞大小限制，不看嗅探）|

### 关键对照：`?raw=1` 也不能绕过

- [big.md](large/big.md) → 下载
- [big.md?raw=1](large/big.md?raw=1) → **同样下载**（源码视图也受上限约束）

### 对照：正常大小仍然预览

- [code/sample.py](code/sample.py) → 预览
- [media/sample.gif](media/sample.gif) → 预览（动图）
- [index.md](index.md) → 本页

## 4. 自己造非稀疏的真实大文件

上面的稀疏文件内容是全零，适合测「超限」逻辑。如果你想测**真实内容**的大文件（比如 30 MiB 的中文文本，看它有多卡），用这个：

```bash
# 30 MiB 真实中文文本
python3 - <<'EOF'
line = "# 中文标题行：这一行大约 80 字节，用来模拟真实文本内容。\n"
with open("real-30mib.txt", "w", encoding="utf-8") as f:
    f.write(line * ((30*1024*1024) // len(line.encode())))
EOF
```

想看 20 MiB 到底有多卡，把它放进服务根目录点开即可 —— 实测约 **13.7 秒、2.5 GiB 内存**。

## 5. 常用参数

```bash
# 关掉上限（任何大小都尝试预览）
python3 mdview.py --root docs --max-preview 0

# 收紧到 1 MiB（舒适阈值，实测数据支持 1-5 MiB）
python3 mdview.py --root docs --max-preview 1M

# 放宽到 100 MiB
python3 mdview.py --root docs --max-preview 100M
```

---

[返回预览总览](index.md) · [代码块专项测试](../guide/code-blocks.md)
