# 项目进度

- 最后更新：2026-08-23
- G4 平台合并基线：PR #62 / `cb6ab6645313716e9ed54c8ecb49c27b3d918f37`
- 当前阶段：`G4_PLATFORM_COMPLETE`
- 下一阶段：`G5_FINAL_REVIEW_FREEZE`

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
| G5 Final Review / Freeze | `NEXT` | 尚未执行 |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于 G4 |

## 5. 下一步

1. 创建独立 G5 Final Code Review / Freeze Issue；
2. 对已完成 G4 baseline 做跨模块 findings-first 审查；
3. 只修复具体 review finding，不借 G5 扩大产品功能；
4. 完成 freeze decision 后，再分别规划真实地图、VehicleVision、AI voice、Web3D 等最终范围。

G4 不再接受没有具体回归/审查 finding 的功能性追加。
