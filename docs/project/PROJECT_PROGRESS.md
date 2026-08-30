# 项目进度

- 最后更新：2026-08-30
- G4 平台合并基线：PR #62 / `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`
- G5 review 基线：`main@7e1ea06e52964b09c8368943236847525a7deccc`
- G5 remediation 合并基线：PR #78 / `ca58b7c15dcd9c8b508c90e26ab63eaaf7924d34`
- 当前阶段：`G5_LOW_FINDINGS_DISPOSITION`
- 当前 verdict：`CHANGES_REQUIRED`
- 下一阶段：Low disposition 由人类合并后执行独立最终复审；G5 尚未完成、尚未 freeze

> 本文件使用稳定的阶段/PR 基线，不追逐包含本文件自身的最新 main commit SHA。

## 1. 已合并事实

| PR | 能力 | 状态 |
| --- | --- | --- |
| #31–#45 | GP05/GP22、平台方向、工作流和第一轮 UI 冻结 | 已合并 |
| #48 | G3 平台边界架构批准（Issue #47） | 已合并 |
| #50 | G4 Slice A：PostgreSQL 持久化基础（Issue #49） | 已合并 |
| #52 | G4 identity 与 Platform Session（Issue #51） | 已合并 |
| #54 | G4 Slice B：认证与 CORS 加固 | 已合并 |
| #56 | G4 Slice C：Audit 持久化（Issue #55） | 已合并 |
| #58 | G4 Slice D：命令/WebSocket 集成（Issue #57） | 已合并 |
| #59 | 同步 G4 Slice A–D 项目进度 | 已合并 |
| #60 | 移除未批准的 `ultralytics` 依赖 | 已合并 |
| #62 | G4 Slice E：Admin / Viewer / Recovery（Issue #61） | 已人类 Squash Merge |
| #64 | G4 Post-Merge Closure：恢复证据与平台阶段收口（Issue #63） | 已合并 |
| #66 | G5 七轴 review publication（Issue #65） | 已合并；verdict `CHANGES_REQUIRED` |
| #69 | G5 Security Fix（Issue #68） | 已合并 |
| #70 | GP22 Asset Intake（Issue #67） | 已合并 |
| #72 | G5 Audit Fix（Issue #71） | 已合并 |
| #74 | G5 Frontend Truth Fix（Issue #73） | 已合并 |
| #76 | G5 CI Fix（Issue #75） | 已合并 |
| #78 | G5 Docs Truth Fix（Issue #77） | 已合并 |

PR #62 的 merge commit 为 `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`。

## 2. G4 完成范围

G4 现在已经形成完整平台纵向闭环：

- PostgreSQL users / Platform Sessions / Audit persistence；
- Argon2 登录、opaque Platform Session、服务端 Principal；
- Role policy AND Endpoint policy；
- Command Gateway / Audit Runtime / CockpitService；
- authenticated WebSocket 与单进程 Session registry；
- Admin 用户、角色和 Session 管理；
- role change / disable 后 durable revoke，数据库 commit 后再传播 WebSocket close；
- role-scoped Audit history；
- 独立 `/platform` Admin / Operator / Viewer surface；
- explicit user seed；
- guarded PostgreSQL custom backup / isolated restore；
- sanitized recovery evidence。

共享座舱实时状态仍只有 `CockpitService` 一个权威来源；PostgreSQL 不保存或决定当前
车速、路线、风险、媒体或 WebSocket snapshot。

## 3. Post-merge recovery closure

PR #62 合并后，以公开 G4 merge baseline：

`cb6ab6645313716e9ed54c8ecb49c27b3d918f37`

重新执行了真实 PostgreSQL backup / isolated restore / application acceptance rehearsal。
同时在 source 与 restore target 核对了 Audit 排序索引并执行降序查询 `EXPLAIN`；临时索引
操作仅发生在隔离库的事务内，没有修改 migration 或持久项目 schema。

权威结果见：

- [backup-manifest.json](../../deliverables/platform-recovery/backup-manifest.json)
- [restore-report.json](../../deliverables/platform-recovery/restore-report.json)
- [acceptance.json](../../deliverables/platform-recovery/acceptance.json)
- [platform recovery evidence](../../deliverables/platform-recovery/README.md)

