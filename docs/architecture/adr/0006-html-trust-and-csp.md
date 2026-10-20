# 裸 HTML、Trust 与 CSP：复刻 VS Code 预览的安全模型

**Status**: accepted（2026-10-19）；`form-action` 由
[ADR 0009](0009-search-scope-and-form-csp.md) 从 `'none'` 放宽为 `'self'`

VS Code 核心语义要求裸 HTML 透传（markdown-it `html: true`）。这推翻了旧版
“正文与代码块里的裸 HTML 一律转义”的核心防线，必须用另一套模型补上。
VS Code 的做法是两层：**工作区信任**决定打开预览前是否提示；**预览安全级别**
决定 CSP 的松紧。本决定把这套模型搬到独立服务器上。

## 决定

### 1. 裸 HTML

- 始终透传，不再转义。旧版的 XSS 防线从“转义”改为 **CSP + Trust**。
- Markdown 生成的链接/图片仍过 `validateLink`（见 ADR 0005）；裸 HTML 不经过它，
  由 CSP 约束。

### 2. 启动信任

- 启动时读取 `--root`（或当前目录）的规范化绝对路径，在用户配置目录里查记录。
- 没有记录且 stdin 是 TTY：询问“是否信任该目录”。回答写入配置。
- 配置位置：
  - macOS `~/Library/Application Support/mdview/trust.toml`
  - Linux `$XDG_CONFIG_HOME/mdview/trust.toml`（默认 `~/.config/mdview/trust.toml`）
  - Windows `%APPDATA%\mdview\trust.toml`
- 记录按根目录路径保存 `trusted` 与 `security_level`。
- 非 TTY 且没有记录：默认**未信任**，打印提示；`--trust` / `--untrusted`
  覆盖本次运行。
- 信任状态只决定“渲染 Markdown 时是否先拦”，不改变文件可读范围、目录索引、
  搜索或下载。

### 3. 未信任时的拦截面

- 每个渲染 `.md` 请求都显示 VS Code 风格的拦截面：
  “这个 Markdown 文件所在的目录尚未受信任。仍要打开吗？” + 取消 / 仍要打开。
- 「仍要打开」给当前 URL 加一个**一次性令牌**（`?open=<随机值>`）。服务端在内存里
  保存“令牌 → 路径 + 过期时间”，验证后立即删除；刷新同一 URL、收藏该 URL、打开下一
  页面都会再次拦截。这与 VS Code “每次打开预览都提示”一致，也避免 `?open=1` 成为
  永久绕过开关。
- `?raw=1` 与 `?download=1` 不渲染裸 HTML，不需要拦截。
- 非 md 源码查看页只做转义展示，也不需要拦截。

### 4. 安全级别

完整复刻 VS Code 的 4 档，按根目录保存，默认 0：

| 级别 | 名称 | 行为 |
|---|---|---|
| 0 | Strict | 只允许 https/data 图片、字体、媒体；脚本只允许带 nonce 的本站脚本 |
| 3 | 允许 localhost HTTP | 在 0 上增加 `http://localhost:*`、`http://127.0.0.1:*` |
| 1 | 允许 HTTP | 在 0 上增加 `http:` |
| 2 | Disable | 不发送 CSP；文档内脚本可执行（不推荐） |

Strict 的 CSP：

```text
default-src 'none';
img-src 'self' https: data:;
media-src 'self' https: data:;
script-src 'nonce-<random>';
style-src 'self' 'unsafe-inline' https: data:;
font-src 'self' https: data:;
frame-src 'none';
form-action 'none';
base-uri 'none';
object-src 'none'
```

- `script-src` **只用 nonce**，绝不加 `'self'`。否则磁盘上任意 `.js` 都能被裸 HTML
  以同源脚本加载，等于绕过防线。
- 页面里我们自己的脚本标签带同一 nonce；highlight.js 也从 `/_assets/` 以 nonce 加载。
- 所有 HTML 响应加 `X-Content-Type-Options: nosniff`。
- 级别 2 不发送 CSP；启动横幅明确警告。它与 Trust 独立：未信任目录点
  「仍要打开」后，如果级别是 2，文档脚本会执行——这与 VS Code 的组合一致。

### 5. 修改安全级别

没有 Web UI（VS Code 有预览工具栏的安全选择器）。用：

```bash
mdview --security-level 0|3|1|2 --root docs
```

或编辑 `trust.toml`。命令行给出的级别会写入该根目录的配置。
这是有意的收敛：服务器可能被局域网访问，不能给远程用户一个改安全设置的入口。

### 6. 资产与 nonce

- CSS/JS 全部从 `/_assets/<hash>/…` 同源提供。
- 每个 HTML 响应生成新的随机 nonce；`<script nonce="…">` 只出现在我们生成的
  模板里，裸 HTML 无法预知它。
- 静态资产长缓存；页面本身 `no-store`（Markdown 改动刷新即见）。

## 考虑过的替代方案

- **继续全部转义裸 HTML**：最安全、旧测试全保留；但与 VS Code 核心语义直接冲突，
  用户明确否掉。
- **HTML sanitizer（ammonia 等）**：可以放行安全子集；但这是第三套语义，
  既不是 VS Code 的透传，也不是旧版的转义，且 sanitizer 自身是攻击面。
- **不实现 Trust，只留 `--allow-html`**：部署简单，但没有 VS Code 的启动询问与
  拦截面体验。
- **拦截面只弹一次/会话 cookie**：文档站更好用；用户明确选择“每次打开都弹”，
  与 VS Code 保持一致。
- **把安全级别做成网页设置**：更接近 VS Code 的选择器；但任何能访问服务器的人
  都能把级别降到 2，风险不可接受。

## 后果

- 安全模型更复杂：CSP 头、nonce、Trust 配置、拦截面都要有测试。
- 级别 2 是一个真实的“文档脚本可执行”模式；只能显式选择。
- 即使在 Strict，裸 HTML 仍可做 UI 伪装（隐藏内容、假按钮等）；VS Code 接受
  这个风险，我们也接受，并在 README 里提示只服务可信文档。
- 旧版“裸 HTML 一律转义”的回归测试全部失效，替换为 CSP/协议/拦截面测试。
