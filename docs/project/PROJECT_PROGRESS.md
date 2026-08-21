# 项目进度

- 最后更新：2026-08-22
- 远端主线：`main@2522c93cf77deb1fcd2a141e97c1b39be26a5752`
- 当前候选：[Issue #61](https://github.com/OasisSaber/Supersonic/issues/61) / `codex/issue-61-g4-slice-e`
- 当前阶段：`G4_SLICE_E_CANDIDATE_VALIDATED`；尚未合并，`HUMAN_MERGE_GATE` 保持开启

## 1. 已合并事实

| PR | 能力 | 状态 |
| --- | --- | --- |
| #31–#45 | GP05/GP22、平台方向、工作流和第一轮 UI 冻结 | 已合并 |
| #48 | G3 平台边界架构批准（Issue #47） | 已合并 |
| #50 | G4 Slice A：PostgreSQL 持久化基础（Issue #49） | 已合并 |
| #52 | G4：identity 与 Platform Session（Issue #51） | 已合并 |
| #54 | G4 Slice B：认证与 CORS 加固 | 已合并 |
| #56 | G4 Slice C：审计持久化（Issue #55） | 已合并 |
| #58 | G4 Slice D：命令/WebSocket 集成（Issue #57） | 已合并 |
| #59 | 合并后同步 G4 Slice A–D 项目进度 | 已合并为 `a56662e` |
| #60 | 移除未批准的 `ultralytics` 依赖 | 已合并为当前主线 `2522c93c` |

各历史 PR 的本地验证与 GitHub Actions 结果以对应 PR 记录为准。Issue #61
基于 `main@2522c93c`，没有把候选状态写成主线事实。

## 2. Issue #61 候选范围

Slice E 已在一个 jj change 中实现并接线：

- Admin 用户、角色和 Session 查询；角色变更、账户禁用/启用和 Admin 归因的
  Session 撤销；last-admin 与 self-management 保护；数据库提交后才传播 WebSocket
  关闭；
- 服务端角色范围 Audit 查询，以及结构上独立的 `/platform` 登录、Users、Sessions、
  Audit 控制台；
- 显式交互式用户 seed CLI、受保护的 PostgreSQL custom backup、严格七键 manifest、
  显式 opt-in 的隔离 `_restore_test` restore；
- 恢复模板、实际恢复报告、应用验收记录和仅含合成身份的浏览器截图。

共享座舱实时状态仍只有 `CockpitService` 一个权威来源；Slice E 没有把实时车况写入
PostgreSQL，也没有引入多实例 revoke、OAuth/JWT/SSO、Redis、定时备份或公开部署。

## 3. Task 11 本机验收证据

- PostgreSQL 集成：`pnpm test:backend:integration` 为 61 passed；其中 Slice E 原子性、
  rollback、last-admin、归因和角色范围焦点用例为 8 passed。
- 真实备份/恢复：PostgreSQL / `pg_dump` / `pg_restore` 16.15；源数据为 4 users、
  6 platform sessions、9 audit events；checksum、仓库/恢复 Alembic revision
  `20260809_0001`、精确行数和三个恢复 invariant 一致。
- 恢复后应用验收：Admin 登录、禁用账户拒绝、4 个既有 revoked Session、Admin
  安全 Audit 可见、Operator/Viewer 安全 Audit 不可见、提交后 WebSocket 关闭、旧身份
  HTTP 401、旧 WebSocket 1008 均已验证。
- `pnpm smoke:gp05` 通过 `gp05.v1` 四客户端流程，Cockpit 实时权威边界未改变。
- 最终候选 `pnpm check` 通过：Ruff/ESLint、后端 682 passed / 4 skipped、前端
  15 files / 69 tests 和 1675-module production build。
- `bash scripts/validate.sh` 通过：23 个 validator tests、6 个 Markdown-link tests、
  tracked Markdown/YAML/Shell 检查以及同一套 project check 全部完成。
- 恢复证据测试为 11 passed；实际记录见
  [backup-manifest.json](../../deliverables/platform-recovery/backup-manifest.json)、
  [restore-report.json](../../deliverables/platform-recovery/restore-report.json) 和
  [acceptance.json](../../deliverables/platform-recovery/acceptance.json)。
- 浏览器证据见 [platform recovery evidence](../../deliverables/platform-recovery/README.md)。
  所有身份均为合成数据；真实 dump、凭据、DSN、token/cookie 和原始运行日志不进入 Git。

以上只证明本机候选验收。完整 diff/敏感信息自审、Draft PR 和 latest-head GitHub
Actions 仍是发布前门禁；只有产生新证据后才能在 PR 中标记通过。

## 4. 当前模块状态

| 模块 | 状态 | 边界 |
| --- | --- | --- |
| `gp05.v1` 运行时 | `VERIFIED_MAIN_BASELINE` | 主线权威状态、权限、reset/reconnect 与 Smoke 已建立 |
| GP22 第一轮 UI | `VERIFIED_MAIN_G1_G2` | 六端点正常/降级视觉证据已进入主线 |
| G4 Slice A–D | `VERIFIED_MAIN` | PostgreSQL、Session、认证/CORS、Audit、命令/WS 已合入 |
| G4 Slice E | `CANDIDATE_VALIDATED_LOCAL` | Issue #61 候选已完成本机恢复/应用证据，尚未合并 |
| 真实地图、Vision、语音、Web3D | `PLANNED` | 不属于当前 G4 范围 |

## 5. 下一步

1. 在 Issue #61 change 上完成最终全量验证、完整 diff 与敏感信息自审；
2. 普通 push `codex/issue-61-g4-slice-e`，创建或更新关联 Draft PR，并验证 latest-head CI；
3. 等待人类 Review 与 Squash Merge；Agent 不 merge、release 或关闭人工门；
4. 只有人类合并后，后续独立同步才可标记 `G4 PLATFORM COMPLETE` 并进入 G5。
