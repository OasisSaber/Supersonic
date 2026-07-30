# 开发与验证

## 环境与命令

先从示例创建仓库根目录配置：

```powershell
Copy-Item .env.example .env
```

`.env` 是前后端唯一约定的项目配置文件位置，并已被 Git 忽略。FastAPI 读取该文件，再以启动进程中的同名环境变量覆盖文件值；Vite 通过 `envDir` 从同一位置加载 `VITE_*`。测试使用临时环境文件或临时进程值，不依赖开发者本机 `.env`。

| 变量 | 当前行为 | 缺失时默认值 |
| --- | --- | --- |
| `APP_MODE` | FastAPI 运行模式；当前只实现并接受 `mock` | `mock` |
| `VITE_API_URL` | `gp05.v1` HTTP 命令、snapshot 与 `/ws/v1/cockpit` 的 FastAPI 基地址 | `http://127.0.0.1:8000` |
| `VITE_WS_URL` | 仅供旧 `/ws/simulation` Hook 使用，不控制 `gp05.v1` 主链路 | `ws://127.0.0.1:8000/ws/simulation` |

`local`、`api` 是保留的 `APP_MODE` 名称，当前没有真实运行路径，因此会与其他非法值一样明确拒绝启动。`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`YOLO_MODEL_PATH`、`DEMO_VIDEO_PATH` 也仅为后续能力保留，当前运行时不读取。后端健康接口只返回经过验证的模式，不返回 `.env` 内容或秘密。

```powershell
.\scripts\setup.ps1
pnpm dev
pnpm lint
pnpm test
pnpm build
pnpm check
pnpm smoke
```

## 验证矩阵

| 任务 | 命令 | 当前含义 |
| --- | --- | --- |
| 前端 lint / 测试 / 构建 | `pnpm --filter @cockpit/frontend lint`；`test --run`；`build` | 前端静态、行为和生产构建验证 |
| 后端 lint / 测试 | `pnpm lint:backend`；`pnpm test:backend` | Ruff 与 pytest |
| 全量检查 | `pnpm check` | Lint、单元测试与前端构建 |
| 仓库验证 | `bash scripts/validate.sh` | Markdown、YAML、Shell/mode 与 `pnpm check` |
| 运行态冒烟 | `pnpm smoke` | 当前只覆盖旧 Mock HTTP 和 `/ws/simulation` |

### Smoke 的当前边界

现有 `pnpm smoke` 不证明：

- 四个 `gp05.v1` WebSocket 客户端同时在线；
- `/api/v1/commands` 后所有客户端收敛；
- reset 创建新 session 后连接状态正确；
- reconnect 获取最新完整 snapshot；
- 服务端端点上下文阻止身份伪造；
- 前端能拒绝损坏 WebSocket 数据。

Issue #14 负责真实 FastAPI 进程和四客户端 Smoke；Issue #11 定义 reset/reconnect 的正确行为；Issue #13 和 #19 分别负责权限上下文与前端消息容错。在 #14 完成前，PR 不得把 `pnpm smoke` 表述为完整四屏集成验证。

## 项目工程标准

当前仓库是本地、单用户、可信环境的毕业设计原型。代码应达到可重复开发、可测试和可答辩标准，但不要求提前建设公共云或企业多租户基础设施。

默认核心关注：

- 权威状态完整性；
- 四屏职责和命令边界；
- 可恢复的 HTTP/WebSocket 通信；
- 明确的 Mock、真实和降级标签；
- Windows 主机上的可重复启动；
- GitHub Actions 和本地验证一致。

只有在独立 Issue 明确触发时，才加入：

- MySQL 或其他持久化；
- 高德真实地图；
- Vision 模型和视频输入；
- Web3D；
- AI 服务；
- Electron/Tauri；
- 签名、公证、容器或公共部署设施。

不要因为依赖已经存在就把对应能力写成已实现或必须使用。

## 工作方式

- 根部 `AGENTS.md` 是唯一具有约束力的通用 Agent 工作流入口；
- 开始前读取当前 Issue 和相关 `docs/project/` 决策、进度或路线文档；
- 进入目标目录前读取适用的局部 `AGENTS.md`；
- 一个可独立实现、关联 PR 和关闭的问题使用一个 Issue；
- Tracker/路线文档只组织优先级，不保存长期未编号 Bug；
- 一个任务对应一个 jj change 和短生命周期 bookmark；
- 只改任务范围内文件，不覆盖来源未确认的已有改动；
- 完成后如实记录实际验证；未执行的检查不得标记为通过；
- 已记录远端、任务来源、bookmark、base、文件范围与 push/PR 权限的任务级授权，覆盖同一边界内的普通 push 与关联 PR 更新；
- 边界变化、验证失败后仍拟 push、force push、远端删除、仓库设置或其他破坏性操作必须重新授权；
- Merge、Release 和公开发布只由人类决定。

## Issue 优先级

- P0：数据和权威状态完整性；
- P1：核心产品正确性、答辩功能和明显运行时失败；
- P2：近期可靠性、内部权限与集成证据；
- Recommended：核心稳定后的增强；
- Conditional：只有学校、论文、部署或发行条件触发后实施；
- Not planned：与当前本地原型定位不符的通用平台工作。

具体顺序见 [`project/IMPLEMENTATION_ROADMAP.md`](project/IMPLEMENTATION_ROADMAP.md)。

## AgenticWonderwall 采用记录

- 来源：[OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)
- 采用基线：`689d4edb8aacc1fc7a277da89efed05199b75edb`
- 采用日期：2026-07-23
- 首次演练任务：GitHub Issue #4 与对应 Pull Request

该工作流的 MIT 来源许可证仅适用于实际派生的工作流脚本与文本，不自动改变本 HMI 毕业设计项目整体的许可状态。具体声明见 [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。

详细规范见 [`DEVELOPMENT_STANDARDS.md`](./DEVELOPMENT_STANDARDS.md)。