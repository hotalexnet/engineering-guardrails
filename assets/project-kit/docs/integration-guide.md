# 工具接入、CI 与渐进迁移

本文为接入说明，不表示前端示例或目标平台已完成实际验收。Python 工具包和本 Skill 的 GitHub CI 有独立测试；应用自己的依赖、构建及业务测试仍需项目验证。

## 1. JavaScript / TypeScript

建议使用项目锁定版本的 ESLint：

- `complexity`：函数复杂度，例如默认15；ESLint 与本工具 Python 分支指标不完全相同。
- `eslint-plugin-import` 的 `import/no-cycle`：静态导入循环。
- `import/no-restricted-paths`：按目录限制模块依赖。更复杂的分层可评估 `eslint-plugin-boundaries` 或 dependency-cruiser，不能只靠目录命名。
- TS 使用 `typescript-eslint` 解析器；路径别名和 TS 解析需要匹配的 resolver 及 `tsconfig.json`。

以下为 TS／JS 混合项目的 flat-config 示例，需在目标项目按实际目录和锁定版本验证：

```js
// eslint.config.mjs
import tseslint from 'typescript-eslint';
import importPlugin from 'eslint-plugin-import';

export default [{
  files: ['src/**/*.{js,jsx,ts,tsx}'],
  languageOptions: {
    parser: tseslint.parser,
    parserOptions: {
      ecmaVersion: 'latest', sourceType: 'module',
      ecmaFeatures: { jsx: true },
    },
  },
  plugins: { import: importPlugin },
  settings: {
    'import/resolver': { typescript: { project: './tsconfig.json' } },
  },
  rules: {
    complexity: ['error', 15],
    'import/no-cycle': ['error', { ignoreExternal: true }],
    'import/no-restricted-paths': ['error', {
      zones: [{
        target: './src/domain', from: './src/ui',
        message: 'domain must not depend on ui',
      }],
    }],
  },
}];
```

目标项目需安装并锁定 `eslint`、`typescript`、`typescript-eslint`、`eslint-plugin-import`、`eslint-import-resolver-typescript`。纯 JS 项目可使用 ESLint 默认解析器及适合 JS 的 resolver，不必为本指南引入 TS。

`package.json` 中提供可退出的 CI 命令，禁止 watch 模式，例如：

```json
{
  "scripts": {
    "lint": "eslint src",
    "test:ci": "vitest run"
  }
}
```

测试命令按实际框架填写；这里只示例 Vitest，不强制选型。新增禁止依赖和高复杂度反例，验证 ESLint 确实报错，并核对别名导入不会绕过目录约束。

## 2. 接入统一入口

在现有 `quality-gates.json` 保留 `python` 配置，合并顶层 `commands`：

```json
{
  "commands": [
    ["npm", "run", "lint"],
    ["npm", "run", "test:ci"]
  ]
}
```

这是配置片段，不是完整文件。每个命令都是 argv 数组，按顺序执行，非零结果阻断门禁；不调用 shell、不接受 `&&` 字符串，也不解释环境变量或重定向。命令本身仍是受信任的项目代码，接入前必须审核。

- 工作区模式在项目根目录执行，需要事先安装锁定依赖。
- `--staged`／`--revision` 在临时导出的快照根目录执行，使用该快照的命令配置。
- 未跟踪的 `node_modules`、虚拟环境及 `.git` 不随导出复制；不能偷偷链接工作区依赖或拿工作区代码冒充快照。
- 如需在快照中安装依赖，须明确授权并显式加入 `npm ci --ignore-scripts` 等受控准备命令；这可能联网且增加 hook 耗时，不是默认行为。原生依赖需要安装脚本时另行评估，不能盲目忽略或放开。
- 若应用测试必须访问 `.git`、数据库或系统工具，应配置隔离的 CI 检出与运行环境，并记录限制，不在失败时自动跳过。
- Python 工具测试会把当前测试根目录的 `scripts/` 加入子进程 `sys.path`，支持 `from check_file_lines import ...`；应用包仍应使用明确的包导入和依赖安装。