这些 actual records 使用公开 merge baseline 作为 recovery checkpoint，并记录已完成的人类
merge gate。Examples 仍保持 `pending` / `not_run`，只作为未来操作模板。

真实 dump、凭据、DSN、token/cookie 和 raw logs 不进入 Git。

## 4. 当前模块状态

| 模块 | 状态 | 边界 |
| --- | --- | --- |
| `gp05.v1` 运行时 | `VERIFIED_MAIN_BASELINE` | Cockpit 实时权威、权限、reset/reconnect 与 Smoke |
| GP22 第一轮 UI | `VERIFIED_MAIN_G1_G2` | 六端点正常/降级视觉证据 |
| G3 Architecture | `APPROVED` | PR #48 |
| G4 Platform | `COMPLETE` | PR #50/#52/#54/#56/#58/#62 |
| Post-merge Recovery | `VERIFIED` | 公开 PR #62 merge baseline 上的恢复复验 |
| G5 Final Review / Freeze | `REVIEWED — CHANGES_REQUIRED` | [Issue #65](https://github.com/OasisSaber/Supersonic/issues/65) 七轴 review 已执行；报告 publication 属于当前 review change；尚未完成、尚未 freeze |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于 G4 |

## 5. G5 Review publication（Issue #65）

本轮以 `main@7e1ea06e52964b09c8368943236847525a7deccc` 为基线执行七轴 review，publication
由当前 review change 承载，报告见：

- [G5 Findings Report](../../deliverables/g5-review/G5_FINDINGS_REPORT.md)
- [G5 Freeze Report](../../deliverables/g5-review/G5_FREEZE_REPORT.md)

结果为 **0 Critical / 4 High / 5 Medium / 5 Low，verdict `CHANGES_REQUIRED`**。因此 G5
尚未完成，也没有 freeze decision。恢复 acceptance template 中刻意保留的 `pending` /
`not_run` 示例已单独识别为模板状态，不作为 stale finding。

## 6. G5 remediation 合并状态

以下五组均按独立授权、Issue、change、验证、Draft PR 与人类 merge 门完成。原始 review
报告仍保留当时的 `CHANGES_REQUIRED` 历史结论；最终 verdict 只能由新的七轴复审给出：

| 修复组 | Findings | 后续要求 | 当前状态 |
| --- | --- | --- | --- |
| Security Fix | G5-SEC-001/002/003 | Issue #68 / PR #69 | 已合并 |
| Audit Fix | G5-AUD-001 | Issue #71 / PR #72 | 已合并 |
| Frontend Truth Fix | G5-FE-001/002/003 | Issue #73 / PR #74 | 已合并 |
| CI Fix | G5-CI-001 | Issue #75 / PR #76 | 已合并 |
| Docs Truth Fix | G5-DOC-001 | Issue #77 / PR #78 | 已合并 |

## 7. Low Findings Disposition（Issue #79）

五项 Low finding 的批准决定记录在
[G5 Low Findings Disposition Record](../../deliverables/g5-review/G5_LOW_FINDINGS_DISPOSITION.md)：

| Finding | Disposition | Follow-up |
| --- | --- | --- |
| G5-ARCH-001 | `BACKLOG` | [Issue #80](https://github.com/OasisSaber/Supersonic/issues/80) |
| G5-ARCH-002 | `ACCEPTED_LIMITATION` | 第二个 command adapter 出现时重新评审并集中 policy |
| G5-REC-001 | `ACCEPTED_LIMITATION` | 保留 fail-closed 的 orphan dump 人工识别/清理说明 |
| G5-REC-002 | `BACKLOG` | [Issue #81](https://github.com/OasisSaber/Supersonic/issues/81) |
| G5-LIC-001 | `BACKLOG` | [Issue #82](https://github.com/OasisSaber/Supersonic/issues/82) |

五项均已选择允许的 disposition，没有未决定项。这只满足最终复审的 Low input gate，
不代表 finding 已修复，也不产生 freeze decision。当前 verdict 仍为 `CHANGES_REQUIRED`。

G4 不再接受没有具体回归/审查 finding 的功能性追加。
