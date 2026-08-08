# Supersonic Domain Context

- 状态：G3 架构批准词汇
- 日期：2026-08-09
- 权威设计：[G3 平台架构设计](docs/design/2026-08-09-g3-platform-architecture-design.md)
- 关联决策：[ADR 0001](docs/adr/0001-postgresql-platform-boundary.md)

本文固定 Supersonic Cockpit Runtime 与 Platform Access/Audit 两个上下文之间的词汇。
新增代码、测试、API 和文档必须使用这些含义，不能用同名字段隐式混合不同生命周期。

## 1. Bounded Context

### Cockpit Runtime

负责车辆、导航、风险、媒体、端点连接、Cockpit Session、revision 和完整 snapshot。
`CockpitService` 是唯一实时权威；PostgreSQL 不决定这些值。

### Platform Access and Audit

负责 User、Platform Session、Principal、RBAC、AuditEvent、用户/会话管理和审计查询。
该上下文只决定“谁可以请求什么”以及“发生了什么持久事实”，不拥有 Cockpit 状态。

## 2. Canonical Terms

| Term | 定义 | 不等同于 |
| --- | --- | --- |
| User | 本地/内网平台的持久身份 | Cockpit endpoint、乘员 Profile |
| Platform Session | 数据库支持、可过期/撤销的用户认证会话 | Cockpit Session、浏览器 `sessionStorage` |
| Cockpit Session | reset 后更换的 `gp05.v1` 运行态实例标识 | 登录会话 |
| Principal | 服务端从有效 Platform Session 与当前 User 解析的身份 | 客户端 role/user claim |
| Role | `admin/operator/viewer` 平台权限类别 | endpoint 权限 |
| Server Endpoint Context | 服务端从受约束 Router/连接上下文解析的 endpoint | 请求体自报 endpoint |
| CockpitAuthority | 平台命令 Gateway 调用实时权威的窄 Interface | 数据库 Repository |
| AuditEvent | 不可变、追加式的身份/安全/管理/命令事实 | 普通日志、Cockpit snapshot |
| Audit Result | `attempted/succeeded/rejected/error` 业务结果 | 审计介质状态 |
| Audit Delivery | `primary/fallback/lost` 审计介质结果 | 命令成功或失败 |
| Management Command | 需要 durable attempted 的高风险命令 | 仅由 admin 执行的同义词 |
| Reconciliation | 将已 sanitize 的 fallback 事件幂等导入 PostgreSQL | 重放 Cockpit 命令 |

## 3. Required Field Names

- 用户认证上下文使用 `platform_session_id`。
- 座舱运行上下文使用 `cockpit_session_id`。
- 只有局部类型已明确限定上下文时才可使用无前缀 `session_id`。
- 审计 Actor 使用 `actor_user_id`、`actor_platform_session_id` 和
  `actor_role`。
- command endpoint 必须以 `server_endpoint` 或 `server_endpoint_context`
  表示服务端事实。

## 4. Relationships and Invariants

- 一个 User 在 G4 首版恰有一个 Role，可以拥有多个 Platform Session。
- Platform Session 必须属于一个未禁用 User，并具有绝对过期时间。
- Principal 只由服务端解析，不能从请求 body、query 或前端 Store 构造。
- RolePolicy 与 EndpointPolicy 是相交关系，不互相替代。
- Cockpit Session 可以在 Platform Session 不变时因 reset 更换。
- Platform Session 可以在 Cockpit Session 不变时因注销、撤销或到期失效。
- AuditEvent 记录 actor 当时的 Role；后续 Role 变化不改写历史。
- Audit Result 和 Audit Delivery 必须分别判断和展示。
- Reconciliation 只导入审计事实，不得重新执行 Cockpit 命令。

## 5. Forbidden Ambiguities

- 不在跨上下文文档或 API 中单独写“Session”而不说明 Platform 或 Cockpit。
- 不把 client endpoint/source 字段称为“服务端 endpoint 权限”。
- 不把 PostgreSQL 中的历史或恢复数据称为“当前实时权威状态”。
- 不把 `primary/fallback/lost` 当作命令业务结果。
- 不把 `attempted` 当作命令已经执行。
- 不把设计批准、迁移通过或 CI 通过表述为 UI/运行时/部署已经完成。

## 6. Examples

- reset 成功：Cockpit Session 改变；Platform Session 不变。
- admin 撤销 operator：Platform Session 失效并关闭其 WebSocket；
  Cockpit Session 不变。
- 普通命令执行成功但 PostgreSQL 审计失败：Audit Result 为 `succeeded`，
  Audit Delivery 为 `fallback` 或 `lost`。
- 管理命令 attempted 未提交：CockpitService 不被调用，Result 不得写成
  `succeeded`。
