# 项目进度

- 最后更新：2026-08-08
- 远端主线：`main@71b4c46ee3816b4c8e0834f25ef4eb363be034f1`
- 已完成任务：Issue #44、PR #45
- 当前阶段：GP22 第一轮 UI 与 G1 视觉证据已合入，准备独立 G3 架构评审 Issue

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

主线最近完整验证来自 PR #45：后端 88 tests、前端 46 tests、构建、
`bash scripts/validate.sh` 和 `pnpm smoke` 通过；合并后 main CI 也已独立通过。

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
| 平台领域端口 | `REVIEW_FIXED_NOT_WIRED` | 不接公开路由；审计结果与故障语义已修复并测试 |
| PostgreSQL / RBAC / Audit adapter | `G3_REVIEW_PENDING` | 先建独立 Issue 做架构评审，不得直接接线 |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于当前 G3 范围 |

## 4. 下一步

1. 为 PostgreSQL / server session / RBAC / Audit 最小纵向切片创建独立 G3 Issue；
2. 完成 ERD、身份与权限、审计、故障、migration、恢复和测试策略评审；
3. 由人类批准 G3 决策并指定首个 G4 Slice，未批准前不接公开 Router。
