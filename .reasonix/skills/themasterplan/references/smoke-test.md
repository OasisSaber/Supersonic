# 采用与烟雾测试清单

采用 TheMasterplan 工作流的项目应在部署本 skill 后完成以下工作。记录实际
使用的来源版本（Release tag 或完整 commit SHA），不得因为示例而声称采用了
未实际使用的版本。

## 工具与平台基线

- Jujutsu 命令已在 `0.43.0` 上核对；更高版本必须在采用时重新完成烟雾测试。
- Git `2.34.0` 或更高版本；Windows 使用包含 Git Bash 的 Git for Windows。
- `VERIFIED`：Ubuntu GitHub Actions 中的 Bash 权威入口与 PowerShell 7 委托入口。
- `PARTIAL`：macOS Bash 与真实 Windows PowerShell 7 + Git for Windows；采用时
  必须在目标平台运行完整烟雾测试。
- 默认远端名为 `origin`、受保护分支为 `main`。采用项目使用其他名称时必须
  统一替换。

> Windows PowerShell 转义提示：命令示例为 Bash 风格。PowerShell 中 `@`
> 是自动变量展开符，`jj bookmark create <name> -r @` 会解析失败；照抄时把
> 参数写成引号形式：`-r '@'`。Bash 中两种写法均可。

采用前运行 `jj --version` 与 `git --version`，把真实版本、操作系统和验证状态
记录在演练结果中。不得仅因仓库提供入口就把 `PARTIAL` 平台表述为已验证。

## 部署步骤

1. 复制本 skill 目录（`SKILL.md` 与 `references/`）到采用项目的 skill 目录。
2. 在采用项目规则文件的“项目事实”中填写项目目标、技术栈、默认分支和真实
   验证命令。
3. 确认采用项目的权威验证入口（本项目为 `bash scripts/validate.sh`，
   显式 Git Bash 调用见 `CONTRIBUTING.md`）真实存在；不存在时
   必须删除或替换所有指向它的规则与链接，不得声明不存在的入口。
4. 由人类按项目需要配置 GitHub 保护规则（`main` 只接受 Pull Request、
   禁止 force push 与删除 `main`、只启用 Squash Merge、Agent 凭据无 merge 或
   release 权限）。
5. 记录来源版本、采用范围、采用日期与首次演练任务。
6. 完成一次低风险端到端烟雾测试（见下）。

保留一个通用规则入口，避免建立第二套相互冲突的通用规则。采用项目自身的
架构、安全、测试和交付资料按照权威顺序保留。

## 新仓库烟雾测试

维护者应在全新的采用仓库中完成一次真实但低风险的端到端演练：

- [ ] 记录 `jj --version`、`git --version`、操作系统、验证入口，以及开始时
      的 `VERIFIED` 或 `PARTIAL` 状态。
- [ ] 通过 `jj git clone`，或通过 `git clone` 后运行 `jj git init --colocate`。
- [ ] 运行 `jj git fetch --remote origin`，确认 `main`、`main@origin` 和
      `jj bookmark list --conflicted` 没有冲突。
- [ ] 用一个真实 Issue 或明确人类授权创建单独 jj change 与短期 bookmark。
- [ ] 做一处容易审阅和回滚的变更，运行 `bash scripts/validate.sh`；Windows
      显式使用 Git Bash 调用同一权威命令，macOS 在本机运行
      Bash 入口。
- [ ] 阅读完整 diff，只 push 任务 bookmark，并确认该 bookmark 已跟踪 `@origin`。
- [ ] 创建 Draft Pull Request，确认正文校验与仓库 CI 通过。
- [ ] 由人类决定并执行 Squash Merge；Agent 不执行 merge。
- [ ] fetch 最新 `main`，新建基于 `main` 的空 change，并用 `jj bookmark forget`
      完成本地清理。
- [ ] 若要删除仍存在的远端 bookmark，另行记录明确人类决定，先 dry-run，再
      执行远端删除。
- [ ] 将演练任务、PR、合并提交、验证结果和任何平台限制写入采用记录。

只有目标平台的完整烟雾测试通过后，才能把该平台从 `PARTIAL` 记录为采用项目
自身的 `VERIFIED`。

任一步出现 conflicted bookmark、push 拒绝、未经确认的远端差异或范围扩大时，
烟雾测试失败并停止；不得靠强推、自动冲突解决或跳过验证继续。

## 版本记录模板

```markdown
来源: TheMasterplan <release-tag-or-full-commit-sha>
采用范围: <完整模板 / 最小采用集合（AGENTS.md + core/ + profiles/…）/ 自定义文件集合>
采用日期: <YYYY-MM-DD>
首次演练任务: Issue #<number> / <human authorization reference>
Jujutsu 版本: <jj --version>
Git 版本: <git --version>
平台与验证入口: <OS / Bash / PowerShell 7>
验证状态: <VERIFIED / PARTIAL>
首次演练 PR: <URL>
```

Issue 与明确人类授权二选一。使用授权引用时，必须同时记录授权来源、目标和
范围。`PARTIAL` 只描述尚未在真实目标平台完成烟雾测试，不应被写成完整跨平台
支持。
