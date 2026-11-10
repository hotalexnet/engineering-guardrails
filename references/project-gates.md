# 仓库门禁工具包

## 五类约束

| 类别 | 自动化能力 | 仍需人工判断 |
| --- | --- | --- |
| 文件规模 | 非文档文本文件最多1000物理行 | 是否压缩代码或机械分片绕过 |
| 复杂度 | Python 函数 AST 分支分数默认最多15 | 低分函数是否仍难读，非 Python 代码的工具选择 |
| 模块边界 | 声明层的静态导入依赖、模块归属、文件级循环 | SQL、动态导入、跨模块写数据和公开接口合理性 |
| 测试 | 执行工具回归测试，缺文件／零测试失败 | 应用行为覆盖、必要并发和集成测试是否充分 |
| 评审 | 提供随变更填写的清单 | 独立评审人、结论、风险接受及主分支审核要求 |

工具不将“全部检查通过”解释为软件质量保证。15是可说明、可调整的项目默认值，不是行业标准。

## 文件与职责

- `quality-gates.json`：Python 函数阈值、源码根、模块所属层及允许依赖。
- `scripts/check_file_lines.py`：工作区、暂存快照或指定 Git 树的1000行检查。
- `scripts/check_python_design.py`：Python 复杂度、声明层依赖及静态循环检查。
- `scripts/check_quality.py`：统一运行以上检查和 `tests/test_*.py`。
- `scripts/install_hooks.py`：设置当前仓库 `core.hooksPath=.githooks`，拒绝接管已有其他 hook。
- `.githooks/pre-commit`：检查完整暂存快照。
- `.githooks/pre-push`：检查待推送引用的本地 tip，不检查删除操作或逐个回放历史。
- `tests/test_file_lines.py`：行数边界及不同快照。
- `tests/test_python_design.py`：复杂度15／16、允许／禁止依赖、相对导入循环及归属错误。
- `tests/test_quality_gates.py`：真实 hook 拦截、快照隔离、缺文件／零测试、安装冲突。
- `docs/engineering-gates.md`：项目规则、度量口径和强制能力边界。
- `docs/change-review.md`：测试矩阵、模块影响、独立评审和发布证据记录模板。

依赖 Python 3.12+ 和 Git，快照导出使用 tarfile data filter，无第三方 Python 依赖。

## 复杂度与依赖口径

每个函数从1开始计分：if／条件表达式、for／async for／while、except、assert 各加1；and／or 按额外操作数计；推导式按生成器及筛选条件计；match 按非默认分支及 guard 计。嵌套函数、方法及 lambda 独立度量。不宣称与 Radon／Sonar 完全等价，非 Python 代码需选择对应工具。

源码根必须明确，每个 Python 文件只能归属一个声明层；新模块漏配会失败。依赖按 import／from 的静态模块名解析，允许同层依赖但仍禁止文件级循环。标准库和第三方导入不参与内部层约束；动态路径和运行时注册需要评审，不能把这种分析称为完整架构验证。

初始化配置仅描述工具本身的 checks／entry／tests 分层。加入业务模块时需声明实际数据和接口边界，不能把全部业务归入一个通用层来规避约束。

## 初始化和已有文件

`init_project.py` 预检所有目标，只复制不存在或内容相同的文件；有不同内容时停止，不覆盖。工具包不包含 AGENTS，以免覆盖项目规则，由使用者针对性追加。

已有项目先报告存量问题并确认采用方式。更新已知的门禁实现时，先读原文件、针对性修改、重新验证，不使用初始化器强制覆盖。

## 常用命令

```bash
python3 scripts/check_quality.py
python3 scripts/check_quality.py --staged
python3 scripts/check_quality.py --revision HEAD
python3 scripts/check_python_design.py
```

`--staged` 用 git write-tree 固定索引，不创建提交或改变暂存内容；冲突会失败。快照检查使用该快照的配置和源文件，测试在临时导出目录执行，不能用工作区修复冒充提交通过。

无测试或测试失败均失败。增加业务及其他语言后，需要把实际测试命令接入入口，Python 工具测试不是应用验收。新增规则要注入违规反例，验证 hook 同样会失败。

## 独立评审与强制能力

按 `docs/change-review.md` 填写测试矩阵与评审记录，记录候选提交、范围、实际结果及遗留风险；未评审不得自动打勾。高风险变更需要独立只读评审，代理自查不能替代，不自动启动其他代理或修改生产。

本地 hook 可被 --no-verify 绕过，新克隆也不会自动启用。远端需要 CI、必要检查和主分支保护；工具包不自动配置平台、不假设平台支持某种配置格式。

CI 应在干净检出、固定候选提交和受控依赖环境执行入口；门禁／阈值／测试删除同样需审查。Git archive 受 export-ignore 影响，不得借导出属性排除受测代码；缺必需检查文件或测试会失败。

本 Skill 仓库的 GitHub 工作流独立于目标项目工具包。工作流配置存在不等于已运行成功，也不等于主分支保护已开启，交付时分别报告。
