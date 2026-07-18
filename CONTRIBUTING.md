# 协作开发入口

本项目由人类作者、Codex和OpenCode共同开发。所有参与者使用同一套项目事实、开发标准和Jujutsu历史。

## 开始之前

1. 阅读根目录 `AGENTS.md`；
2. 阅读 `docs/ai-collaboration/CURRENT_HANDOFF.md`；
3. Agent任务还需读取不可变合同和本地runtime状态；
4. 运行 `jj status`、`jj workspace list` 与 `jj log -n 5`；
5. 确认当前workspace lease没有被另一所有者占用；
6. 用 `jj describe` 描述当前change。

OpenCode自动任务只能通过本地Supervisor启动：

```powershell
pnpm agent:status TASK-0001
pnpm agent:start TASK-0001
```

不要在OpenCode Desktop中直接打开Codex主工作区并要求其自主选择任务。

## 验证

```powershell
pnpm check
node --test tests/orchestration/supervisor.test.mjs
```

详细规范：

- `docs/ai-collaboration/DEVELOPMENT_STANDARDS.md`
- `docs/ai-collaboration/HANDOFF_PROTOCOL.md`
- `docs/11-jujutsu-workflow.md`

## 提交与推送

- 使用Jujutsu，不使用会改变状态的Git命令；
- 一个change对应一个任务；
- change描述采用 `design:`、`feat:`、`fix:`、`docs:`、`data:`、`chore:` 前缀；
- 推送、PR和Release必须得到用户明确授权。
