# 贡献说明

开始前阅读根目录 [AGENTS.md](AGENTS.md)；它是唯一具有约束力的通用 Agent 工作流入口。本文件面向人类贡献者，不建立第二套规则权威。

复杂、跨模块或有歧义的工作优先创建 GitHub Issue；目标清晰、低风险且易回滚的小任务可使用当前会话中的明确人类授权。两条路径都要求一个任务对应一个 jj change，并使用短生命周期 bookmark。

## 本地工具与入口

本仓库当前以 Jujutsu 0.43、Git 2.54、pnpm 11、Python 3.11 和 uv 为验证基线。Windows 上已验证的完整入口是显式调用 Git Bash：

```powershell
& 'C:\Program Files\Git\bin\bash.exe' scripts/validate.sh
```

仓库没有承诺 PowerShell 7 委托入口；如果本机 `bash` 优先解析到 WSL，请显式使用 Git Bash。工具版本变化后应重新验证，不得沿用旧结论。

## Jujutsu 任务生命周期

新任务开始前先同步并检查工作区，不要覆盖来源不明的改动：

```bash
jj git fetch
jj status
jj bookmark list --all
jj log -n 5
```

若 `main`、`main@origin` 或目标 bookmark 存在冲突，先停止并确认目标，不要猜测或强推。复杂任务从已记录 Issue 创建单一 change；低风险任务使用当前会话的明确授权：

```bash
jj new main -m "issue #<number>: <short description>"
jj bookmark create codex/issue-<number>-<name> -r @
```

实现和验证期间定期运行 `jj status`、`jj diff --stat` 与 `jj diff`。Jujutsu 不存在“当前 bookmark”；创建子 change 或移动 revision 后，必须用 `jj bookmark list --all` 确认任务 bookmark 仍指向预期 change。

首次 push 前必须满足根部 `AGENTS.md` 的授权、完整 diff、自审和验证门禁。普通 push 使用任务 bookmark，push 被拒绝、bookmark 分叉或 rebase 冲突时不得 force push：

```bash
jj git push --remote origin --bookmark codex/issue-<number>-<name>
```

bookmark 首次发布后，restack 或改写该 change 会影响已发布历史；只有任务级授权仍覆盖相同远端、Issue、bookmark、base、PR 和范围时才能继续普通更新，否则先重新取得授权。任何 force push、已发布历史重写、远端删除或目标变化都需要单独授权。

人类完成 Squash Merge 后，默认只清理本地 bookmark：

```bash
jj bookmark forget codex/issue-<number>-<name>
```

删除远端 bookmark 是独立的外部破坏性动作，必须另行由人类决定并在执行前 dry-run；Agent 不自行 merge、release 或删除远端数据。

## 验证与 Pull Request

只修改已记录范围内的文件，不覆盖来源未确认的改动。根据改动范围运行聚焦测试；push 前的完整入口为：

```bash
bash scripts/validate.sh
```

PR 必须如实记录任务来源、结果、验证、人工 HMI/视觉证据（如适用）、范围、风险、后续项和 Agent 自审。当任务说明已记录远端、Issue/授权来源、bookmark、base、允许范围及 push/PR 权限时，Agent 可在同一边界内 push、创建或更新关联 PR，无须重复申请；任何实质边界变化都回到根部 `AGENTS.md` 的重新授权规则。只有人类决定是否 Squash Merge，merge 和 release 不属于该授权。

本仓库的最小单 Agent 工作流采用自 [OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)；采用记录和许可证边界见 [docs/development.md](docs/development.md)。
