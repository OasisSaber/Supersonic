# 实施路线与验收门

- 状态：`CURRENT_EXECUTION_ROADMAP`
- 主线基线：`main@e8610d8712f2fc878525ee2e62cd88693dbc7396`
- 当前任务：Issue #44 / Draft PR #45

## G0：文档事实同步

PR #45 已提供候选文档，但合并前必须保留环境配置、项目入口和许可说明，并准确
记录 CI 与视觉证据边界。

退出条件：README、Progress、Roadmap、PR body 和 GitHub 状态一致。

## G1：Windows 六端点视觉证据

已完成主要正常、导航、接管、确认、恢复、Day/Night、数据域离线、
`systemMode=offline`、`systemMode=stale`、实际后端/WebSocket 连接中断与恢复截图。
截图、权威快照、传输证据和矩阵名称一致；G1 最终通过仍需 GitHub Actions 独立通过。

退出条件：无阻塞溢出或不可操作控件，Overview 无命令，六端点状态来源准确，所有
未覆盖项明确记录。

## G2：GP22 第一轮 UI 冻结

仅允许修复有证据的 Token、字号、间距、对比度、状态表达、可访问性和端点布局。
禁止更改 `gp05.v1`、端点权限、命令名称、实时权威模型或引入新 UI 框架。

退出条件：PR #45 Review 无 Critical/High，CI、Smoke 与视觉矩阵通过。

## G3：平台纵向切片架构评审

G2 完成且 PR #45 合并后，评审 ER 图、migration、服务端会话、角色矩阵、审计字段、
失败语义、回滚和测试计划。

硬约束：

- PostgreSQL 不保存或决定当前车速、路线、风险、媒体或 WebSocket 快照；
- 客户端角色声明不可信；
- 管理命令在缺少主审计 intent 时不得修改状态；
- 非管理命令的审计故障不能导致“状态已修改但响应失败”的假象；
- fallback 必须保留 succeeded/rejected/error 结果，单独记录交付状态。

## G4：平台纵向切片实现

数据库配置 → migration → 用户/角色/会话/审计 → 登录 → 服务端身份上下文 →
RBAC → 一个现有 command → audit 查询 → session revoke → 备份恢复。

## G5：最终 Code Review 与冻结

检查 UI、外部数据校验、实时状态权威、数据库职责、权限、审计、migration、失败
恢复、Mock/真实标签、测试有效性和文档准确性。

## 当前排除项

真实地图、真实 VehicleVision、AI 语音、Web3D、Electron/Tauri、公共云、企业 SSO、
多租户、高可用和量产车辆安全认证。
