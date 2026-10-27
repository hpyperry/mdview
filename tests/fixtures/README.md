# 手动测试夹具

每个 feature 一个子目录，目录内是可被 mdview 直接服务的测试文件和一份 README。
自动化测试可以使用这些目录中的夹具；人工复测直接用目录启动服务。

| 目录 | 覆盖 |
|---|---|
| `archives/` | 压缩包虚拟目录、包内 Markdown/HTML、嵌套包 |
| `html-preview/` | HTML Trust 原文/沙箱、子资源、SVG |
| `encodings/` | GBK/UTF-16/UTF-32、编码标签、搜索与 charset |
| `static-parity/` | 内部 URL 与同名文件、文件尾斜杠、Markdown 扩展名、目录 index 非目标 |

通用启动方式：

```bash
cargo build --release
./target/release/mdview --root tests/fixtures/<feature> --trust --port 8003 --port-tries 0
```

新增 feature 夹具时：

1. 新建 `tests/fixtures/<feature>/`；
2. 在 README 写启动命令、入口 URL、预期结果与已知限制；
3. 自动测试从该目录复制文件，不另生成同名夹具；
4. 二进制夹具在 `.gitattributes` 标为 `binary`。
