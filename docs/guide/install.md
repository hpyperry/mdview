# 安装与使用（子目录示例）

这篇文档放在 `docs/guide/` 下，用来验证**相对链接**与**图片相对路径**的重写。

## 安装步骤

1. 确认 Python 版本（3.6+ 即可，本目录代码不用 3.9+ 语法）：

   ```bash
   python3 -V
   ```

2. 拷贝整个 `md-preview/` 目录到目标机器（无需 `pip install`）。

3. 在 `md-preview/` 下启动：

   ```bash
   python3 mdview.py --root docs
   ```

## 相对链接

- 回到上级：[../index.md](../index.md)
- 同级文件：[advanced.md](advanced.md)
- 锚点：[#安装步骤](#安装步骤)
- 回到根：[mdview 示例首页](../index.md#行内语法)

## 图片相对路径

相对路径按「**当前文档所在目录**」解析，因此 `../media/logo.svg` 会指向 `docs/media/logo.svg`。
这种写法与用哪个 `--root` 启动无关，**推荐优先用相对路径**：

![mdview 图标](../media/logo.svg)

以 `/` 开头的站内路径则按「**服务根**」解析，所以下面这张图只有在
`--root docs`（也就是根目录恰好是文档库根）时才加载得出来：

![mdview 图标（根路径）](/media/logo.svg)

> 若在上一层目录用默认根启动（例如 `python3 mdview.py`），上面这张图会 404 ——
> 因为 `/media/logo.svg` 会被解析成 `<服务根>/media/logo.svg`。
> `mdview` 启动时若发现根目录下没有 Markdown 而子目录里有，会直接提示该用哪个 `--root`。

## 目录结构

```text
md-preview/
├─ mdview.py            # 唯一可交付源码
├─ README.md
├─ SELFTEST.md
├─ tests/               # 测试
│  ├─ tests_render.py
│  └─ selftest.sh
└─ docs/                # 就是本目录
   ├─ index.md
   ├─ guide/
   │  ├─ install.md    <- 就是本篇
   │  ├─ advanced.md
   │  └─ code-blocks.md
   └─ media/
      ├─ logo.svg
      └─ screenshot-*.png
```

## 返回

[回到首页](../index.md)
