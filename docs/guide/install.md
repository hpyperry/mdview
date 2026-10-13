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

### 路径里有空格：两种写法

文件名带空格时 Markdown 有两种写法，`mdview` 渲染出的 `src` **完全相同**，
与 VS Code 预览的判定也一致（`%20` 就是空格；只解码一次、只编码一次）：

- **尖括号写法** —— VS Code 把文件拖进编辑器时写出的正是这种形式：空格保持
  原样，整段路径用 `<>` 包住；
- **百分号写法** —— 从 URL 或别处粘贴过来时常见的形式。

![带空格的图片（尖括号写法）](<../media/带 空格.png>)

![带空格的图片（百分号写法）](../media/带%20空格.png)

两张图指向同一个文件，输出都是：

```html
<img src="/media/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png" alt="…">
```

> 文件名里**字面**含 `%` 的文件（例如 `100%.png`）要写成 `100%25.png`；
> 反过来，写成 `%25` 的路径也只会命中名字里真的带 `%` 的那个文件。
> 裸空格（`![x](../media/带 空格.png)`，不带尖括号）不是合法写法 ——
> 与 VS Code 一样，整行按字面文本显示；用上面两种写法之一即可。

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
