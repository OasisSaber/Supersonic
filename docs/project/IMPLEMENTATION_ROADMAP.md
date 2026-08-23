# 实施路线与验收门

- 状态：`CURRENT_EXECUTION_ROADMAP`
- G4 平台合并基线：PR #62 / `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`
- 当前门：`G4_PLATFORM_COMPLETE`
- 下一门：`G5_FINAL_REVIEW_FREEZE`

## G0–G2：主线基线与第一轮 UI 冻结

GP05/GP22、Windows 六端点视觉证据、传输/权威状态合同和第一轮 UI 冻结已进入主线。

## G3：平台纵向切片架构评审

G3 已由 Issue #47 / PR #48 批准并合入。持续有效：

- PostgreSQL 不保存或决定当前 cockpit runtime state；
- 客户端角色声明不可信；
- Principal / role / Audit scope 由服务端身份决定；
- 管理变更和主审计事实保持明确事务边界；
- WebSocket close 只在 DB commit 后传播；
- Audit business result 与 delivery 独立表达。

## G4：平台纵向切片实现 — COMPLETE

已合并：

- Slice A / PR #50：PostgreSQL ORM、migration、adapter、UoW；
- identity / PR #52：User / Platform Session；
- Slice B / PR #54：认证、服务端身份、CORS；
- Slice C / PR #56：Audit persistence / fallback / reconciliation；
- Slice D / PR #58：Command Gateway / authenticated WebSocket integration；
- Slice E / PR #62：Admin/Viewer、role-scoped Audit、user seed、backup/restore、recovery evidence。

PR #62 由人类 Squash Merge；G4 人工 merge gate 已满足。

### Post-merge recovery

以公开 merge baseline `cb6ab6645313716e9ed54c8ecb49c27b3d918f37` 重新执行真实 backup / isolated restore / restored-app acceptance。

source 与 restore target 的 Audit 排序索引、降序查询 `EXPLAIN` 以及隔离事务内的临时索引
生命周期也已验证；没有修改 production migration 或持久项目 schema。

actual evidence：

- [recovery README](../../deliverables/platform-recovery/README.md)
- [backup manifest](../../deliverables/platform-recovery/backup-manifest.json)
- [restore report](../../deliverables/platform-recovery/restore-report.json)
- [application acceptance](../../deliverables/platform-recovery/acceptance.json)

这一步只关闭 recovery provenance / 文档事实，不新增 runtime 功能。

### G4 退出条件

| 门禁 | 状态 |
| --- | --- |
| PostgreSQL persistence | PASS |
| Identity / Platform Session | PASS |
| Authentication / CORS | PASS |
| Audit persistence / recovery | PASS |
| Command / WebSocket integration | PASS |
| Admin / Viewer management | PASS |
| real backup / isolated restore | PASS |
| role-scoped Audit UI | PASS |
| GP05 regression | PASS |
| human Squash Merge of Slice E | PASS |
| post-merge recovery provenance | PASS |
| Audit index / EXPLAIN isolation check | PASS |

`G4 PLATFORM COMPLETE`。

## G5：Final Code Review / Freeze — NEXT

G5 是跨模块最终审查，不是新功能 Sprint。

检查：

- realtime state authority；
- HTTP/WS authorization；
- Platform Session / Principal / RBAC；
- Audit integrity / fallback / reconciliation；
- management transaction ordering；
- DB failure / degraded semantics；
- backup/restore provenance；
- UI role boundary；
- secrets/logging；
- migration；
- tests/CI validity；
- docs truth；
- dependency/license state；
- visual evidence completeness。

输出 freeze verdict；具体 finding 可形成后续窄修复。

## G5 排除项

除非直接修复 G5 Critical/High finding，否则不加入：

- real map
- VehicleVision
- AI voice
- Web3D
- Electron/Tauri
- public cloud
- enterprise SSO
- Redis / multitenant / HA
