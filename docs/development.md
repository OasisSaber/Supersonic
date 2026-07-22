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

- 开始前读取根目录 `AGENTS.md`，并按任务读取 `docs/project/` 下相关的决策、进度或路线文档。
- 进入目标目录前读取适用的局部 `AGENTS.md`；只改任务范围内的文件，不覆盖来源未确认的已有改动。
- 文档改动校验链接、路径、事实与术语；代码改动按影响层运行对应命令。
- 完成后如实记录实际验证结果；未执行的验证不得标记为通过。
- push、PR、merge 和 release 每次均需明确授权。

详细规范见 [`DEVELOPMENT_STANDARDS.md`](./DEVELOPMENT_STANDARDS.md)。
