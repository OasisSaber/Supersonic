# 项目进度

- 最后更新：2026-08-16
- 远端主线：`main@5308850cefff016a67692c417d590c9ed5882868`
- 已完成任务：Issue #44、PR #45（GP22 G1/G2）；G3 架构评审 Issue #47 / PR #48；G4 平台切片 A–D（PR #50、#52、#54、#56、#58）
- 当前阶段：G4 平台纵向切片 A–D 已合入 `main`（PostgreSQL 持久化、identity/Platform Session、认证与 CORS 加固、审计持久化与回填、命令/WebSocket 集成）；剩余 session revoke、备份恢复等切片按 ROADMAP 继续

## 1. 已合并事实

| PR | 能力 | 状态 |
| --- | --- | --- |
| #31–#33 | 导航健康、Control、`gp05.v1` 真实进程 Smoke | 已合并 |
| #34–#38 | 平台方向、核心 Review 修复、进度与 Apple 资产评估 | 已合并 |
| #39–#40 | TheMasterplan v3 工作流及采用收尾 | 已合并 |
| #41 | 更名、风险状态机、HTTP/WS 竞态与合同收紧 | 已合并 |
| #42 | 远端仓库改名与旧 slug 清理 | 已合并 |
| #43 | GP22 六端点 UI 和后端事务式服务架构 | 已合并 |
| #45 | Quality Pack v3、平台领域端口、审计语义修复与 72 张 Windows 视觉证据 | 已合并 |
| #46 | PR #45 合并后进度同步 | 已合并 |
| #48 | G3 平台边界架构批准（Issue #47） | 已合并 |
| #50 | G4 Slice A：PostgreSQL 持久化基础（Issue #49） | 已合并 |
| #52 | G4：identity 与 Platform Session（Issue #51） | 已合并 |
| #54 | G4 Slice B：认证与 CORS 加固 | 已合并 |
| #56 | G4 Slice C：审计持久化（Issue #55） | 已合并 |
| #58 | G4 Slice D：命令/WebSocket 集成（Issue #57） | 已合并 |

主线最近完整验证来自 PR #45：后端 88 tests、前端 46 tests、构建、
`bash scripts/validate.sh` 和 `pnpm smoke` 通过；合并后 main CI 也已独立通过。
G3/G4 各 PR 的本地验证与 CI 结果以各自 PR 记录为准，本文不再逐条重复。

## 2. PR #45 已合并基线

PR #45 已由人类 Squash Merge 为 `71b4c46ee3816b4c8e0834f25ef4eb363be034f1`。
合并树与最终候选 `1b484703f5cb5ac9b0ae2d7fc0de5de4ff86dd5f` 完全一致；
Issue #44 已关闭，合并后 main CI 已完成 Validate 与 GP05 Smoke。

已修复的 Code Review 阻断项：

- 普通命令可能先修改权威状态，再因审计写入失败向调用者返回错误；
- fallback 把原始 succeeded/rejected 结果覆盖成 degraded；
- `app.main` 的兼容导出被移除；
- offline/stale 视觉矩阵混淆数据域状态与系统/连接状态；
- PR body 原不符合仓库模板，导致 CI 无法进入真实验证；现已修复并通过。

## 3. 当前模块状态

| 模块 | 状态 | 边界 |
| --- | --- | --- |
| `gp05.v1` 运行时 | `VERIFIED_MAIN_BASELINE` | 主线权威状态、权限、reset/reconnect 与 Smoke 已建立 |
| GP22 第一轮 UI | `VERIFIED_MAIN_G1` | 系统 offline/stale、连接中断与恢复证据及 CI 已进入主线 |
| PostgreSQL / Platform 层 | `G4_IMPLEMENTING` | G3 已批准；PostgreSQL adapter（database/ORM/audit sink/unit of work）、identity 与 Platform Session、认证与 CORS、审计持久化与回填、命令网关/WS 集成已合入 `main`；Router 已接线并有 wiring 测试 |
| G4 剩余切片 | `PLANNED` | session revoke、备份恢复等按 ROADMAP 顺序逐 Slice 实施 |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于当前 G4 范围 |

## 4. 下一步

1. 按 `IMPLEMENTATION_ROADMAP.md` G4 顺序继续剩余切片：session revoke → 备份恢复等，每个 Slice 独立 Issue/授权、jj change、验证与 PR；
2. G4 完成后进入 G5 最终 Code Review 与冻结检查（DECISION_BASELINE §10）；
3. 之后按决策基线分别立项真实地图、VehicleVision、AI 语音、多显示部署与 Web3D。
