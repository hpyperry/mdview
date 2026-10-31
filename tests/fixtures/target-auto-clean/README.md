# post-merge 自动清理 target/debug 复测文档

- 关联：Issue #31 / PR #N / 无 F-xx（开发者工具，不是用户可见功能）
- 夹具根：`tests/fixtures/target-auto-clean/`（README-only，没有可服务的夹具）
- 启动：不启动服务；下面的命令在临时 git 仓库里跑，不碰本仓库的 `target/`
- 自动化覆盖：无新增自动化；`node tests/check-doc-links.mjs` 与 `bash tests/run-all.sh`
  覆盖文档与既有套件

## 背景

`scripts/git-hooks/post-merge` 在合并或 `git pull` 之后检查 `target/debug`，超过阈值
（默认 2048 MB）就删除它，保留 `target/release`。hook 永远以 0 退出，不会挡住 git。

## 复测步骤

1. 操作：`bash scripts/install-git-hooks.sh`
   预期：输出 `已设置 core.hooksPath = scripts/git-hooks`；
   `git config --get core.hooksPath` 返回 `scripts/git-hooks`。

2. 操作：在临时仓库里超过阈值时触发
   ```bash
   TMP="$(mktemp -d)" && cd "$TMP" && git init -q
   mkdir -p target/debug && dd if=/dev/zero of=target/debug/blob bs=1048576 count=3
   MDVIEW_CLEAN_THRESHOLD_MB=2 bash /path/to/mdview/scripts/git-hooks/post-merge
   test ! -d target/debug && echo "cleaned"
   ```
   预期：打印 `target/debug 已到 3 MB（阈值 2 MB）…`，然后 `cleaned`。

3. 操作：未超过阈值时什么都不做
   ```bash
   TMP="$(mktemp -d)" && cd "$TMP" && git init -q
   mkdir -p target/debug && dd if=/dev/zero of=target/debug/blob bs=1048576 count=1
   MDVIEW_CLEAN_THRESHOLD_MB=2 bash /path/to/mdview/scripts/git-hooks/post-merge
   test -d target/debug && echo "kept"
   ```
   预期：无输出，`kept`。

4. 操作：关闭开关
   ```bash
   MDVIEW_NO_AUTO_CLEAN=1 MDVIEW_CLEAN_THRESHOLD_MB=0 \
     bash /path/to/mdview/scripts/git-hooks/post-merge
   test -d target/debug && echo "kept"
   ```
   预期：无输出，`kept`（阈值 0 本应触发，被开关挡下）。

5. 操作：本仓库正常拉取
   ```bash
   git pull --ff-only
   ```
   预期：`target/debug` 低于阈值时 hook 不产生任何输出，`git pull` 照常成功。

## 已知限制

- git hooks 不进版本库：没跑过安装器的 clone 不会自动清理，只有文档约定。
- `core.hooksPath` 是仓库本地配置，会**覆盖**已有的 hooks 目录（安装器会提示）。
- hook 只处理 `target/debug`；`target/release`、`tools/spike/*/target` 不动。
- 阈值写在脚本常量里，文档里的 2 GB 是同一口径；改阈值要同时改两处或改用环境变量。
- 在 cargo 正在构建时删目录会让那次构建失败；hook 不做运行中检测，遇到时重跑即可。
- Windows 上 git hooks 走 Git Bash，`du` 语义与 macOS/Linux 一致，但未在 CI 验证。

## 清理

- 临时仓库与其中的 `target/debug` 用完删除（`rm -rf "$TMP"`）。
- 本仓库想停用：`git config --unset core.hooksPath`。
