# ADR 0001: PostgreSQL 平台边界不替代 Cockpit 实时权威

- Status: Accepted
- Date: 2026-08-09
- Owners: Oasis
- Related issues/changes:
  [Issue #47](https://github.com/OasisSaber/Supersonic/issues/47),
  `pvmvnuqs` / `codex/issue-47-g3-architecture-review`

## Context

Supersonic 需要在 2027 年 4 月最终验收前提供 PostgreSQL、多用户登录、
`admin/operator/viewer` RBAC、会话撤销和追加式审计。现有运行时同时要求
`CockpitService` 保持车辆、导航、风险、媒体和 `gp05.v1` snapshot 的唯一权威。

若身份、授权、审计和数据库细节直接分散到 Router，容易产生绕过路径；若把命令先写入
数据库再执行，则 PostgreSQL 会成为实时命令的事实来源并改变现有可用性边界。架构还必须
区分用于 reset/revision 的 Cockpit Session 与用户认证用的 Platform Session。

完整证据、数据模型、故障矩阵和验证合同见
[G3 架构设计](../design/2026-08-09-g3-platform-architecture-design.md)。

## Decision

1. 采用 `app.platform` 深 Module，统一拥有 User、Platform Session、Principal、
   RBAC、AuditEvent 和 WebSocket Session 注册规则。
2. FastAPI 与 PostgreSQL 是 Adapter；`app.main` 是唯一 composition root。
3. `app.platform` 通过窄 `CockpitAuthority` Interface 调用 `CockpitService`，
   不依赖具体实现，也不持有 Cockpit 状态。
4. 变更请求每次实时查库解析 Platform Session；数据库不可用时 fail-closed。
5. 已建立 WebSocket 通过内存注册表主动撤销，PostgreSQL 不进入 snapshot 广播热路径。
6. 普通命令在真实执行后记录结果并允许有界 fallback；管理命令要求主审计
   `attempted` 事务提交后才允许 mutation。
7. Audit Result 与 Audit Delivery 独立，fallback reconciliation 以 UUID 幂等。
8. `gp05.v1`、Overview 只读边界和 Control 经 FastAPI 的要求保持不变。
9. G4 按 Persistence、Identity、Audit、Integration、Demo 五个独立切片实施。

## Rationale

该方案将身份与审计复杂度隐藏在一个高 Depth Module 中，只通过少量应用级 Interface
暴露能力。它提供明确的 Seam，阻止 Router 直接绕过联合授权，同时把 PostgreSQL 故障
限制在平台身份与持久化边界内。Cockpit Runtime 保持单一真相和现有测试 Locality，
数据库与 FastAPI Implementation 可以用 fake 或集成测试独立验证。

严格数据库 Session 牺牲了数据库中断时的新认证和变更可用性，但保证撤销、禁用和角色
变化没有缓存窗口。保留已建立的只读 WebSocket 则避免把数据库查询引入实时广播热路径。

## Consequences

- Positive:
  - Cockpit 实时状态没有第二权威来源；
  - 所有变更具有统一认证、Role+Endpoint 授权和审计路径；
  - `gp05.v1` 可保持兼容；
  - PostgreSQL Adapter、fallback 和 CockpitAuthority 均可独立测试；
  - 管理命令不会在 durable intent 缺失时改变状态。
- Negative:
  - PostgreSQL 不可用时，新会话、新 WebSocket 和全部变更请求不可用；
  - 内存连接注册表只适合当前单 FastAPI 进程；
  - 内存 Cockpit mutation 与 PostgreSQL outcome audit 不具备原子事务；
  - G4 需要新的依赖、迁移、CI PostgreSQL 和前端 cookie 支持。
- Risks:
  - 事后主审计与 fallback 同时失败时只能报告 `lost`；
  - LAN 部署必须提供 HTTPS 和正确 cookie 配置，不能复用 loopback dev 模式；
  - 多进程或公开部署将要求重新评估连接撤销、rate limit 和信任边界。

## Alternatives considered

### 最小适配现有 Gateway

在现有命令专用 Gateway 旁增加 Session 与用户服务。虽然起步较快，但授权与审计会分散，
登录、会话管理和 cockpit command 容易形成平行路径，因此拒绝。

### 数据库命令账本/CQRS

先持久化每个命令再驱动 CockpitService。该方案会把 PostgreSQL 放入实时命令关键路径，
改变权威和可用性语义，并超出当前项目需要，因此拒绝。

### 短时 Session cache 或无状态 JWT

可以提高数据库故障时的命令可用性，但引入撤销延迟或额外撤销机制，与本地/内网单进程
系统所需的最小权限边界不匹配，因此拒绝。

## Verification

- 文档层验证领域词汇、D0–D15、故障矩阵和 G4 切片一致；
- 单元测试覆盖登录、撤销、联合授权、管理 pre-audit、fallback 和 WebSocket 主动关闭；
- PostgreSQL 集成测试覆盖迁移、约束、事务、查询与幂等 reconciliation；
- `bash scripts/validate.sh` 和 `pnpm smoke:gp05` 继续通过；
- 自动化结果不替代浏览器多屏、LAN HTTPS、备份恢复或目标机验证。

出现以下任一条件时重新评估本 ADR：

- FastAPI 改为多进程/多节点；
- 服务面向公共互联网；
- 需要离线变更命令或数据库中断期间继续 mutation；
- `gp05.v1` 或 CockpitAuthority 的责任发生实质变化；
- 引入企业 SSO、多租户或外部身份提供者。
