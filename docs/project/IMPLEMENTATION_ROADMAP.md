# 实施路线与验收门

- 状态：`CURRENT_EXECUTION_ROADMAP`
- G4 平台合并基线：PR #62 / `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`
- G4 状态：`COMPLETE`
- G5 remediation 合并基线：PR #78 / `ca58b7c15dcd9c8b508c90e26ab63eaaf7924d34`
- 当前门：`G5_FINAL_RE_REVIEW — FREEZE_READY`（复审 publication 由当前 change 承载，待人类合并）
- 下一门：人类 G5 freeze 决定；freeze 后按 2027 年 4 月最终验收路线分别立项 real map、VehicleVision、AI 语音、多显示部署与 Web3D

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

### G5 五组 remediation 合并状态

每组均已按独立授权建立 Fix Issue/change/PR，并由人类合并。原 review 报告保持历史原貌；
这些 merge 事实不能替代最终七轴复审：

| 修复组 | Findings | 必须复验的范围 | 状态 |
| --- | --- | --- | --- |
| Security Fix | G5-SEC-001/002/003 | established WS expiry/revoke-send、Origin gate | 已合并：Issue #68 / PR #69 |
| Audit Fix | G5-AUD-001 | attempted pre-audit commit ordering/failure semantics | 已合并：Issue #71 / PR #72 |
| Frontend Truth Fix | G5-FE-001/002/003 | credentials、null snapshot truth、invalid route boundary | 已合并：Issue #73 / PR #74 |
| CI Fix | G5-CI-001 | recovery evidence contract in required validation/CI | 已合并：Issue #75 / PR #76 |
| Docs Truth Fix | G5-DOC-001 | root README、`docs/architecture.md`、`docs/development.md` 的 current-state facts | 已合并：Issue #77 / PR #78 |

### G5 Low Findings Disposition

[Issue #79](https://github.com/OasisSaber/Supersonic/issues/79) 记录五项批准决定，完整理由、
风险与操作边界见
[G5 Low Findings Disposition Record](../../deliverables/g5-review/G5_LOW_FINDINGS_DISPOSITION.md)：

- `G5-ARCH-001 = BACKLOG` → [Issue #80](https://github.com/OasisSaber/Supersonic/issues/80)
- `G5-ARCH-002 = ACCEPTED_LIMITATION`
- `G5-REC-001 = ACCEPTED_LIMITATION`
- `G5-REC-002 = BACKLOG` → [Issue #81](https://github.com/OasisSaber/Supersonic/issues/81)
- `G5-LIC-001 = BACKLOG` → [Issue #82](https://github.com/OasisSaber/Supersonic/issues/82)

全部五项均有允许的 disposition；没有 Low finding 被本记录声明为 `FIXED`。复审开始前，
verdict 继续为 `CHANGES_REQUIRED`，不得宣告 freeze。

### G5 Final Re-Review — FREEZE_READY

独立授权的七轴复审已在 reviewed head `main@6cfbe9f8542721b32a54e14a15b183be29a55d97`
执行（复审 delta 为 `7e1ea06e..6cfbe9f8` 的 8 个提交）。结果见
[G5 Final Re-Review](../../deliverables/g5-review/G5_FINAL_RE_REVIEW.md)：

- 4 High + 5 Medium 全部核验为 FIXED，均有代码与必需回归证据；
- 5 Low disposition 与批准记录一致（2 项 ACCEPTED_LIMITATION、3 项 BACKLOG）；
- 无新增 finding；七轴均为 PASS（Dependency/License 为 PASS WITH LOW，BACKLOG 已记录）；
- 本地 `bash scripts/validate.sh` PASS；精确头部 CI run `33299616699` PASS
  （Validate、PostgreSQL integration、GP05 smoke）。

最终 verdict 为 **`FREEZE_READY`**。复审 publication 由当前 change 承载；G5 freeze
宣告是人类决定，本 change 不宣告 freeze。#80/#81/#82 仍是单独授权的 backlog，不阻塞
该 verdict。

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
