# Supersonic：智能座舱多屏协同 HMI

Supersonic 是面向毕业设计的本地多屏智能座舱 HMI。React + TypeScript 负责六个屏幕端点，FastAPI 维护唯一权威业务状态，HTTP 承载命令，WebSocket 广播完整 `gp05.v1` 快照。

## 当前已实现

- Cluster、HUD、Center、Passenger、Overview、Control 六端点；
- GP22 第一轮语义 Token、共享 UI 原语与端点级信息层级；
- Overview 严格只读，Control 通过服务端命令修改状态；
- 本地确定性路线、模拟风险生命周期和副驾协作；
- session/revision、reset/reconnect、非法消息和端点权限验证；
- 后端 Policy、State Factory、Transitions、Broker、Service、Router 分层；
- Ruff、pytest、ESLint、Vitest、TypeScript 构建、项目验证和真实进程 Smoke。

当前运行形态仍是**一台 Windows 主机上的本地、单用户、可信环境 Mock 原型**。GP22 第一轮代码迁移已完成；Windows 六端点视觉验收截图与状态矩阵已完成（见 [docs/VISUAL_ACCEPTANCE_MATRIX.md](docs/VISUAL_ACCEPTANCE_MATRIX.md)），Figma 逐屏对照尚未完成。

## 当前未实现

- PostgreSQL 身份、会话、RBAC、审计与恢复；
- 真实地图 Provider；
- 真实 VehicleVision；
- AI 语音；
- 多显示部署编排；
- Web3D。

不得把 `local_fallback`、`simulated_event` 或静态视觉表述为真实地图、真实摄像头推理或量产车辆能力。

## 快速开始

```powershell
Copy-Item .env.example .env
.\scripts\setup.ps1
pnpm dev
```

## 验证

```powershell
pnpm check
pnpm smoke
```

跨层改动在提交前运行：

```bash
bash scripts/validate.sh
```

## 当前推进顺序

1. 同步 README、进度和路线文档；
2. 完成 Windows 六端点视觉矩阵与 GP22 Figma 对照；
3. 修复有证据的视觉偏差并冻结 GP22 第一轮 UI；
4. 评审 PostgreSQL / RBAC / Audit 最小纵向切片；
5. 评审通过后实施登录、会话、审计、撤销和备份恢复；
6. 再分别立项真实地图、VehicleVision、AI 语音、多显示部署和 Web3D。

权威状态见 `docs/project/PROJECT_PROGRESS.md`，执行门见 `docs/project/IMPLEMENTATION_ROADMAP.md`，Agent 规则见 `AGENTS.md`。
