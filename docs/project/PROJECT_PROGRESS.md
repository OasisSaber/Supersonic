# 项目进度

- 最后更新：2026-08-31
- G4 平台合并基线：PR #62 / `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`
- G5 review 基线：`main@7e1ea06e52964b09c8368943236847525a7deccc`
- G5 remediation 合并基线：PR #78 / `ca58b7c15dcd9c8b508c90e26ab63eaaf7924d34`
- G5 复审 publication 基线：PR #85 / Issue #84
- 最新合并基线：PR #89 / Issue #82
- 当前阶段：`G5_FINAL_RE_REVIEW`
- 当前 verdict：`FREEZE_READY`（由 [G5 Final Re-Review](../../deliverables/g5-review/G5_FINAL_RE_REVIEW.md) 给出；复审 publication 已由 PR #85 合并、Issue #84 已关闭；G5 freeze 宣告是人类决定，本文档不宣告 freeze）
- 下一阶段：人类作出 G5 freeze 决定；之后按最终验收路线分别立项真实地图、VehicleVision、AI 语音、多显示部署与 Web3D

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
| #83 | G5 Low Findings Disposition 记录（Issue #79） | 已合并 |
| #85 | G5 七轴终审 publication（Issue #84） | 已合并；verdict `FREEZE_READY` |
| #86 | 行尾归一化：`.gitattributes` 与 CR guard | 已合并 |
| #87 | G5 架构 Backlog：移除 legacy gateway 与 Audit 导出面（Issue #80） | 已合并 |
| #88 | G5 恢复 Backlog：替换自引用恢复证据（Issue #81） | 已合并 |
| #89 | G5 许可 Backlog：补全依赖来源记录（Issue #82） | 已合并 |
| #90 | 工作流修订：采纳「微小修复快速通道」 | 已合并 |

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
| G5 Final Review / Freeze | `REVIEWED — FREEZE_READY` | 七轴复审已在 `main@6cfbe9f8` 执行，[G5 Final Re-Review](../../deliverables/g5-review/G5_FINAL_RE_REVIEW.md) 给出 `FREEZE_READY`；复审 publication 已由 PR #85 合并、Issue #84 已关闭；G5 freeze 宣告仍待人类决定。原始报告（`CHANGES_REQUIRED`）保留历史原貌 |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于 G4 |

## 5. G5 Review publication（Issue #65）

本轮以 `main@7e1ea06e52964b09c8368943236847525a7deccc` 为基线执行七轴 review，publication
由当前 review change 承载，报告见：

- [G5 Findings Report](../../deliverables/g5-review/G5_FINDINGS_REPORT.md)
- [G5 Freeze Report](../../deliverables/g5-review/G5_FREEZE_REPORT.md)

结果为 **0 Critical / 4 High / 5 Medium / 5 Low，verdict `CHANGES_REQUIRED`**。因此该轮
publication 后 G5 尚未完成，也没有 freeze decision；最终结论见第 8 节。恢复 acceptance
template 中刻意保留的 `pending` / `not_run` 示例已单独识别为模板状态，不作为 stale finding。

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
| G5-ARCH-001 | `BACKLOG` | [Issue #80](https://github.com/OasisSaber/Supersonic/issues/80) → 已完成：PR #87，Issue 已关闭 |
| G5-ARCH-002 | `ACCEPTED_LIMITATION` | 第二个 command adapter 出现时重新评审并集中 policy |
| G5-REC-001 | `ACCEPTED_LIMITATION` | 保留 fail-closed 的 orphan dump 人工识别/清理说明 |
| G5-REC-002 | `BACKLOG` | [Issue #81](https://github.com/OasisSaber/Supersonic/issues/81) → 已完成：PR #88，Issue 已关闭 |
| G5-LIC-001 | `BACKLOG` | [Issue #82](https://github.com/OasisSaber/Supersonic/issues/82) → 已完成：PR #89，Issue 已关闭 |

五项均已选择允许的 disposition，没有未决定项。这只满足最终复审的 Low input gate，
不代表 finding 已修复，也不产生 freeze decision。复审执行前 verdict 为
`CHANGES_REQUIRED`；复审结果见第 8 节。

上表 Follow-up 列的「已完成」只表示对应编码与记录工作已合并且 Issue 已关闭；
[G5 Low Findings Disposition Record](../../deliverables/g5-review/G5_LOW_FINDINGS_DISPOSITION.md)
中的 disposition 值保持批准时的历史原貌，是否改写为 `FIXED` 属于人类决定，本文档不代改。

G4 不再接受没有具体回归/审查 finding 的功能性追加。

## 8. G5 Final Re-Review（Issue #84 / PR #85，已合并）

七轴复审已在 reviewed head `main@6cfbe9f83f9d82bc2ff0afb523fbf1277817e993` 执行，复审
delta 为原审查基线 `7e1ea06e` 之后的 8 个提交（五组 remediation、GP22 资产引入与两笔
记录）。结果：

- 4 High + 5 Medium 全部核验为 FIXED，每项都有对应代码与必需回归测试/记录证据；
- 5 Low 的 disposition 与批准记录一致（2 项 ACCEPTED_LIMITATION、3 项 BACKLOG #80/#81/#82）；
- 无新增 Critical/High/Medium/Low finding；
- 本地 `bash scripts/validate.sh` PASS（后端 724 passed / 4 skipped，前端 85 passed，
  构建通过）；精确头部 CI run `33299616699` PASS（Validate、PostgreSQL integration、
  GP05 smoke）。

权威结果见 [G5 Final Re-Review](../../deliverables/g5-review/G5_FINAL_RE_REVIEW.md)，
最终 verdict 为 **`FREEZE_READY`**。该 verdict 表示七轴审查门通过。复审 publication 已由
PR #85 合并、Issue #84 已关闭，因此本文档不再表述为「待人类合并」；G5 freeze 宣告仍是人类
决定，本文档不宣告 freeze。

## 9. G5 复审后的收口（PR #86–#90）

PR #85 之后，以下五个 change 继续经 PR 与人类 merge 门合入 `main`：

| PR | 内容 | 关联 |
| --- | --- | --- |
| #86 | 行尾归一化：`.gitattributes` 与 CR guard | 仓库卫生，无 Issue |
| #87 | 移除 legacy gateway 与 Audit 导出面 | Issue #80（G5-ARCH-001） |
| #88 | 恢复证据去除自引用并补充 provenance policy | Issue #81（G5-REC-002） |
| #89 | 补全依赖来源记录 | Issue #82（G5-LIC-001） |
| #90 | 工作流修订：采纳「微小修复快速通道」 | 规则修订，无 Issue |

至此 #80/#81/#82 三项 BACKLOG follow-up 的编码与记录工作已完成、Issue 已关闭；#90 的
「微小修复快速通道」已写入根部 `AGENTS.md`。G5 七轴复审的 verdict 仍为 `FREEZE_READY`，
G5 freeze 宣告仍是人类决定。
