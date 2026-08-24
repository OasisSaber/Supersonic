# 实施路线与验收门

- 状态：`CURRENT_EXECUTION_ROADMAP`
- G4 平台合并基线：PR #62 / `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`
- G4 状态：`COMPLETE`
- 当前门：`G5_REVIEW_EXECUTED — CHANGES_REQUIRED`
- 下一门：独立授权后的五组窄修复、复验与 G5 freeze decision

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

## G5：Final Code Review / Freeze — REVIEWED, CHANGES_REQUIRED

G5 是跨模块最终审查，不是新功能 Sprint。

[Issue #65](https://github.com/OasisSaber/Supersonic/issues/65) 已按七轴执行 review，针对
基线 `main@7e1ea06e52964b09c8368943236847525a7deccc` 的 publication 由当前 review change
承载。报告见 [G5 Findings Report](../../deliverables/g5-review/G5_FINDINGS_REPORT.md) 与
[G5 Freeze Report](../../deliverables/g5-review/G5_FREEZE_REPORT.md)。当前统计为
**0 Critical / 4 High / 5 Medium / 5 Low**，verdict 为 **`CHANGES_REQUIRED`**；G5 尚未
完成，尚未 freeze。

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

输出 review verdict；具体 finding 形成后续窄修复。恢复 acceptance template 中刻意保留的
`pending` / `not_run` 示例已单独识别为模板状态，不作为 stale finding。

### G5 后续五组修复门

每组都必须独立授权，并建立独立 Fix Issue、change 和 PR；本 review change 仅发布报告，
不实现或预先声称修复：

| 修复组 | Findings | 必须复验的范围 | 状态 |
| --- | --- | --- | --- |
| Security Fix | G5-SEC-001/002/003 | established WS expiry/revoke-send、Origin gate | 未开始 |
| Audit Fix | G5-AUD-001 | attempted pre-audit commit ordering/failure semantics | 未开始 |
| Frontend Truth Fix | G5-FE-001/002/003 | credentials、null snapshot truth、invalid route boundary | 未开始 |
| CI Fix | G5-CI-001 | recovery evidence contract in required validation/CI | 未开始 |
| Docs Truth Fix | G5-DOC-001 | root README、`docs/architecture.md`、`docs/development.md` 的 current-state facts | 未开始 |

G5-ARCH-001/002、G5-REC-001/002、G5-LIC-001 的 Low disposition 保持在 findings report
中，尚未批准为 limitation 或修复承诺。

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
