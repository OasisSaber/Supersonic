# G3 PostgreSQL、Platform Session、RBAC 与审计架构设计

- 状态：`G3-ARCHITECTURE-APPROVED`
- 批准日期：2026-08-09
- 批准人：Oasis
- 任务来源：[Issue #47](https://github.com/OasisSaber/Supersonic/issues/47)
- 评审 change：`pvmvnuqs` / `codex/issue-47-g3-architecture-review`
- 评审基线：`main@739c9245f551c555ff3475103c5f20b988ffd6e5`
- 资产包 SHA-256：`A4133A4A5770A4AF71E6EFD7EA73C929BF18A7CE6EC5C5A3D327E2CAC083F6B9`
- 关联 ADR：[ADR 0001](../adr/0001-postgresql-platform-boundary.md)
- 领域词汇：[CONTEXT.md](../../CONTEXT.md)

## 1. 结论与批准边界

G3 批准采用一个深模块化的平台边界，在不改变 `gp05.v1`、不替换
`CockpitService` 实时权威地位的前提下，引入 PostgreSQL 支持的 User、
Platform Session、RBAC 与追加式 AuditEvent。

本批准只确认架构、数据语义、故障语义、验证合同和 G4 切片：

- 不表示 PostgreSQL、登录、RBAC、审计或管理界面已经实现；
- 不允许在 G3 change 中接入公开 Router；
- 不自动授权任何 G4 实现、push、PR、Ready、merge、release 或部署；
- 每个 G4 切片仍需独立 Issue 或明确人类授权、独立 jj change 和独立 PR。

## 2. 不变量与非目标

### 2.1 必须保持

- `CockpitService` 是车辆、导航、风险、媒体和 snapshot 的唯一实时权威来源。
- PostgreSQL 不决定当前车辆状态，也不进入 snapshot 生成或广播热路径。
- Principal 由服务端根据 Platform Session 解析；客户端 user、role、session 和
  endpoint 声明均不是权限事实。
- Role policy 与现有 endpoint policy 必须同时允许，命令才可执行。
- `gp05.v1` 不修改、不自动升级，也不创建第二套 command 或 snapshot 协议。
- Overview 严格只读；Control 也必须经过 FastAPI、联合授权和同一 Gateway。
- 命令业务结果与审计 delivery 独立，不能用审计故障改写真实业务结果。
- 管理命令只有在 durable `attempted` 事件提交后才允许改变 Cockpit 状态。
- 密码、raw session secret、cookie、token、私有文本和私人路径不得进入审计。

### 2.2 G3/G4 平台骨架不做

- OAuth、公共 SSO、通用 JWT 平台或复杂多租户；
- Redis、微服务、消息总线、分布式锁或高可用 PostgreSQL；
- 公共互联网、公共云安全平台、WAF 或量产车辆 PKI；
- 用数据库命令账本替换 CockpitService；
- 持久化实时 snapshot、车辆、导航、风险或媒体状态；
- 自动后台 fallback reconciliation；
- G3 阶段的 Router 接线或 UI 实现。

## 3. 领域词汇

### 3.1 两种 Session

- **Cockpit Session**：`gp05.v1` 中的运行态 session；reset 后更换，用于判断
  snapshot/revision 是否属于同一座舱运行实例。
- **Platform Session**：数据库支持的用户认证会话；可过期、注销和撤销。
- `platform_session_id` 与 `cockpit_session_id` 必须使用不同字段，禁止用
  `session_id` 在两者之间隐式复用。

### 3.2 其他核心词汇

- **User**：本地/内网平台的持久身份。
- **Principal**：服务端从有效 Platform Session 与当前 User 解析出的请求身份。
- **Server Endpoint Context**：由受约束 Router/连接上下文解析的 endpoint，
  再与客户端 payload/source 做一致性检查。
- **AuditEvent**：对身份、安全、管理或座舱命令事实的不可变、追加式记录。
- **Audit Result**：`attempted/succeeded/rejected/error`，描述业务结果。
- **Audit Delivery**：`primary/fallback/lost`，描述审计介质结果。

完整定义和禁止的歧义用语见 [CONTEXT.md](../../CONTEXT.md)。

## 4. 方案比较

### 4.1 采用：深模块化平台边界

`app.platform` 作为高 Depth Module，隐藏 Repository、ORM 和事务细节，只暴露
应用级 Interface。FastAPI 和 PostgreSQL 都是 Adapter，`app.main` 是唯一
composition root。该方案提供最高 Leverage，同时保留 Cockpit Runtime 的 Locality。

### 4.2 未采用：最小适配现有 Gateway

保留命令专用 Gateway 并在旁边增加 Session、用户与认证审计服务，起步较快，但
身份和审计会形成多条平行路径，容易从 Router 绕过统一策略，长期 Locality 较差。

### 4.3 未采用：数据库命令账本/CQRS

所有命令先持久化再由执行器驱动 CockpitService，可以强化 durable ledger，但会让
PostgreSQL 进入实时命令关键路径，改变既有权威边界，并引入当前项目不需要的复杂度。

## 5. Module、Interface 与依赖方向

### 5.1 Module 职责

`app.platform` 拥有：

- User、Platform Session、Principal、RolePolicy 和 AuditEvent；
- 登录、解析、注销、撤销、禁用和角色变更；
- Role 与 Server Endpoint Context 的联合授权；
- 命令审计编排；
- WebSocket Platform Session 连接注册；
- 受范围限制的用户、会话和审计查询。

它不拥有车辆、导航、风险、媒体、Cockpit Session 或 snapshot。

### 5.2 对外 Interface

- `SessionService`：登录、解析、注销和撤销。
- `PlatformCommandGateway`：联合授权、审计并调用座舱命令。
- `WebSocketSessionRegistry`：注册、阻止发送并关闭 Platform Session 连接。
- `UserAdminService`：用户禁用、角色变更和受控查询。
- `AuditQueryService`：角色范围内的 keyset 查询。
- `CockpitAuthority`：平台模块调用实时权威的窄 Protocol。

Repository、ORM Row、SQLAlchemy Session 和 Alembic 对象不是公共 Interface。

### 5.3 Adapter 与 Implementation

- FastAPI Router/Dependency：入站 Adapter；
- PostgreSQL Repository、Unit of Work 与 AuditSink：出站 Adapter；
- 有界 JSONL：审计 fallback Adapter；
- 内存连接注册表：当前单进程 Implementation；
- `CockpitService`：满足 `CockpitAuthority` 的实时 Implementation；
- `app.main`：创建并注入所有 Implementation 的唯一 composition root。

`app.platform` 不导入 FastAPI、SQLAlchemy 或 Alembic，也不直接导入具体
`CockpitService` 类。

### 5.4 依赖和请求流

```text
HTTP Router
  -> Origin / request validation
  -> PrincipalResolver
  -> RolePolicy AND EndpointPolicy
  -> PlatformCommandGateway
  -> CockpitAuthority
```

```text
WebSocket handshake
  -> exact Origin allowlist
  -> PrincipalResolver
  -> WebSocketSessionRegistry
  -> CockpitService snapshot broker
```

公开 Router 在 G4 Slice D 之前不得调用 PlatformCommandGateway。

## 6. PostgreSQL 模型

### 6.1 `users`

| 字段 | 约束与含义 |
| --- | --- |
| `id` | UUID 主键 |
| `username_norm` | 唯一、非空；应用统一 trim/casefold |
| `display_name` | 非空显示名 |
| `password_hash` | 成熟 Argon2id 哈希 |
| `role` | `admin/operator/viewer`，首版单角色 |
| `disabled_at` | 可空；G4 不做硬删除 |
| `created_at/updated_at` | UTC timestamptz |

禁用或角色变化在下一次请求解析时立即生效。角色变化同时撤销现有 Platform Session，
避免旧 UI 与新权限不一致。

### 6.2 `platform_sessions`

| 字段 | 约束与含义 |
| --- | --- |
| `id` | UUID 主键 |
| `user_id` | 外键到 `users`，`ON DELETE RESTRICT` |
| `token_digest` | 唯一；raw secret 的 SHA-256 digest |
| `created_at` | UTC timestamptz |
| `expires_at` | 绝对过期时间 |
| `last_seen_at` | 观测字段，G4 首版不做滑动续期 |
| `revoked_at` | 可空撤销时间 |
| `revoke_reason` | 有界、可空机器/人工原因 |

Session Row 不复制角色；解析时关联当前 User。默认绝对有效期为可配置的 8 小时。
raw secret 只存在于 HttpOnly cookie，不能进入数据库、日志、审计或前端 Store。

### 6.3 `audit_events`

AuditEvent 是通用事件，不局限于 cockpit command：

- `id`：UUID 主键，也是 reconciliation 幂等键；
- `occurred_at`：UTC timestamptz；
- `action`：稳定命名，例如 `auth.login`、`session.revoke`、
  `user.disable`、`user.role_change`、`cockpit.command`；
- `result`：`attempted/succeeded/rejected/error`；
- `delivery`：数据库记录保留原始 `primary/fallback`；
- `actor_user_id`：允许为空；已解析 User 时使用
  `ON DELETE RESTRICT` 外键保留历史引用；
- `actor_platform_session_id`：允许为空；作为历史值保存，不设置强外键；
- `actor_role`：允许为空，是事件发生时的快照；
- `actor_role` 是事件发生时的快照；
- 可选上下文：`endpoint`、`cockpit_session_id`、`command_name`、
  `correlation_id`、`target_type`、`target_id`；
- `parameters JSONB`：写入前必须 sanitize；
- `error_code` 与 `source_type`：稳定、可查询的机器值。

`lost` 只可能是运行时 delivery，因为没有介质能够持久化它。User 只禁用不删除，
其审计引用使用 `ON DELETE RESTRICT`；Platform Session 未来可以清理，因此审计中的
Platform Session ID 不设置阻断清理的强外键。fallback 重试复用同一 AuditEvent UUID，
PostgreSQL 以幂等插入消除
“实际已提交但客户端误判失败”造成的重复事件。

### 6.4 迁移与 seed

- Alembic 迁移只创建 schema、约束、索引和必要数据库权限；
- 迁移不创建密码或默认管理员；
- 初始管理员由显式 CLI seed 创建；
- migration 未到 head 必须报告 `migration_required`，不得静默运行；
- G4 当前切片不增加 Cockpit Runtime 状态表。

## 7. 认证、cookie 与 CSRF

### 7.1 登录

- 密码采用当前成熟的 Argon2id 库；具体依赖和参数在 G4 评审时锁定；
- 支持登录时 rehash；
- 无效用户名、错误密码和禁用用户返回相同 `invalid_credentials`；
- 执行统一失败延迟和适用于单进程的简单节流；
- 成功登录在一个事务中创建 Platform Session 并提交
  `auth.login/succeeded`，审计未提交就不签发 cookie；
- raw secret 由至少 32 字节 CSPRNG 生成。

### 7.2 cookie

- host-only、`HttpOnly`、`SameSite=Strict`、`Path=/`；
- HTTPS/受控部署使用 `Secure` 和 `__Host-` 名称；
- 明确的 loopback 开发模式使用不同 dev cookie 名称，可关闭 `Secure`；
- dev cookie 不得用于 LAN 部署；
- 登录和 Session 响应使用 `Cache-Control: no-store`；
- 默认开发 host 固定为 `127.0.0.1`，同一会话不混用 `localhost`。

### 7.3 Origin 与客户端声明

- 所有 cookie 认证的变更请求要求与配置完全匹配的 Origin；
- CORS 只允许明确 UI origin、必要 method/header 和 credentials；
- 前端 fetch 显式设置 `credentials: "include"`；
- 不存在状态变更 GET；
- WebSocket 握手独立校验 Origin；
- 不使用通配符、后缀或 substring Origin 匹配；
- user、role、Platform Session 和 endpoint 的客户端声明均不可信；
- endpoint 从受约束 Router/连接上下文解析，再校验 payload/source 一致性。

## 8. 事务与命令语义

### 8.1 普通命令

1. 实时查库解析 Platform Session 与当前 User；
2. 校验 RolePolicy、EndpointPolicy 和现有 Cockpit command policy；
3. 调用 CockpitService；
4. 根据真实结果写主审计，失败则写 JSONL fallback；
5. 返回真实业务结果，不用事后审计故障伪报命令失败。

审计 delivery 通过 HTTP header 返回 `primary/fallback/lost`，不改变
`gp05.v1` payload。`lost` 同时产生高严重级别结构化日志。

### 8.2 管理命令

`set_theme`、`set_system_mode` 和 `reset_session` 保持高风险类别：

1. 完成认证与联合授权；
2. 在独立短事务中 INSERT 并 COMMIT `attempted`；
3. COMMIT 成功后才调用 CockpitService；
4. 以同一 correlation ID 写 `succeeded/rejected/error`；
5. 结果事件可 fallback，但 `attempted` 不允许 fallback 代替主审计门。

`is_available()` 只用于健康诊断；真正的门是 INSERT 事务完成 COMMIT。

### 8.3 注销、撤销、禁用和角色变化

- 注销：事务内撤销 Session 并写审计，提交后清 cookie，再关闭连接；
- 管理员撤销：提交数据库和审计后，连接注册表立即阻止发送并关闭连接；
- 禁用用户：一个事务内禁用用户、撤销全部 Session 并写审计；
- 角色变化：更新角色、撤销现有 Session 并要求重新登录；
- 注册表同步标记不可发送，再 best-effort 发送关闭帧；
- 网络关闭失败不能恢复数据库中已撤销的 Session。

每个并发请求/任务使用独立 AsyncSession 和明确事务作用域，不跨 asyncio task
共享数据库 Session，也不把 PostgreSQL 与内存 CockpitService 包装成伪分布式事务。

## 9. WebSocket

- 新连接必须通过 exact Origin 与实时数据库 Session 解析；
- 内存注册表按 `platform_session_id` 管理连接；
- 注销、撤销、禁用和绝对到期立即停止发送并关闭连接；
- 已建立连接只接收 snapshot，不接受业务命令；
- PostgreSQL 在连接建立后短暂中断时，现有只读连接继续；
- 新连接和全部变更请求在数据库不可用时失败关闭；
- CockpitService broker 不查询 PostgreSQL。

## 10. 读取范围

### 10.1 Admin

- 管理用户、角色和 Platform Session；
- 查看全部已 sanitize 的平台与操作审计；
- 执行 Session revoke 并查看 fallback/reconciliation 状态。

### 10.2 Operator

- 执行白名单命令；
- 查看座舱命令、风险和恢复结果等操作历史；
- 不读取登录失败、用户管理或其他安全管理事件。

### 10.3 Viewer

- 不执行任何命令；
- 只读查看已 sanitize 的操作历史和报告；
- 不访问用户、Session 或安全管理接口。

审计查询使用有上限的 keyset pagination，以 `(occurred_at, id)` 稳定排序，
不接受任意 SQL-like filter。

## 11. 故障矩阵

| 情况 | CockpitService | 审计/持久化 | 对外结果 |
| --- | --- | --- | --- |
| Session 缺失、过期或撤销 | 不调用 | 尽可能记录拒绝 | 401 |
| Session 数据库查询失败 | 不调用 | 受限故障日志 | 503 |
| Role 或 endpoint 禁止 | 不调用 | primary/fallback 拒绝 | 403 |
| 管理命令 attempted 未提交 | 不调用 | 高严重级别告警 | 503，状态不变 |
| Cockpit 领域拒绝 | 状态不变 | rejected primary/fallback | 保留现有 4xx/409/501 |
| 普通命令成功、主审计失败 | 状态已变更 | fallback 或 lost | 成功和真实 delivery |
| 管理命令成功、结果审计失败 | 状态已变更 | attempted durable；结果 fallback/lost | 真实成功 |
| PostgreSQL 在已建 WS 后中断 | 继续只读广播 | 不写实时状态 | 现有连接继续，新连接失败 |
| 重复 reconciliation | 不受影响 | UUID 幂等忽略 | 报告重复数 |

错误必须保持真实性：

- 无效认证为 401；
- 已认证但禁止为 403；
- 数据库无法解析 Session 为 503 `database_unavailable`，不是 401；
- durable pre-audit 失败为 503 `audit_unavailable`；
- 不向客户端暴露 SQL、连接串、驱动异常或内部路径。

## 12. Fallback、reconciliation 与健康状态

- G4 首版只提供显式人工 reconciliation CLI，不运行后台同步线程；
- reconciliation CLI 是受控本地主机操作，不暴露为浏览器或公共 HTTP 动作；
- CLI 支持 dry-run、校验、幂等导入和导入报告；
- 只有完整成功后才能归档已处理文件；
- fallback 文件有界、权限受限、内容已 sanitize；
- fallback 写入失败产生 `lost` 告警；
- `/api/health` 保持核心 HMI liveness，不在每次调用时制造数据库探测抖动；
- 无身份依赖的粗粒度 platform readiness 只返回
  `ready/degraded/unavailable/migration_required`，确保数据库故障时仍可诊断；
- 受保护的详细查询只在身份服务可用时返回 `database/audit/migration` 分项；
- 两类健康接口都不暴露连接串、驱动文本、异常文本或路径。

## 13. 验证合同

### 13.1 单元测试

- 登录成功/失败、禁用用户、过期和撤销；
- raw secret 从不持久化或记录；
- admin/operator/viewer 与 endpoint 权限交集；
- forged payload endpoint/source 不能升级权限；
- 管理命令 pre-audit 失败时状态不变；
- 普通命令 primary/fallback/lost 的真实结果；
- sanitizer 边界、AuditEvent 幂等和查询范围；
- WebSocket bad Origin、缺失/撤销 Session、主动关闭和到期。

### 13.2 PostgreSQL 集成测试

- 空数据库迁移到 head；
- unique/check/FK 约束；
- use case 事务提交与回滚；
- Session resolve/revoke、用户禁用与角色变化；
- UTC/JSONB、审计排序和 keyset pagination；
- 模拟“提交成功但客户端误判失败”后的幂等 reconciliation；
- 数据库不可用和 migration 未应用。

### 13.3 执行环境

- 本地 `pnpm check` 与 `bash scripts/validate.sh` 保持无需 PostgreSQL；
- 本地集成测试通过显式 `TEST_DATABASE_URL` 运行，不要求 Docker；
- CI 提供临时 PostgreSQL service，集成测试不可跳过；
- 继续运行 `bash scripts/validate.sh` 和 `pnpm smoke:gp05`；
- 自动化结果不冒充浏览器多屏、目标机、LAN HTTPS 或备份恢复人工验证。

## 14. G4 实施切片

### Slice A — Persistence foundation

依赖、配置、engine/session factory、ORM、Alembic、Repository 和迁移测试。
不接 Router。

### Slice B — Identity / Platform Session

密码、登录/注销/me、Origin、防暴力尝试、Session 解析与撤销。仍不接 command Router。

### Slice C — Audit persistence

通用 AuditEvent、查询、PostgreSQL sink、JSONL fallback 和人工 reconciliation。

### Slice D — Command / WebSocket integration

Principal、Role+Endpoint、Gateway、管理命令 pre-audit、连接注册表和完整故障矩阵。

### Slice E — Admin / viewer demo and recovery evidence

用户/会话管理、角色界面、审计历史、完整演示、备份恢复和文档冻结。

每个 Slice 都需要独立 Issue 或明确授权、独立 jj change、focused tests、完整验证、
自审和 PR。只有人类决定是否 Squash Merge。

## 15. 已关闭决策

| ID | 决策 |
| --- | --- |
| D0 | Cockpit Session 与 Platform Session 使用独立术语和 ID |
| D1 | 不透明、严格数据库支持的 Platform Session |
| D2 | User 单角色，角色定义在代码中 |
| D3 | 成熟 Argon2id 库，G4 锁定依赖与参数 |
| D4 | SameSite Strict |
| D5 | exact Origin allowlist |
| D6 | 内存注册表主动关闭；不把数据库放入 snapshot 热路径 |
| D7 | Viewer 只读操作历史；安全/管理审计仅 Admin |
| D8 | User soft-disable |
| D9 | User actor 使用 RESTRICT FK；Session actor 为可清理的历史值 |
| D10 | 管理命令 durable attempted 后才允许 mutation |
| D11 | 变更请求实时查库并 fail-closed |
| D12 | 首版显式人工 fallback reconciliation |
| D13 | 显式 CLI seed |
| D14 | 本地可选 PostgreSQL，CI 强制 PostgreSQL 集成测试 |
| D15 | Service/UoW 明确事务边界，每 task 一个 AsyncSession |

## 16. G3 验收与后续门

G3 验收只需要证明：

- 本设计、ADR、领域词汇和决策基线一致；
- 资产包 D0–D15 均有明确结论；
- Module、Interface、Adapter、事务、失败和测试边界可执行；
- 没有 Router 接线、依赖引入、迁移或运行时能力被误报为完成；
- 完整文档 diff 和仓库验证通过。

完成上述证据后，由 Oasis 复核书面规格。只有规格再次获准，才调用 writing-plans
为 G4 Slice A 编写实施计划；该计划仍不等于实现或远端授权。

## 17. 参考

- [项目决策基线](../project/DECISION_BASELINE.md)
- [项目方向](../project/PROJECT_DIRECTION.md)
- [当前架构](../architecture.md)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html)
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
