# 项目进度

- 最后更新：2026-08-08
- 远端主线：`main@e8610d8712f2fc878525ee2e62cd88693dbc7396`
- 开放任务：Issue #44、Draft PR #45
- 当前阶段：PR #45 Review 修复、G1 视觉证据、最终 Review 与 CI 已完成，等待人类决策

## 1. 已合并事实

| PR | 能力 | 状态 |
| --- | --- | --- |
| #31–#33 | 导航健康、Control、`gp05.v1` 真实进程 Smoke | 已合并 |
| #34–#38 | 平台方向、核心 Review 修复、进度与 Apple 资产评估 | 已合并 |
| #39–#40 | TheMasterplan v3 工作流及采用收尾 | 已合并 |
| #41 | 更名、风险状态机、HTTP/WS 竞态与合同收紧 | 已合并 |
| #42 | 远端仓库改名与旧 slug 清理 | 已合并 |
| #43 | GP22 六端点 UI 和后端事务式服务架构 | 已合并 |

主线最近完整验证来自 PR #43：后端 78 tests、前端 42 tests、构建、
`bash scripts/validate.sh` 和 `pnpm smoke` 通过。

## 2. PR #45 当前状态

PR #45 已实现 v3 默认 overlay、平台领域端口和 72 张 Windows 截图，但仍为 Draft。
Review 修复包已进入候选 head，并通过后端 88 tests、前端 46 tests、构建、
`bash scripts/validate.sh` 与 `pnpm smoke`。PR body 已按仓库模板更新，GitHub Actions
已独立完成 Validate 与 GP05 Smoke 验证；PR 仍保持 Draft。

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
| GP22 第一轮 UI | `CANDIDATE_G1_VERIFIED` | 系统 offline/stale、连接中断与恢复证据及 CI 已通过 |
| 平台领域端口 | `REVIEW_FIXED_NOT_WIRED` | 不接公开路由；审计结果与故障语义已修复并测试 |
| PostgreSQL / RBAC / Audit adapter | `G3_NOT_APPROVED` | 不得进入当前 PR |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于当前修复范围 |

## 4. 下一步

1. 由人类决定是否将 PR #45 标记 Ready 并 Squash Merge；
2. 合并后更新本文件到新的 `main` squash commit；
3. 再进入 G3 架构评审。
