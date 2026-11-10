# 工程约束与门禁

## 硬规则

- 手写程序文件最多1000物理行，空行、注释和模板内容计入。默认更严格地覆盖非文档文本文件（包括配置），仅 `.md`、`.rst` 文档及二进制不计行数。
- 按职责拆分，禁止压缩长行、改后缀、代码载荷或无意义编号拆分绕过。
- 模块数据有归属，公开接口有边界；禁止循环依赖和随意跨模块写数据。Python 静态导入按声明层及循环检查；直接 SQL、动态导入等仍须评审。
- Python 函数复杂度默认最多15，具体计算口径见下文；这是本工具的默认门槛，不是行业统一标准。
- 涉及权限、状态、数量、版本的功能，必须有相应的后台约束和反例测试；本工具的测试不等于业务测试已完成。
- 门禁实现、测试及豁免变更本身也须评审，不自行放宽阈值。

## 运行环境

Python 3.12+、Git。当前工具不安装第三方依赖。

## 统一入口

```bash
# 工作区，包括未被忽略的新文件
python3 scripts/check_quality.py

# 完整暂存快照
python3 scripts/check_quality.py --staged

# 指定提交的内容，而非旁边的工作区
python3 scripts/check_quality.py --revision HEAD

# 只检查行数
python3 scripts/check_file_lines.py
```

统一入口先检查行数、Python 函数复杂度、声明层依赖及静态循环，再执行配置的 `commands` 和 `tests/test_*.py`。无测试、测试失败、缺少必需检查文件均失败。暂存及提交快照在临时目录中运行测试，避免用未提交修复掩盖失败。

增加其他语言或业务模块后，必须将真实测试命令接入统一入口；现有 Python 测试仅验证门禁工具本身，不能代替前后端或全流程验收。

## 复杂度与模块边界

`quality-gates.json` 显式声明 Python 源码根、层所拥有的模块前缀及允许依赖的层。每个 Python 文件必须且只能归属一个层，缺配置、未归属或重复归属均失败。新增业务模块必须补充实际边界，不能把所有模块长期归为一个层。

函数分支分数从1开始：if／条件表达式、循环、except、assert 每项加1；布尔 and／or 按额外操作数计；推导式按生成器和筛选条件计；match 按非默认分支和 guard 计。嵌套函数及 lambda 单独计算。它是明确约定的 AST 分支指标，不宣称与 Radon、Sonar 等工具完全等价。

默认上限15，可在评审后按项目调整；不得为放行某次失败静默调高。1000行硬上限仍需用户明确确认才能改变。

边界示例（均有回归测试）：

```python
def nested(rows):
    # 1 + 两个生成器 + 两个筛选条件 = 5
    return [[x for x in row if x > 0] for row in rows if row]


def guarded():
    # 1 + 两个 except = 3；try / else / finally 本身不加分
    try:
        work()
    except ValueError:
        recover()
    except TypeError:
        reject()
    else:
        accept()
    finally:
        cleanup()


def choose(x):
    # 1 + 一个非默认 case = 2；模式中的 | 不是布尔 or，不额外加分
    match x:
        case 1 | 2:
            return True
        case _:
            return False
```

嵌套结构不另设加权；嵌套太深仍可能难读，需要人工评审。match 的 guard 另加1，其中布尔表达式仍按规则计分。

静态依赖检查覆盖 Python 的 import／from，包括相对导入，禁止未声明的跨层依赖及文件级循环。不能识别任意动态导入、SQL 或其他语言，不冒充完整架构验证；非 Python 项目需配置对应语言的复杂度及依赖工具。

## 测试与评审

按 [变更评审清单](change-review.md) 记录正常、禁止、异常及适用的并发／幂等路径，绑定候选提交与实际结果。复杂度低于阈值仍需评审职责、嵌套、状态组合及可读性。

权限、审批、金额、库存、数量或迁移等高风险变更需安排独立评审；未取得时写明“未独立评审”，不能自行宣称通过。不设置一个通用覆盖率百分比来代替业务行为测试。

## 其他语言、CI 与旧项目

具体工具、可复制配置和接入步骤见 [integration-guide.md](integration-guide.md)：包含 ESLint complexity、导入边界、argv 命令接入、快照依赖限制、GitHub／GitLab 模板及旧项目盘点。

Python 3.12+ 是 CLI 的显式启动检查，不依赖 shebang 保证版本。hook 只支持 POSIX 环境，原生 Windows 使用 WSL2；junction 有防护和模拟测试，不宣称原生 Windows 已完成验收。

## 本地自动门禁

启用：

```bash
python3 scripts/install_hooks.py
```

安装器只修改当前仓库的 `core.hooksPath`，拒绝覆盖不同的已有配置或传统 hook。不要用全局 hooksPath 强制接管其他项目。

- `pre-commit`：自动检查完整暂存快照。
- `pre-push`：自动检查待推送引用的本地 tip 快照，删除引用除外；不回放所有历史提交。
- 查看当前是否启用：`git config --show-origin --get core.hooksPath`，预期为本仓库 `.githooks`。
- 新机器克隆后需主动执行安装器。查看现有 hook 后才能启用，不自动覆盖。

## 远端门禁待办

本地 hook 可被 `--no-verify` 绕过，不能作为远端强制保障。

远端 CI 与主分支保护尚未配置、未验证。启用时需要：

1. 核对实际 Git 托管平台及套餐支持的 CI、必过检查与审核能力。
2. 在干净环境固定候选提交运行 `python3 scripts/check_quality.py`，依赖有锁定。
3. 禁止直接推送和强推主分支；必要检查失败时不得合并。
4. 在临时分支制造超限或测试失败，实际验证远端会拒绝合并。
5. 门禁文件受审查，不能通过在同一个变更中删除检查来自行放行。

不因脚本存在或本地检查通过，就宣称上述远端要求已生效。

## 验证依据

自动测试覆盖1000／1001行、复杂度15／16、禁止依赖、允许依赖、相对导入循环、模块归属、注释空行、未跟踪文件、暂存与工作区不一致、指定提交、真实提交 hook、推送 hook、缺文件、零测试，以及已有 hook 冲突。全部在临时仓库操作，不在业务分支制造测试提交。

行数只是必要条件，不是可维护性的充分条件；职责边界、业务正确性、权限与并发需要各自评审和测试。
