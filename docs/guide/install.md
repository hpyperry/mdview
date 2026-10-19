# 安装、运行与 Trust

这篇文档放在 `docs/guide/` 下，用来验证**相对链接**与**图片相对路径**的重写，
同时说明新实现的启动方式与安全模型。

## 构建

```bash
cargo build --release
# 产物：target/release/mdview（macOS/Linux）或 mdview.exe（Windows）
```

CI 为四个目标平台构建单文件二进制：

| 平台 | target |
|------|--------|
| macOS Apple Silicon | `aarch64-apple-darwin` |
| Linux x86_64 (musl) | `x86_64-unknown-linux-musl` |
| Linux arm64 (musl) | `aarch64-unknown-linux-musl` |
| Windows x86_64 (static CRT) | `x86_64-pc-windows-msvc` |

二进制内嵌 CSS、highlight.js 与客户端脚本，运行时**不请求任何外部资源**，
也不依赖 Python/Node。

## 运行

```bash
# 服务当前目录，本机访问
mdview --root . --host 127.0.0.1

# 只暴露 Markdown 与图片
mdview --root docs --host 127.0.0.1 --safe

# 端口被占用时自动 +1 重试（默认 10 次）
mdview --root docs --port 8000
```

默认监听 `0.0.0.0:8000`；只想自己看时务必改成 `127.0.0.1`。

| 参数 | 默认 | 说明 |
|------|------|------|
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8000` | 起始端口 |
| `--port-tries` | `10` | 端口占用时向后尝试次数 |
| `--root` | 当前目录 | 服务根目录 |
| `--safe` | 关 | 只放行 `.md` 与图片 |
| `--max-preview` | `20M` | 超过此大小改为下载；`0` 不限制 |
| `--no-search` | 关 | 关闭全文搜索 |
| `--trust` / `--untrusted` | — | 本次运行强制信任/不信任（不写入配置） |
| `--security-level` | 配置或 `0` | CSP 级别 0–3 |

## Trust：为什么第一次打开会问一次

裸 HTML 按 VS Code 语义**原样透传**，因此“是否信任这个目录”决定了页面能执行什么：

- **trusted**：Markdown 直接渲染；
- **untrusted**：每个 `.md` 首次打开出现确认页，点“仍要打开”后生成一次性令牌
  （绑定路径、60 秒有效、消费一次）。`?raw=1` 与 `?download=1` 不受拦截。

启动时如果该根目录没有已保存的信任状态，会在 TTY 里问一次并写入配置；
非交互环境默认 **untrusted**。配置位置（`directories` crate）：

| 平台 | 路径 |
|------|------|
| macOS | `~/Library/Application Support/mdview/trust.toml` |
| Linux | `~/.config/mdview/trust.toml` |
| Windows | `%APPDATA%\mdview\config\trust.toml` |

`--trust` / `--untrusted` 只影响本次运行，不写配置；`--security-level` 会写入。

## CSP（4 档）

| 级别 | 行为 |
|------|------|
| 0 Strict | 脚本只允许 per-response nonce；图片/样式/字体允许 `self`、`https:`、`data:`；`frame/form/base/object 'none'` |
| 1 Allow HTTP | 在 0 的基础上为图片/样式/字体额外允许 `http:` |
| 2 Disable（不推荐） | 不发送 CSP |
| 3 Allow localhost HTTP | 在 0 的基础上额外允许 `http://localhost:*` / `http://127.0.0.1:*` |

所有响应带 `X-Content-Type-Options: nosniff`；渲染页与源码页带 per-response nonce，
`script-src` 只信任该 nonce（没有 `'self'`）。

## 相对链接

- 回到上级：[../index.md](../index.md)
- 同级文件：[advanced.md](advanced.md)
- 回到本节：本页开头（标题不生成锚点，见 [边界](advanced.md)）

## 图片相对路径

相对路径按「**当前文档所在目录**」解析，因此 `../media/logo.svg` 指向
`docs/media/logo.svg`，与用哪个 `--root` 启动无关：

![mdview 图标](../media/logo.svg)

以 `/` 开头的站内路径按「**服务根**」解析，所以下面这张图只有在
`--root docs` 时才加载得出来：

![mdview 图标（根路径）](/media/logo.svg)

### 路径里有空格

文件名带空格时，尖括号写法与百分号写法渲染出的 `src` 完全相同：

![带空格的图片（尖括号写法）](<../media/带 空格.png>)

![带空格的图片（百分号写法）](../media/带%20空格.png)

输出都是：

```html
<img src="/media/%E5%B8%A6%20%E7%A9%BA%E6%A0%BC.png" alt="…" />
```

> 相对目标按 VS Code 语义**解码两次、编码一次**。代价是文件名里**字面**含
> `%xx` 的文件（如 `x%20y.png`）不能通过相对 Markdown 目标到达；用目录索引或
> 绝对 URL 访问。理由见 [ADR 0001](../adr/0001-markdown-target-encoding.md)。

## 目录结构

```text
md-preview/
├─ Cargo.toml
├─ src/                     # Rust 实现
│  ├─ main.rs / lib.rs
│  ├─ cli.rs / trust.rs
│  ├─ server.rs
│  ├─ render.rs
│  └─ assets.rs
├─ assets/                  # 内嵌的 CSS / highlight.js / 客户端 JS
├─ tests/
│  ├─ render_compat.rs
│  └─ selftest-rust.sh
└─ docs/                    # 本目录
```

## 返回

[回到首页](../index.md)
