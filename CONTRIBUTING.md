# 贡献说明

开始前阅读根目录 [AGENTS.md](AGENTS.md)；它是唯一具有约束力的通用 Agent 工作流入口。本文件面向人类贡献者，不建立第二套规则权威。

复杂、跨模块或有歧义的工作优先创建 GitHub Issue；目标清晰、低风险且易回滚的小任务可使用当前会话中的明确人类授权。两条路径都要求一个任务对应一个 jj change，并使用短生命周期 bookmark。

只修改已记录范围内的文件，不覆盖来源未确认的改动。根据改动范围运行验证；完整入口为：

```bash
bash scripts/validate.sh
```

PR 必须如实记录任务来源、结果、验证、人工 HMI/视觉证据（如适用）、范围、风险、后续项和 Agent 自审。当任务说明已记录远端、Issue/授权来源、bookmark、base、允许范围及 push/PR 权限时，Agent 可在同一边界内 push、创建或更新关联 PR，无须重复申请；任何实质边界变化都回到根部 `AGENTS.md` 的重新授权规则。只有人类决定是否 Squash Merge，merge 和 release 不属于该授权。

本仓库的最小单 Agent 工作流采用自 [OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)；采用记录和许可证边界见 [docs/development.md](docs/development.md)。
