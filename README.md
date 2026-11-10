# Engineering Guardrails

面向 AI 编程代理的通用工程约束 Skill：把规则放进长期指令，把执行步骤放进 Skill，把可验证检查放进项目仓库。

## 解决什么问题

- 手写程序单文件最多 **1000 个物理行**，含空行、注释及模板内容。
- 按职责拆分模块，避免循环依赖、越界写数据及巨型公共工具文件。
- 适用时验证权限、版本、状态、事务、并发和重复请求，不只测试正常路径。
- 用反例验证门禁真的会失败，不把“检查脚本存在”等同于约束生效。
- 不强制技术栈、微服务或通用流程引擎；旧项目先评估，不自动批量改造。

## 安装到 Pi

在目标目录尚不存在时：

```bash
git clone https://github.com/hotalexnet/engineering-guardrails.git \
  ~/.agents/skills/engineering-guardrails
```

Pi 支持发现 `~/.agents/skills/` 下的 Skill。当前会话执行 `/reload`；可使用 `/skill:engineering-guardrails` 显式加载。

**发现 Skill 不等于每次都加载全文。** 建议在自己的 `~/.pi/agent/AGENTS.md` 中追加简短规则，不要覆盖已有配置：

```markdown
## 工程约束
- 新项目、代码修改／重构、门禁建立和交付前，先读取并遵循
  ~/.agents/skills/engineering-guardrails/SKILL.md。
- 程序单文件最多1000物理行，包含空行与注释，不得靠压缩代码绕过。
- 新项目建立仓库内检查；旧项目先评估，不自动批量改造。
- 只报告实际验证结果，不将本地 hook 称为远端强制门禁。
```

其他代理是否自动发现此目录、如何加载全局约定，应按对应工具配置，不假设与 Pi 相同。

## 给项目建立门禁

要求：Python 3.12+、Git，且目标已是独立 Git 仓库。

```bash
python3 ~/.agents/skills/engineering-guardrails/scripts/init_project.py \
  --repo /absolute/path/to/project

cd /absolute/path/to/project
python3 scripts/check_quality.py

# 审核已有 hook 后，主动启用本仓库的自动门禁
python3 scripts/install_hooks.py
```

初始化器先预检全部目标，不覆盖不同内容，不修改 AGENTS，不安装依赖，不暂存、不提交、不推送。存在已有实现时停止，由维护者针对性整合。

工具复制进项目后自包含，不依赖使用者的主目录或这个 Skill 仓库运行。

### 项目中的能力

| 入口 | 行为 |
| --- | --- |
| `python3 scripts/check_quality.py` | 检查工作区行数并运行工具测试 |
| `python3 scripts/check_quality.py --staged` | 检查完整暂存快照，并在临时快照运行测试 |
| `python3 scripts/check_quality.py --revision HEAD` | 检查指定提交快照 |
| `pre-commit` | 自动检查即将提交的暂存快照 |
| `pre-push` | 检查待推送引用的本地 tip，删除引用除外 |

行数默认覆盖所有非文档文本文件，包括配置。`.md`、`.rst` 文档与二进制不计行数。已跟踪文件不能通过新加 `.gitignore` 逃避检查。

## 验证本 Skill

从本仓库根目录执行：

```bash
python3 assets/project-kit/scripts/check_file_lines.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s assets/project-kit/tests -p 'test_*.py' -v
```

测试在临时 Git 仓库验证1000／1001行边界、暂存与工作区差异、真实 hook 拦截、快照隔离、零测试失败、初始化冲突及不覆盖已有 hook。

## 明确限制

- Skill 和全局约定是代理指导，不是不可绕过的强制执行器。
- 本地 hook 可绕过，新克隆也不会自动启用；远端强制约束需要另行配置 CI、必要检查及分支保护。
- 工具包当前实现的是行数门禁和工具自身测试，**没有自动实现模块依赖、权限、业务流程或并发正确性检查**。
- 新业务和其他语言的测试必须接入项目检查入口；工具测试不是应用验收。
- 不含任何本机全局配置、业务资料、账号凭据；不自动修改远端设置。

完整流程见 [SKILL.md](SKILL.md)，门禁机制见 [references/project-gates.md](references/project-gates.md)。
