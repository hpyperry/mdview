# <Feature 或 Fix 名称> 测试报告（YYYY-MM-DD）

- 关联：Issue #N / PR #N / F-xx
- 夹具：`tests/fixtures/<slug>/README.md`（没有新夹具时写现有夹具路径）
- 类型：browser（浏览器/视觉）或 test（后端/其他）

## 环境

| 项 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| 分支 / commit | `feat/...` @ `<sha>` |
| 平台 | macOS / Linux / Windows + 架构 |
| Rust / Node | 版本 |
| 浏览器 | 版本（浏览器/视觉报告必填） |
| 被测根 | 夹具路径 / 启动命令 |
| 端口 | 主端口 / 第二 origin（如适用） |

## 自动套件

| 套件 | 命令 | 结果 |
|---|---|---|
| 单元/集成 | `cargo test --lib` | N passed |
| 黑盒 HTTP | `bash tests/selftest-rust.sh` | PASS=N FAIL=N |
| 浏览器探针 | `node tests/browser-probe.mjs` | PASS=N FAIL=N |
| 其他 | `...` | ... |

非可视化改动在这里贴关键命令输出或 CI run 链接；浏览器/视觉报告把截图放到
`docs/testing/evidence/<YYYY-MM-DD>/`。

## 复测步骤与证据

| 编号 | 场景 | 操作 | 预期 | 结果 | 证据 |
|---|---|---|---|---|---|
| F-xx | ... | ... | ... | 通过/失败 | `../evidence/<date>/...png` 或命令输出 |

## 发现

- 通过项 / 失败项 / 需要人工确认的项。
- 失败项必须有复现步骤、预期、实际与证据。

## 覆盖缺口

- 未测平台、旧内核、反向代理、局域网/手机、未覆盖的边界。

## 结论

- 是否通过；是否可以进入下一阶段；需要哪些后续 Issue。
