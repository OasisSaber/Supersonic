# Supersonic：智能座舱多屏协同 HMI

> **Status: `FROZEN / MAINTENANCE_ONLY`**
> **G5 quality baseline frozen**: 2026-08-31 (decision head `d0b2bafdeea9af69210b0640e5945abe34ffd630`, PR #94)
> **Active graduation-design development moved to OasisSaber/Pioneer**: 2026-09-04
> See [PROJECT_CLOSURE.md](docs/project/PROJECT_CLOSURE.md) and [PROJECT_LESSONS_LEARNED.md](docs/project/PROJECT_LESSONS_LEARNED.md).

Supersonic 是面向毕业设计的本地多屏智能座舱 HMI。React + TypeScript
负责 Cluster、HUD、Center、Passenger、Overview 和 Control 六个端点；FastAPI
中的 `CockpitService` 维护唯一权威座舱实时状态，HTTP 承载命令，WebSocket 广播
完整 `gp05.v1` 快照。

## 项目定位

当前运行形态是一台 Windows 主机上的**本地、可信环境 Mock 原型**。配置 PostgreSQL
后，本地 Platform 界面支持 admin、operator 和 viewer 身份；这不等于公共互联网服务、
量产车载系统或企业级多租户平台。

当前实现包括：

- `gp05.v1` TypeScript/Pydantic 合同；
- 六端点 GP22 第一轮语义 Token、共享 UI 原语和端点级信息层级；
- Overview 严格只读，Control 通过服务端命令修改状态；
- 本地确定性路线、模拟风险生命周期和副驾协作；
- session/revision、reset/reconnect、非法消息和端点权限验证；
- 后端 Policy、State Factory、Transitions、Broker、Service、Router 分层；
- 配置 PostgreSQL 后启用的用户、Platform Session、服务端 Principal/RBAC 与 Audit；
- `/platform` 的登录、admin 管理界面，以及 operator/viewer 的角色范围界面；
- `pg_dump` 备份、隔离 `*_restore_test` 恢复工具和脱敏恢复验收证据；
- Ruff、pytest、ESLint、Vitest、TypeScript 构建、项目验证和真实进程 Smoke。

Windows 视觉证据已经覆盖主要正常、导航、接管、确认、恢复、Day/Night、
数据域离线、`systemMode=offline`、`systemMode=stale` 与实际后端/WebSocket
连接中断。数据域离线、系统模式与传输状态分别记录，不能相互替代。
Session 撤销后的 WebSocket 主动关闭由单进程 registry 传播，不是多实例撤销能力。

## 未实现规划能力（收口前未实现 / 已不再作为活跃路线）

以下规划能力在 2026-09-04 项目收口前**未完成实现**，且随着项目进入维护状态，已不再属于 Supersonic 的活跃路线：

- 真实地图 Provider；
- 真实 VehicleVision；
- AI 语音；
- 多显示部署编排；
- Web3D。

不得把 `local_fallback`、`simulated_event` 或静态视觉表述为真实地图、真实摄像头
推理或量产车辆能力。

## 快速开始

```powershell
Copy-Item .env.example .env
.\scripts\setup.ps1
pnpm dev
```

运行时配置统一放在仓库根目录 `.env`。该文件已被 Git 忽略；不要提交密钥、模型
路径或私人素材路径。当前后端只实现 `APP_MODE=mock`，其他值会明确拒绝启动。
`VITE_API_URL` 控制前端访问 FastAPI 的 HTTP 与 WebSocket 基地址；`VITE_WS_URL`
仅保留给旧 simulation Hook。设置 `DATABASE_URL` 后会接线 Platform 用户、Session、
RBAC 与 Audit；缺失时现有 Mock HMI 仍可无数据库运行，但 `/platform` 不可用。
完整配置合同见 `docs/development.md`。

## 验证

```powershell
pnpm check
pnpm smoke
```

跨层改动在提交前还必须运行：

```bash
bash scripts/validate.sh
```

GitHub Actions 必须独立通过。PR 描述中的本地验证记录不能替代 CI 结果。

## 当前推进状态：已收口维护（FROZEN / MAINTENANCE_ONLY）

- **G4 平台纵向切片**：已完成 Platform 登录、Session、RBAC、Audit、管理操作与备份恢复（PR #62 / PR #64）。
- **G5 质量复审与冻结**：G5 七轴复审结论为 `FREEZE_READY`（[G5 Final Re-Review](deliverables/g5-review/G5_FINAL_RE_REVIEW.md)），人类已于 2026-08-31 正式宣告 G5 冻结（PR #94，冻结基线 `d0b2bafdeea9af69210b0640e5945abe34ffd630`）。
- **项目正式收口（2026-09-04）**：因毕业设计主线调整至 Pioneer，Supersonic 活跃产品研发正式结束，仓库进入 `FROZEN / MAINTENANCE_ONLY` 维护状态。真实地图、VehicleVision、AI 语音、多显示部署和 Web3D 保持为历史规划证据，不再作为 Supersonic 实施路线。
- 完整收口决策见 [PROJECT_CLOSURE.md](docs/project/PROJECT_CLOSURE.md)，工程与协作经验总结见 [PROJECT_LESSONS_LEARNED.md](docs/project/PROJECT_LESSONS_LEARNED.md)。

### 历史推进记录（保留，用于追溯）

以下是历史各阶段演进记录，仅用于追溯：

1. PR #45 已由人类 Squash Merge 到 `main`，GP22 第一轮 UI、Review 修复与视觉证据已进入主线；
2. 创建独立 G3 Issue，只评审 PostgreSQL / server session / RBAC / Audit 最小纵向切片；
3. 人类批准 G3 决策并指定首个 Slice 后，才进入 G4 实现；
4. G4 小步实施登录、会话、审计、撤销和备份恢复，每个 Slice 独立验证与评审；
5. 原计划的真实地图、VehicleVision、AI 语音、多显示部署和 Web3D 在项目收口前未实现，已转为历史规划记录。

## 项目入口

| 内容 | 入口 |
| --- | --- |
| 当前范围与非目标 | `docs/project/DECISION_BASELINE.md` |
| 当前进度和验证 | `docs/project/PROJECT_PROGRESS.md` |
| 执行门与路线 | `docs/project/IMPLEMENTATION_ROADMAP.md` |
| 项目收口决策 | `docs/project/PROJECT_CLOSURE.md` |
| 工程与协作经验总结 | `docs/project/PROJECT_LESSONS_LEARNED.md` |
| 系统边界 | `docs/architecture.md` |
| 开发与配置 | `docs/development.md` |
| Windows 视觉证据 | `docs/VISUAL_ACCEPTANCE_MATRIX.md` |
| Agent 工作规则 | `AGENTS.md` |

## 目录

- `apps/`：运行时前端与后端；
- `contracts/`：跨端协议合同；
- `docs/`：决策、架构、验证和毕设证据；
- `deliverables/`：阶段交付物；
- `scripts/`、`tests/`：开发和验证工具。

默认不要读取或提交依赖目录、缓存、虚拟环境、临时目录和构建产物。

## 使用许可

本仓库用于毕业设计作品展示与技术审查。当前未授予复制、再分发、修改或商业
使用许可；第三方依赖与引用资料分别适用其原有许可和条款。

### Vision 许可证门禁

当前版本未采用 Ultralytics/YOLO：运行代码没有导入或调用 Ultralytics，也没有提交
模型权重或分发包含该组件的发行物。Ultralytics 已从
`apps/backend/pyproject.toml` 的 `vision` 可选组和 `apps/backend/uv.lock` 移除；
未来重新加入前必须完成许可核验。

如果未来启用 Ultralytics/YOLO，必须先在
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 和
[`docs/08-data-and-license-log.md`](docs/08-data-and-license-log.md) 记录准确版本、
模型来源和授权证据，并在 AGPL-3.0 全项目开源路线与 Ultralytics Enterprise/R&D
许可路线之间作出明确选择。