## 3. 目标项目 CI 模板

初始化器复制到 `examples/` 的两个示例：

- `examples/github-actions-quality.yml`：审查后合并到 `.github/workflows/quality.yml`。
- `examples/gitlab-ci-quality.yml`：审查后合并到 `.gitlab-ci.yml`。

不会自动覆盖已有 CI 或修改远端设置。根据应用补充锁定依赖及数据库服务，固定运行时；镜像发布场景应核对镜像摘要。GitHub 模板使用明确提交的 action；GitLab 镜像 tag 建议换成项目批准的 digest。

GitHub hosted runner 可直接运行，不要求 Docker。GitLab 示例适用于支持该镜像的 Docker／Kubernetes runner；shell runner 需预装 Python 3.12+ 和 Git。是否需要容器取决于应用依赖和环境一致性要求，不是 Skill 强制要求。

启用流水线后，还需实际验证失败不能合并，并设置主分支保护、必要检查和审核要求。仅有 YAML 文件或一次绿色结果，不代表远端已经强制保护。

## 4. 旧项目渐进接入

不把全局上限从1000调成2000或1500。建议分阶段：

1. **只读盘点**：从旧项目 Git 根运行 Skill 内的行数脚本，不需先复制全部工具：

   ```bash
   report=$(mktemp)
   status=0
   python3 ~/.agents/skills/engineering-guardrails/assets/project-kit/scripts/check_file_lines.py > "$report" 2>&1 || status=$?
   printf 'exit=%s; report=%s\n' "$status" "$report"
   ```

   报告逐文件列出实际行数；非零结果保留，不能宣布通过。盘点输出放在仓库外，避免污染扫描。

2. **登记技术债**：按下面格式记录，不添加隐藏排除项：

   | 文件 | 实际行数／复杂度 | 负责人 | issue | 截止日期 | 拆分方案 | 状态 |
   | --- | --- | --- | --- | --- | --- | --- |
   | `src/legacy.py` | `<实际值>` | `<负责人>` | `<issue链接>` | `<日期>` | `<职责拆分>` | 待处理 |

3. **迁移分支整改**：先处理高风险和活跃文件，新增代码遵守1000行；声明真实模块边界，保持业务回归，不机械分片。
4. **小范围试运行**：在独立迁移流水线观察并修复问题，明确标为非阻断盘点，不能冒充已启用全仓库门禁。
5. **全量强制**：存量达到要求后启用提交／推送检查及远端必要检查。

确需临时例外时，必须由用户明确批准具体文件、负责人、issue、期限和退出条件；本工具目前没有自动豁免／基线功能，不能靠配置假装已经支持，也不能为了放行而静默调高全局阈值。

## 5. 为什么暂不提供 --diff

全量依赖图才能发现跨文件循环；只检查修改文件可能漏掉未改动模块形成的环。配置、源码根和模块归属变化也可能影响未改文件。当前没有 `--diff` 模式，不把性能优化包装成同等保障。

现有 pre-push 会按相同 SHA 去重。同一提交推送到多个分支只验证一次。大型项目可在 CI 使用有明确定义的提交／依赖缓存和测试分组，但仍应保留全量架构检查及必要的全量回归，新增增量功能前先建立不漏检的测试。

## 6. 平台范围

所有 CLI 在执行前要求 Python 3.12+。Git hook 仅承诺 POSIX shell 环境；Windows 使用 WSL2。原生 Windows hook 安装会明确拒绝，不依靠 chmod 假装安装成功。

初始化器拒绝目标及父目录的 symlink／junction，原生 Windows 不尝试设置 POSIX 执行位。junction 拦截有模拟测试，但未完成原生 Windows 全流程验收；不能将 Linux 测试结果扩展成 Windows 兼容声明。
