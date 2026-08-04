# 实施路线与验收门

- 状态：`CURRENT_EXECUTION_ROADMAP`
- 基线：`main@e8610d8712f2fc878525ee2e62cd88693dbc7396`
- 周期：4–6 周

## 已完成历史

以下核心任务已合并，不得作为当前待办重复实施：Issue #7、#11、#12、#13、#14、#17、#18、#19，以及 PR #39–#43 对应的工作流、更名、状态完整性、UI 和后端架构任务。

## G0：文档事实同步

- 更新 README、Progress、Roadmap；
- 记录 PR #39–#43 和当前验证数字；
- 明确当前单用户 Mock 形态、GP22 第一轮实现和最终平台目标。

退出条件：文档互相一致，`bash scripts/validate.sh` 通过。

## G1：Windows 六端点视觉证据

覆盖：Cluster、HUD、Center、Passenger、Overview、Control；Day/Night；normal、navigation、takeover、acknowledged、recovery、stale、offline；Control enabled/disabled。

退出条件：无阻塞溢出或不可操作控件，Overview 无命令，六端点使用同一 session/revision，偏差全部记录。

## G2：GP22 第一轮 UI 冻结

允许修复 Token、字号、间距、对比度、状态表达、可访问性和端点布局。禁止更改 `gp05.v1`、端点权限、命令名称、实时权威模型或引入新 UI 框架。

退出条件：无 P0/P1 视觉缺陷，偏差关闭或获批延期，截图可用于答辩，`validate.sh` 与 Smoke 通过。

## G3：平台纵向切片架构评审

评审 ER 图、migration、服务端会话、角色矩阵、审计字段、失败语义、回滚和测试计划。

硬约束：PostgreSQL 不保存或决定当前车速、路线、风险、媒体或 WebSocket 快照；客户端角色声明不可信；服务端 session 是身份来源。

## G4：平台纵向切片实现

顺序：数据库配置 → migration → 用户/角色/会话/审计 → 登录 → 服务端身份上下文 → RBAC → 一个现有 command → audit 查询 → session revoke → 备份恢复。

退出条件：空库迁移可重复；401/403 负向测试通过；撤销立即生效；审计可查询；数据库故障有明确降级；备份恢复通过。

## G5：最终 Code Review 与冻结

检查 UI、外部数据校验、实时状态权威、数据库职责、权限、审计、migration、失败恢复、Mock/真实标签、测试有效性和文档准确性。

退出条件：无 Critical/High；Medium 有处置；完整演示“登录 → 命令 → 审计 → 查询 → 撤销”。

## 本轮排除项

真实地图、真实 VehicleVision、AI 语音、Web3D、Electron/Tauri、公共云、企业 SSO、多租户、高可用、Docker/Kubernetes 和量产认证不进入本轮。
