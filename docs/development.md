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
| `CONTROL_ENABLED` | 本地 Control 端点命令开关；默认关闭，显式 `true` 才启用 | `false` |

`local`、`api` 是保留的 `APP_MODE` 名称，当前没有真实运行路径，因此会与其他非法值一样明确拒绝启动。`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`YOLO_MODEL_PATH`、`DEMO_VIDEO_PATH` 也仅为后续能力保留，当前运行时不读取。后端健康接口只返回经过验证的模式，不返回 `.env` 内容或秘密。

HTTP 命令路由 `/api/v1/commands/{endpoint}` 由服务端从路径解析端点上下文；请求体中的 `endpoint`/`source` 仅作为一致性声明，不一致返回 403 `endpoint_mismatch`。这能避免仅修改请求体就切换权限，但不是身份认证：可信本地客户端仍可选择其他端点路径。当前单用户演示环境不引入账户、令牌或多租户隔离；Control 命令默认禁用，只有显式设置 `CONTROL_ENABLED=true` 才开放。

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
| 前端 lint / 测试 / 构建 | `pnpm --filter @supersonic/frontend lint`；`test --run`；`build` | 前端静态、行为和生产构建验证 |
| 后端 lint / 测试 | `pnpm lint:backend`；`pnpm test:backend` | Ruff 与 pytest |
| PostgreSQL 集成测试 | `pnpm test:backend:integration` | 需要显式提供安全的 `TEST_DATABASE_URL`，验证 migration、约束与仓储实现 |
| 全量检查 | `pnpm check` | Lint、单元测试与前端构建 |
| 仓库验证 | `bash scripts/validate.sh` | Markdown、YAML、Shell/mode 与 `pnpm check` |
| GP05 运行态冒烟 | `pnpm smoke` 或 `pnpm smoke:gp05` | 启动真实 FastAPI 进程并验证四客户端、命令收敛、reset 与 reconnect |
| 旧 Mock 冒烟 | `pnpm smoke:legacy` | 要求端口 8000 已有服务，仅覆盖旧 Mock HTTP 和 `/ws/simulation` |

### PostgreSQL 集成测试边界

`DATABASE_URL` 是供未来 composition 使用的可选运行配置；本 Slice 不把 PostgreSQL
adapter 接入 Router，缺失该变量时现有 Mock HMI 继续无数据库运行。

`TEST_DATABASE_URL` 只供显式 PostgreSQL 集成测试使用。目标数据库名必须以 `_test`
结尾，且不能与进程级 `DATABASE_URL` 相同；测试会重建该数据库的 `public` schema，
因此不得指向开发、演示或生产数据。重建还要求 `SUPERSONIC_ALLOW_TEST_DB_RESET` 精确
设为 `1`。本地开发不要求 Docker，开发者可以使用自行提供的 PostgreSQL，并显式运行：

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://supersonic:replace-me@127.0.0.1:5432/supersonic_test'
$env:SUPERSONIC_ALLOW_TEST_DB_RESET='1'
pnpm test:backend:integration
```

`pnpm check` 与 `scripts/validate.sh` 保持无数据库；`pnpm test:backend:integration`
才需要数据库。CI 使用临时 PostgreSQL 18.4，并在仓库验证后强制运行集成测试，随后
才运行 GP05 smoke。

Migration 与 CI 通过只证明当前持久化基础的相应自动化检查通过，不代表登录、RBAC、
审计运行时、UI、LAN HTTPS、备份恢复或部署已经完成。

### GP05 Smoke 的边界

`pnpm smoke` 会自行选择动态本地端口，显式启用测试进程的 Control 命令，并在硬超时内完成以下验证：

- 四个 `gp05.v1` WebSocket 客户端同时在线；
- Center 与 Passenger 命令后所有客户端收敛，且 Passenger 命令不改变驾驶关键状态；
- reset 创建新 session 后连接状态正确；
- reconnect 获取最新完整 snapshot，不回放旧 session；
- Passenger 的越权命令返回 `command_forbidden` 且不改变 revision；
- 无论成功或失败，Uvicorn 子进程和 WebSocket 都会被有界清理。

该 Smoke 不替代前端损坏 WebSocket 数据容错的组件测试，也不覆盖视觉回归、性能、外部地图或部署环境。GitHub Actions 在仓库验证后单独运行 `pnpm smoke:gp05`；旧 Mock 链路仍可通过 `pnpm smoke:legacy` 手动验证。

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

## TheMasterplan 采用记录

来源: [TheMasterplan](https://github.com/OasisSaber/TheMasterplan) `v3.0.0` / `6e49aeeaa2eeaa8ce9be2d81a2fa8f5ba88bef18`
采用范围: 完整模板采用（AGENTS.md + core/ + profiles/ + adapters/ + 本地维护 CI + 薄 Skill 加载入口）
采用日期: 2026-08-03
首次演练任务: 当前会话明确人类授权（采纳 TheMasterplan 作为项目工作流）
Jujutsu 版本: `0.43.0`
Git 版本: `2.54.0`
平台与验证入口: Windows / Git Bash（`bash scripts/validate.sh`）
验证状态: VERIFIED（Windows / Git Bash 入口；首次演练 PR #39 已合并；本项目不承诺 PowerShell 7 委托入口）

该项目工作流是旧 [AgenticWonderwall](#agenticwonderwall-采用记录) 采用基线的后续品牌与版本演化；
两条采用记录并存用于追溯。工作流的 MIT 来源许可证仅适用于实际派生的工作流脚本与文本，
不自动改变本 HMI 毕业设计项目整体的许可状态，声明见 [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。

首次演练 PR: <https://github.com/OasisSaber/Supersonic/pull/39>

## AgenticWonderwall 采用记录

- 来源：[OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)
- 采用基线：`689d4edb8aacc1fc7a277da89efed05199b75edb`
- 采用日期：2026-07-23
- 首次演练任务：GitHub Issue #4 与对应 Pull Request

该工作流的 MIT 来源许可证仅适用于实际派生的工作流脚本与文本，不自动改变本 HMI 毕业设计项目整体的许可状态。具体声明见 [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。

详细规范见 [`DEVELOPMENT_STANDARDS.md`](./DEVELOPMENT_STANDARDS.md)。
