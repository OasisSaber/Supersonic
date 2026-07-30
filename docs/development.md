# 开发与验证

## 环境与命令

先从示例创建仓库根目录配置：

```powershell
Copy-Item .env.example .env
```

`.env` 是前后端唯一约定的项目配置文件位置，并已被 Git 忽略。FastAPI 先读取该文件，再以启动进程中的同名环境变量覆盖文件值；Vite 通过 `envDir` 从同一位置加载 `VITE_*`。测试使用临时环境文件或临时进程值，不依赖开发者本机 `.env`。

| 变量 | 当前行为 | 缺失时默认值 |
| --- | --- | --- |
| `APP_MODE` | FastAPI 运行模式；当前只实现并接受 `mock` | `mock` |
| `VITE_API_URL` | GP05 HTTP 命令、snapshot 与 `/ws/v1/cockpit` 的 FastAPI 基地址 | `http://127.0.0.1:8000` |
| `VITE_WS_URL` | 仅供旧 `/ws/simulation` Hook 使用，不控制 GP05 主链路 | `ws://127.0.0.1:8000/ws/simulation` |

`local`、`api` 是保留的 `APP_MODE` 名称，当前没有真实运行路径，因此会与其他非法值一样明确拒绝启动。`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`YOLO_MODEL_PATH`、`DEMO_VIDEO_PATH` 也仅为后续能力保留，当前运行时不读取。后端健康接口只返回经过验证的模式，不返回 `.env` 内容或秘密。

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
