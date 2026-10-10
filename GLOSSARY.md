# Supersonic Domain Glossary

Supersonic 智能座舱多屏协同 HMI 原型的领域模型词汇表，统一 Cockpit Runtime 与 Platform Access/Audit 两个有界上下文的核心术语。详细规范与字段要求见 [`CONTEXT.md`](CONTEXT.md)。

## Cockpit Runtime（座舱运行态）

负责车辆、导航、风险、媒体、端点连接、Cockpit Session、revision 和完整快照。`CockpitService` 是实时状态的唯一权威。

**CockpitService**:
FastAPI 进程中维护唯一权威座舱运行态的核心单例服务，通过 WebSocket 向所有已连接端点广播最新快照。
_Avoid_: Database service, State store

**Cockpit Session**:
座舱运行时状态重置（reset）后更新的 `gp05.v1` 实例标识，代表一次连续的座舱运行会话。
_Avoid_: Platform Session, Login session

**Cluster (仪表屏)**:
位于主驾驶正前方的物理屏幕，负责车速、电量、档位等核心驾驶指标显示与 ADAS 安全告警。
_Avoid_: Center screen, Dashboard

**HUD (平视显示)**:
投射在驾驶员前风挡视线区域的虚像显示，提供精简车速、车道指引与紧急接管视界。
_Avoid_: Cluster, Navigation screen

**Center (中控屏)**:
位于座舱中央的主交互屏，提供完整地图导航、车辆设置、多媒体控制与系统交互。
_Avoid_: Tablet, Infotainment only

**Passenger (副驾屏)**:
位于副驾驶前方的专属娱乐屏，支持独立影音娱乐及向中控屏协同推送导航路线。
_Avoid_: Co-pilot, Rear screen

**Overview (协同总览)**:
严格只读的六端点协同监视端点，仅接收并可视化所有屏幕的当前状态快照，拒绝任何直接写控制。
_Avoid_: Admin dashboard, Control panel

**Control (控制注入台)**:
用于模拟测试与演示的命令注入端点，通过 HTTP 命令网关向 CockpitService 注入接管、故障及状态变更。
_Avoid_: Direct DB writer, Overview

## Platform Access and Audit（平台访问与审计）

负责平台用户、数据库认证会话、RBAC 角色鉴权、审计事件记录与恢复验证。不拥有座舱运行态。

**Platform Session**:
由 PostgreSQL 数据库支持、具备绝对过期时间且可由管理员主动撤销的用户认证会话。
_Avoid_: Cockpit Session, Browser session

**Principal**:
服务端基于有效 Platform Session 与当前持久 User 解析出的安全主体身份。
_Avoid_: Client token claim, Frontend role

**Role**:
平台访问控制类别，当前支持 `admin`（管理员）、`operator`（操作员）与 `viewer`（只读访客）。
_Avoid_: Endpoint permission, Driver profile

**AuditEvent**:
记录于 PostgreSQL 的不可变、追加式安全与管理审计事件，具备 attempted/succeeded 状态与落库交付状态。
_Avoid_: Debug log, System telemetry
