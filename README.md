# Supersonic：智能座舱多屏协同 HMI

Supersonic 是面向毕业设计的本地多屏智能座舱 HMI。React + TypeScript
负责 Cluster、HUD、Center、Passenger、Overview 和 Control 六个端点；FastAPI
维护唯一权威业务状态，HTTP 承载命令，WebSocket 广播完整 `gp05.v1` 快照。

## 项目定位

当前运行形态是一台 Windows 主机上的**本地、单用户、可信环境 Mock 原型**。
它不是公共互联网服务、量产车载系统或企业级多租户平台。

当前实现包括：

- `gp05.v1` TypeScript/Pydantic 合同；
- 六端点 GP22 第一轮语义 Token、共享 UI 原语和端点级信息层级；
- Overview 严格只读，Control 通过服务端命令修改状态；
- 本地确定性路线、模拟风险生命周期和副驾协作；
- session/revision、reset/reconnect、非法消息和端点权限验证；
- 后端 Policy、State Factory、Transitions、Broker、Service、Router 分层；
- Ruff、pytest、ESLint、Vitest、TypeScript 构建、项目验证和真实进程 Smoke。

Windows 视觉证据已经覆盖主要正常、导航、接管、确认、恢复、Day/Night、
数据域离线、`systemMode=offline`、`systemMode=stale` 与实际后端/WebSocket
连接中断。数据域离线、系统模式与传输状态分别记录，不能相互替代。

## 当前未实现

- PostgreSQL 身份、会话、RBAC、审计和恢复；
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
仅保留给旧 simulation Hook。完整配置合同见 `docs/development.md`。

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

## 当前推进顺序

1. 完成 PR #45 Code Review 修复与本地验证；
2. 使用仓库模板更新 PR body，并等待 GitHub Actions 独立验证；
3. 完成最终 Code Review，由人类决定是否合并并冻结 GP22 第一轮 UI；
4. 评审 PostgreSQL / RBAC / Audit 最小纵向切片；
5. G3 通过后实施登录、会话、审计、撤销和备份恢复；
6. 再分别立项真实地图、VehicleVision、AI 语音、多显示部署和 Web3D。

## 项目入口

| 内容 | 入口 |
| --- | --- |
| 当前范围与非目标 | `docs/project/DECISION_BASELINE.md` |
| 当前进度和验证 | `docs/project/PROJECT_PROGRESS.md` |
| 执行门与路线 | `docs/project/IMPLEMENTATION_ROADMAP.md` |
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
