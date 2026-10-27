# 手动测试夹具与复测文档

每个 feature/fix 至少一份人工复测文档。有夹具时放在 `tests/fixtures/<slug>/`，
目录内是可被 mdview 直接服务的测试文件和一份 README；纯修复可以只放 README，但要在
文档里说明实际使用的 root/入口。自动化测试可以使用这些目录中的夹具；人工复测直接
用目录启动服务。

README 是**复测文档**，不是测试执行报告。必须包含：

1. 关联 Issue/PR 与 F-xx（没有 F-xx 的修复写 Issue/PR）；
2. 启动命令与入口 URL；
3. 复测步骤与每一步预期；
4. 自动化覆盖（单测/黑盒/浏览器探针）；
5. 已知限制与清理方式（临时服务、端口、临时文件）。

| 目录 | 覆盖 |
|---|---|
| `archives/` | ZIP 容器（JAR/EPUB/CBZ）、tar.bz2/tar.xz、包内 Markdown/HTML、嵌套包 |
| `html-preview/` | HTML Trust 原文/沙箱、子资源、SVG |
| `encodings/` | GBK/UTF-16/UTF-32、编码标签、搜索与 charset |
| `nav-lazy/` | 三层预载、当前路径脊柱、`dir=` 按需展开、深层目录占位 |
| `static-parity/` | 内部 URL 与同名文件、文件尾斜杠、Markdown 扩展名、目录 index 非目标 |

通用启动方式（使用子目录 root 的以该目录 README 为准）：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/<feature> --trust --port 8003 --port-tries 0
```

新增 feature/fix 夹具时：

1. 新建 `tests/fixtures/<slug>/`，复制 [`TEMPLATE.md`](TEMPLATE.md) 为 README；
   纯修复可以先只建 README；
2. README 写清上面的五项内容；
3. 有夹具时目录必须能作为 `--root` 启动；需要子目录 root 的，在 README 写明确切命令；
4. 自动测试从该目录复制文件，不另生成同名夹具；
5. 二进制夹具在 `.gitattributes` 标为 `binary`；
6. PR 描述链接该 README；新增/修改 F-xx 时功能矩阵也链接它。
