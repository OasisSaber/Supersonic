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

- 根部 `AGENTS.md` 是唯一具有约束力的通用 Agent 工作流入口；项目架构、冻结决策、测试和交付资料继续由现有项目文档维护。
- 开始前读取根目录 `AGENTS.md`，并按任务读取 `docs/project/` 下相关的决策、进度或路线文档。
- 进入目标目录前读取适用的局部 `AGENTS.md`；只改任务范围内的文件，不覆盖来源未确认的已有改动。
- 文档改动校验链接、路径、事实与术语；代码改动按影响层运行对应命令。
- 完成后如实记录实际验证结果；未执行的验证不得标记为通过。
- 复杂任务使用 GitHub Issue；小型低风险任务可以使用当前会话中的明确人类授权。一个任务对应一个 jj change 和短生命周期 bookmark。
- 已记录远端、任务来源、bookmark、base、文件范围与 push/PR 权限的任务级授权，覆盖同一边界内的普通 push 与关联 PR 更新；边界变化、验证失败或破坏性操作必须按根部 `AGENTS.md` 重新授权。merge 和 release 只由人类决定。

## AgenticWonderwall 采用记录

- 来源：[OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)
- 采用基线：`689d4edb8aacc1fc7a277da89efed05199b75edb`（AgenticWonderwall v1.0.0 准备提交；执行时 `main` 同一提交）
- 采用日期：2026-07-23
- 首次演练任务：GitHub Issue #4 与对应 Pull Request

该工作流的 MIT 来源许可证仅适用于实际派生的工作流脚本与文本，不自动改变本 HMI 毕业设计项目整体的许可状态。具体声明见 [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。

详细规范见 [`DEVELOPMENT_STANDARDS.md`](./DEVELOPMENT_STANDARDS.md)。
