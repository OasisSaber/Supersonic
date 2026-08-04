# 项目进度

- 最后更新：2026-08-06
- 远端主线基线：`main@e8610d8712f2fc878525ee2e62cd88693dbc7396`
- 当前阶段：GP22 第一轮代码迁移已完成，进入视觉证据闭环与平台纵向切片设计

## 1. 已合并事实

| PR | 能力 | 状态 |
| --- | --- | --- |
| #31–#33 | 导航健康、Control、`gp05.v1` 真实进程 Smoke | 已合并 |
| #34–#38 | 平台方向、核心 Review 修复、进度与 Apple 资产评估 | 已合并 |
| #39–#40 | TheMasterplan v3 工作流及采用收尾 | 已合并 |
| #41 | Supersonic 更名、风险状态机、HTTP/WS 竞态与合同收紧 | 已合并 |
| #42 | 远端仓库改名与旧 slug 清理 | 已合并 |
| #43 | GP22 六端点 UI 体系与后端事务式服务架构 | 已合并 |

PR #43 报告的最近完整验证：后端 78 tests、前端 42 tests、TypeScript/Vite build、`bash scripts/validate.sh` 与 `pnpm smoke` 通过。

## 2. 当前模块状态

| 模块 | 状态 | 边界 |
| --- | --- | --- |
| `gp05.v1` 合同与运行时 | `VERIFIED_BASELINE` | FastAPI 权威状态、HTTP/WebSocket、权限、reset/reconnect 与 Smoke 已建立 |
| 六端点前端结构 | `IMPLEMENTED_BASELINE` | 已拆分端点与共享原语；Overview 只读，Control 独立 |
| GP22 第一轮代码迁移 | `IMPLEMENTED_VISUAL_EVIDENCE_PARTIAL` | Token、布局、交互和状态表达已进入主线；Windows 六端点截图与状态矩阵已完成，Figma 对照待办 |
| 本地三条核心流程 | `VERIFIED_MOCK_BASELINE` | 导航接力、模拟风险处置、副驾协作可重复演示 |
| 后端架构 | `IMPLEMENTED_BASELINE` | Policy、Factory、Transitions、Broker、Service、Router 已分层 |
| PostgreSQL / RBAC / Audit | `DESIGN_READY_NOT_INTEGRATED` | 本资产包提供端口、策略和 staged adapter；未进入主线 |
| 真实地图 | `PLANNED` | 当前仅 `local_fallback` |
| VehicleVision | `PLANNED` | 当前仅 `simulated_event` |
| AI 语音 | `PLANNED_LATE` | 仅允许未来复用白名单命令 |
| 多显示部署 | `PLANNED` | 当前仍需浏览器手工多窗口 |
| Web3D | `PLANNED_LATE` | 必须后置、懒加载并有静态 fallback |

## 3. 当前最高优先级

### P0：事实与视觉证据

- 同步 README、Progress、Roadmap；
- 在 Windows 目标环境运行六端点（2026-08-06 已执行，见 `docs/VISUAL_ACCEPTANCE_MATRIX.md`）；
- 覆盖 Day/Night、normal、takeover、acknowledged、recovery、stale、offline（截图矩阵已完成）；
- 建立 GP22 Figma 对照和偏差清单；
- 只修有证据的视觉问题，随后冻结第一轮 UI。

### P1：平台最小纵向切片

```text
operator 登录 → 发送现有 command → PostgreSQL 审计 → viewer 查询 → admin 撤销会话
```

数据库只管理身份、会话、审计和历史，不成为实时座舱状态源。

## 4. 未验证项

- 1920×1080 的 200% 浏览器缩放（1366×768、1920×1080、2560×1440 已覆盖）；
- Day/Night 对比度实测；
- GP22 Figma 像素和信息层级对照；
- PostgreSQL migration、备份恢复与故障降级；
- 真实设备和多显示部署。

## 5. 完成定义

一项能力只有同时具备代码、自动化或可重复验证、展示证据、准确来源标签和同步文档，才能标记完成。
