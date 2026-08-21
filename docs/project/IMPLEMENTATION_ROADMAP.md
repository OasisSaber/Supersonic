# 实施路线与验收门

- 状态：`CURRENT_EXECUTION_ROADMAP`
- 主线基线：`main@2522c93cf77deb1fcd2a141e97c1b39be26a5752`
- 当前任务：[Issue #61](https://github.com/OasisSaber/Supersonic/issues/61) / `codex/issue-61-g4-slice-e`
- 当前门：`G4_SLICE_E_CANDIDATE_VALIDATED` / `HUMAN_MERGE_GATE`

## G0–G2：主线基线与第一轮 UI 冻结

GP05/GP22、Windows 六端点视觉证据、传输/权威状态合同和第一轮 UI 冻结已由
PR #31–#45 进入主线。PR #59 同步了 G4 Slice A–D 事实，PR #60 移除了未批准的
`ultralytics` 依赖，形成当前主线基线 `2522c93c`。

## G3：平台纵向切片架构评审

G3 已由 Issue #47 / PR #48 批准并合入。持续有效的硬约束：

- PostgreSQL 不保存或决定当前车速、路线、风险、媒体或 WebSocket 快照；
- 客户端角色声明不可信，角色与 Audit scope 由服务端身份决定；
- 管理变更、Session revoke 和主审计事实必须处于同一提交边界；
- WebSocket close 只在数据库 commit 后传播；
- fallback 保留原始业务结果，交付状态单独表达。

## G4：平台纵向切片实现

### 已进入主线

- Slice A / PR #50：PostgreSQL database、ORM、migration、adapter 与 UoW；
- identity / PR #52：用户与 Platform Session；
- Slice B / PR #54：登录、服务端身份、认证与 CORS；
- Slice C / PR #56：Audit 持久化、fallback 与回填；
- Slice D / PR #58：命令网关和单进程 WebSocket Session registry。

### Slice E 候选（Issue #61，尚未合并）

候选实现 Admin 用户/角色/Session 管理、角色范围 Audit、独立 `/platform` 控制台、
显式 seed、guarded backup/restore 和 sanitized recovery evidence。Task 11 已完成本机
真实 PostgreSQL integration、`pg_dump`、隔离 `_restore_test` `pg_restore --clean`、
恢复后 Admin/API/Audit/WebSocket/browser 验收与 GP05 smoke。

证据入口：

- [恢复操作与证据说明](../../deliverables/platform-recovery/README.md)
- [恢复验收模板](../../deliverables/platform-recovery/RECOVERY_ACCEPTANCE_TEMPLATE.md)
- [实际 restore report](../../deliverables/platform-recovery/restore-report.json)
- [实际 application acceptance](../../deliverables/platform-recovery/acceptance.json)

本机验收没有越过人工门。真实 dump、临时凭据、wrapper 和 raw logs 不提交；Draft PR、
latest-head CI、人类 Review 与 Squash Merge 尚未发生。

### G4 退出条件

| 门禁 | 当前状态 |
| --- | --- |
| 隔离 PostgreSQL integration | 本机通过：61 passed |
| 真实 backup / isolated restore | 本机通过：4/6/9 行、revision/count/invariant 一致 |
| 禁用/revoke persistence 与恢复后 Admin/Audit API | 本机通过 |
| WebSocket revoke 与浏览器证据 | 本机通过，使用合成身份 |
| `pnpm smoke:gp05` | 本机通过，`gp05.v1` 四客户端 |
| `pnpm check` | 通过：后端 682/4 skipped、前端 69、production build |
| `bash scripts/validate.sh` | 通过：validator/link/YAML/Shell/project check |
| 完整 diff、临时文件与敏感信息自审 | 待执行 |
| Draft PR 与 latest-head GitHub Actions | 待执行 |
| 人类 Review 与 Squash Merge | `HUMAN_MERGE_GATE`，待人类决定 |

只有所有前置门禁有真实证据且人类完成合并后，后续独立文档更新才能标记
`G4 PLATFORM COMPLETE`。当前候选不得提前进入 G5。

## G5：最终 Code Review 与冻结

G5 尚未开始。进入条件是 Slice E 人类合并以及 G4 关闭事实已由后续同步记录。
届时检查 UI、外部数据校验、实时状态权威、数据库职责、权限、Audit、migration、
失败恢复、Mock/真实标签、测试有效性和文档准确性。

## 当前排除项

真实地图、真实 VehicleVision、AI 语音、Web3D、Electron/Tauri、公共云、企业 SSO、
多租户、高可用和量产车辆安全认证。
