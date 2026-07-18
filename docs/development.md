# 开发与验证

## 环境与命令

```powershell
.\scripts\setup.ps1
pnpm dev
pnpm lint
pnpm test
pnpm build
pnpm smoke
pnpm check
```

| 任务 | 命令 |
| --- | --- |
| 前端 lint / 测试 / 构建 | `pnpm --filter @cockpit/frontend lint`；`test --run`；`build` |
| 后端 lint / 测试 | `pnpm lint:backend`；`pnpm test:backend` |
| 全量检查 | `pnpm check` |
| 运行态冒烟 | `pnpm smoke` |

## 工作方式

- 使用 jj 管理所有可变版本操作；Git 仅用于只读检查。
- 开始前读 `AGENTS.md`、当前 handoff 和相关任务合同；完成前更新 handoff。
- 只改任务范围内的文件；发现已有其他所有者的改动时停止。
- 文档改动校验链接、路径、事实与术语；代码改动按影响层运行对应命令。
- 实现前按 [`ai-collaboration/OPENCODE_FIRST_WORKFLOW.md`](ai-collaboration/OPENCODE_FIRST_WORKFLOW.md) 路由；适合委派的 L0/L1 叶子任务默认先起草 OpenCode 合同。
- push 与 PR 遵守 P0 外部门禁：由 Codex 先展示完整摘要，Oasis 分别精确批准；失败后不得自动重试。

详细规范在 `ai-collaboration/DEVELOPMENT_STANDARDS.md`，交接格式在 `ai-collaboration/HANDOFF_PROTOCOL.md`。不要在此文件重复协议、设计合同或历史决策。
