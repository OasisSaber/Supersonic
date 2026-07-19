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

- 开始前读 `AGENTS.md`、当前 handoff 和相关任务合同；完成前更新 handoff。
- 只改任务范围内的文件；发现已有其他所有者的改动时停止。
- 文档改动校验链接、路径、事实与术语；代码改动按影响层运行对应命令。
- push 与 PR 每次需单独明确授权。

详细规范见 `ai-collaboration/DEVELOPMENT_STANDARDS.md`。
