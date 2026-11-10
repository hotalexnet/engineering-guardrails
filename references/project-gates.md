# 仓库门禁工具包

## 文件与职责

- `scripts/check_file_lines.py`：检查工作区、暂存快照或指定 Git 树中的非文档文本文件，最多1000物理行。
- `scripts/check_quality.py`：统一检查入口。工作区检查行数并运行 `tests/test_*.py`；暂存／提交检查先验证行数，再在临时导出快照运行测试，避免拿别的工作区版本冒充提交结果。
- `scripts/install_hooks.py`：只设置当前仓库的 `core.hooksPath=.githooks`，拒绝接管已有其他 hook。
- `.githooks/pre-commit`：检查即将提交的完整暂存快照。
- `.githooks/pre-push`：检查待推送分支的本地 tip 快照；删除引用不检查。不逐个回放全部历史提交。
- `tests/test_file_lines.py`：行数边界、暂存与工作区差异、Git 树快照测试。
- `tests/test_quality_gates.py`：真实提交／推送 hook、快照测试隔离、缺文件／零测试及安装冲突测试。
- `docs/engineering-gates.md`：项目可维护性规则及门禁状态说明。

工具仅依赖 Python 3.12+ 和 Git。为安全导出快照使用 tarfile 的 data filter；不拉取外部资源、不自动安装依赖。

## 初始化和已有文件

`init_project.py` 先检查所有目标路径，只复制不存在或内容完全相同的文件；有不同内容时整体停止，不做半套替换。工具包不包含 AGENTS，以免覆盖项目规则；由使用者有针对性追加。

已有项目先报告存量问题并确认采用方式。允许更新已知的门禁实现，但需读原文件、针对性修改、重新测试；不能用初始化器强制覆盖。

## 常用命令

```bash
python3 scripts/check_quality.py
python3 scripts/check_quality.py --staged
python3 scripts/check_quality.py --revision HEAD
python3 scripts/check_file_lines.py
```

`--staged` 会执行 git write-tree，把当前索引写成树对象，不创建提交、不修改暂存内容。存在冲突时失败。
快照检查不包含未暂存或未提交的代码；工作区检查用于补充发现未跟踪文件。
无测试或测试失败均失败；项目增加其他语言后，需要把该语言的实际测试命令明确接入检查入口，不能将这些 Python 工具测试当作全应用验收。

## 强制能力与限制

本地 hook 可被 `--no-verify` 绕过，其他人克隆后也不会自动启用。因此必须在 CI 对候选提交运行统一入口，并在平台上保护主分支，才有远端约束。
当前工具包不配置任何特定平台 CI，不验证分支保护，不修改远端。

CI 应在干净检出、固定候选提交、受控依赖环境运行检查，失败禁止合并。门禁及豁免文件本身应受评审；不能允许一个合并请求删除检查后自行获得通过。
Git archive 可能受 export-ignore 属性影响；快照必须保留 tests 与检查文件，否则检查失败。不要用导出属性排除受测源码。

行数检查不替代职责评审、依赖检查、权限测试、数据正确性或并发验收。1000 行以下也可能设计很差。
