# Supersonic：智能座舱多屏协同 HMI

> **Status: `FROZEN / MAINTENANCE_ONLY`**  
> **G5 quality baseline frozen**: 2026-08-31 (decision head `d0b2bafdeea9af69210b0640e5945abe34ffd630`, PR #94)  
> **Active graduation-design development moved to OasisSaber/Pioneer**: 2026-09-04  
> 完整收口决策见 [`docs/project/PROJECT_CLOSURE.md`](docs/project/PROJECT_CLOSURE.md)，工程与协作经验总结见 [`docs/project/PROJECT_LESSONS_LEARNED.md`](docs/project/PROJECT_LESSONS_LEARNED.md)。

面向高校毕业设计的高保真多屏协同车载人机交互（HMI）原型系统。

前端采用 React 18 + TypeScript + Vite 驱动六大显示端点；后端采用 FastAPI + Python 3.12 提供统一状态中枢，基于 `CockpitService` 维护唯一权威座舱运行态，通过 WebSocket 向全端点实时广播 `gp05.v1` 协议快照；配置 PostgreSQL 后激活平台会话、细粒度 RBAC 鉴权与不可篡改审计追踪体系。

---

## 1. 座舱人机空间与协同架构

### 1.1 人机工程多屏视距分布

系统根据车载人机工程学（HMI Ergonomics）标准将信息显示划分为不同的物理视距与安全层级：

```mermaid
graph TD
    subgraph 前方视界 ["前方前挡风远视区 (虚像视距 ~7.5m)"]
        HUD["HUD (平视显示)<br/>/hud<br/>车道指引 · 车速 · 紧急接管"]
    end

    subgraph 驾驶员仪表区 ["主驾正前主视线 (视距 ~0.8m)"]
        Cluster["Cluster (全液晶仪表)<br/>/cluster<br/>车速 · 档位 · 续航 · ADAS 告警"]
    end

    subgraph 中央控制与副驾娱乐区 ["中控台与副驾副视线 (触控视距 ~0.6m)"]
        Center["Center (中控大屏)<br/>/center<br/>高精地图 · 系统设置 · 媒体控制"]
        Passenger["Passenger (副驾娱乐)<br/>/passenger<br/>专属影音 · 路线协推 · 乘员控制"]
    end

    subgraph 协同监视与仿真注入 ["调试与总览台 (多端协同与测试)"]
        Overview["Overview (协同总览)<br/>/overview<br/>严格只读 · 六端点同屏监视"]
        Control["Control (控制注入台)<br/>/control<br/>接管触发 · 故障注入 · 状态重置"]
    end

    HUD -. "视线分层协同" .-> Cluster
    Cluster <--> "跨屏导航/警报" <--> Center
    Passenger -. "协推路线/媒体共享" .-> Center
    Center -. "状态镜像" .-> Overview
    Control ==> "HTTP 命令注入" ==> Center
```

### 1.2 软件架构与实时数据流拓扑

系统严格解耦 **座舱运行态（Cockpit Runtime）** 与 **平台管理与审计（Platform Access & Audit）** 两个有界上下文（见 [`CONTEXT.md`](CONTEXT.md) 与 [`GLOSSARY.md`](GLOSSARY.md)）：

```mermaid
flowchart TD
    subgraph Frontend ["前端 React 18 + TypeScript (Vite)"]
        direction TB
        E_HUD["HUD (/hud)"]
        E_Cluster["Cluster (/cluster)"]
        E_Center["Center (/center)"]
        E_Passenger["Passenger (/passenger)"]
        E_Overview["Overview (/overview · 只读)"]
        E_Control["Control (/control · 命令)"]
        E_Platform["PlatformConsole (/platform · 管理)"]
    end

    subgraph Backend ["FastAPI 后端 (Python 3.12)"]
        direction TB
        subgraph CockpitRuntime ["Cockpit Runtime (实时运行态上下文)"]
            CS["CockpitService (唯一权威实时状态单例)"]
            WS["WebSocket Server (广播 gp05.v1 Snapshot)"]
            HTTP_CMD["Command Router (端点命令验证与转发)"]
            CS -->|生成权威全量快照| WS
            HTTP_CMD -->|执行合法状态变更| CS
        end

        subgraph PlatformContext ["Platform Access & Audit (平台管理与审计上下文)"]
            Auth["Platform Session & Auth (RBAC 角色鉴权)"]
            Audit["Audit Logger (不可变追加式审计)"]
            Audit -->|Durable Attempted / Succeeded| PG[("PostgreSQL 数据库")]
            Auth -->|会话存储 / 状态核验| PG
        end
    end

    %% 实时广播
    WS ==>|WebSocket 广播 gp05.v1 快照| E_HUD
    WS ==>|WebSocket 广播 gp05.v1 快照| E_Cluster
    WS ==>|WebSocket 广播 gp05.v1 快照| E_Center
    WS ==>|WebSocket 广播 gp05.v1 快照| E_Passenger
    WS ==>|WebSocket 监听| E_Overview
    E_Control -->|HTTP POST 状态变更命令| HTTP_CMD

    %% 平台管理
    E_Platform <-->|HTTP REST / 身份登录与会话| Auth
    E_Platform <-->|查询只读审计流水与用户| Audit
    Auth -. "撤销平台会话时主动切断对应连接" .-> WS
```

---

## 2. 端点协同与路由矩阵

| 端点名称 | 默认访问 URL | 权限模式 | 核心职责与交互特性 |
| --- | --- | --- | --- |
| **Cluster (全液晶仪表)** | `http://localhost:5173/cluster` | 双向接收快照 | 驾驶核心指标（车速/电量/档位）、ADAS 风险告警与 Day/Night 模式自适应 |
| **HUD (平视显示)** | `http://localhost:5173/hud` | 双向接收快照 | 极简投影视界、车道诱导指示与关键接管即时预警 |
| **Center (中控大屏)** | `http://localhost:5173/center` | 双向交互 | 完整高精导航地图、系统设置、媒体播放与车辆总控交互 |
| **Passenger (副驾娱乐)** | `http://localhost:5173/passenger` | 双向交互 | 独立影音娱乐、副驾专属控制、向中控协同推送导航路线 |
| **Overview (协同总览)** | `http://localhost:5173/overview` | 严格只读（Snapshot-only） | 六端点协同总览墙，仅广播监听，任何客户端命令均 fail-closed |
| **Control (控制注入台)** | `http://localhost:5173/control` | 命令端点（Command Gateway） | 模拟驾驶员接管、故障注入、风险生命周期事件注入与状态重置 |
| **Platform (管理控制台)** | `http://localhost:5173/platform` | RBAC 鉴权管理 | 用户身份登录、会话撤销、操作审计日志与数据备份恢复 |

---

## 3. 快速开始

### Tier 1：30 秒极速体验（纯 Mock 模式，无需数据库）

若仅需体验六屏协同联动与 HMI 视觉交互，可直接启动无数据库依赖的纯 Mock 模式：

```powershell
# 1. 复制运行时环境变量配置
Copy-Item .env.example .env

# 2. 一键安装依赖并完成初始化检查
.\scripts\setup.ps1

# 3. 启动前后端联合开发服务
pnpm dev
```

服务启动后，在浏览器中分别打开以下页面即可观察跨屏实时联动：
- 仪表与平视显示：[Cluster](http://localhost:5173/cluster) · [HUD](http://localhost:5173/hud)
- 交互与娱乐：[Center](http://localhost:5173/center) · [Passenger](http://localhost:5173/passenger)
- 协同调试与控制：[Overview 总览](http://localhost:5173/overview) · [Control 控制注入台](http://localhost:5173/control)

在 `Control` 端点点击接管或触发故障，所有已连接屏幕将通过 WebSocket 毫秒级同步最新 `gp05.v1` 权威快照。

### Tier 2：完整平台与审计模式（接入 PostgreSQL）

若需体验多用户登录、细粒度 RBAC 权限（`admin/operator/viewer`）、会话撤销与不可篡改审计追踪体系：

1. 在本地或 Docker 中启动 PostgreSQL 服务；
2. 在根目录 `.env` 中配置数据库连接字符串：
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/supersonic
   ```
3. 执行数据库迁移与初始化 Seed 数据：
   ```powershell
   pnpm db:migrate
   ```
4. 启动服务后访问 [Platform 管理控制台](http://localhost:5173/platform)：
   - 管理员身份：`admin` 用户可执行用户管理、会话撤销、敏感参数修改及审计日志核验；
   - 操作员 / 访客身份：按最小权限原则只读查看或受限操作；
   - 备份与恢复验证：支持通过 `pg_dump` 备份及隔离 `*_restore_test` 自动化恢复测试。

完整配置合同与环境变量说明见 [`docs/development.md`](docs/development.md)。

---

## 4. 质量工程与验证矩阵

本项目遵循严格的高可信工程实践，构建了三层递进质量防护网：

```powershell
# 1. 轻量化日常门禁（类型检查、Lint、前后端单测）
pnpm check

# 2. 权威全量验证（提交与 Push 前强制执行）
bash scripts/validate.sh

# 3. 真实进程 E2E 冒烟测试（无头浏览器多端点自动化冒烟）
pnpm smoke
```

### Windows 视觉验收矩阵

项目已建立完整的视觉基线与自动化回归证据集，详见 [`docs/VISUAL_ACCEPTANCE_MATRIX.md`](docs/VISUAL_ACCEPTANCE_MATRIX.md)。
视觉证据覆盖：
- 正常驾驶态、多段式导航诱导与路线变更；
- 风险触发、紧急接管、确认处置与安全恢复生命周期；
- Day / Night 主题自适应无缝切换；
- 数据域离线降级、`systemMode=offline`、`systemMode=stale` 以及后端连接异常状态；
- 数据域离线、系统模式与传输状态分别独立记录与可视化呈现，杜绝混淆。

---

## 5. 项目状态与演进记录

### 5.1 当前基线状态（G5 已冻结）

- **冻结宣告**：2026-08-31 由 Oasis 批准宣告 G5 核心基线冻结（`FREEZE_READY`），详见 [`DECISION_BASELINE.md` §0.3](docs/project/DECISION_BASELINE.md)。
- **已交付闭环**：
  - GP22 第一轮设计 Token 与组件规范全量实现；
  - 六大端点状态机与 `gp05.v1` 协议实时协同闭环；
  - G4 平台登录、Platform Session 撤销、`admin/operator/viewer` RBAC 与不可篡改审计持久化；
  - 数据库备份恢复验证工具链与脱敏恢复测试。

### 5.2 项目正式收口（FROZEN / MAINTENANCE_ONLY）

因毕业设计主线调整至 Pioneer，Supersonic 活跃产品研发于 2026-09-04 正式结束，仓库进入 `FROZEN / MAINTENANCE_ONLY` 维护状态：
- 真实地图 Provider、真实 VehicleVision、AI 语音、多显示部署和 Web3D 在项目收口前未完成实现，保持为历史规划证据，不再作为 Supersonic 的活跃路线；
- 完整收口决策见 [`docs/project/PROJECT_CLOSURE.md`](docs/project/PROJECT_CLOSURE.md)；
- 项目工程与敏捷协作经验总结见 [`docs/project/PROJECT_LESSONS_LEARNED.md`](docs/project/PROJECT_LESSONS_LEARNED.md)。

历史审查记录与交付物归档见 [`deliverables/g5-review/`](deliverables/g5-review/)。

---

## 6. 系统边界与合规声明

> [!IMPORTANT]
> **学术原型与真实性声明**  
> 本系统作为面向毕业设计的**本地可信环境 Mock 原型**进行开发与展示。  
> - 当前后端仅实现 `APP_MODE=mock`，严禁将 `local_fallback`、`simulated_event` 或静态演示画面表述为真实物理雷达感知、车载视觉推理或量产车辆功能；  
> - 平台模式不等于面向公网的开放式互联网多租户 SaaS 服务；  
> - 本项目严格遵守学术道德与真实性规范，所有能力声明均以自动化测试用例与代码事实为准。

> [!WARNING]
> **第三方与 Vision 许可证合规门禁**  
> 当前版本**未采用且未集成 Ultralytics/YOLO**：代码库未导入或调用相关库，未内置任何模型权重，亦未分发包含该组件的发行制品。  
> 若后续研发计划重新引入相关视觉组件，必须严格执行许可证合规审查（在 AGPL-3.0 开源路线与商业授权路线之间做出明确选择），并在 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 与 [`docs/08-data-and-license-log.md`](docs/08-data-and-license-log.md) 中完整归档授权凭证。

---

## 7. 核心文档入口

| 内容维度 | 对应权威文档入口 |
| --- | --- |
| **当前范围与决策基线** | [`docs/project/DECISION_BASELINE.md`](docs/project/DECISION_BASELINE.md) |
| **项目收口决策** | [`docs/project/PROJECT_CLOSURE.md`](docs/project/PROJECT_CLOSURE.md) |
| **工程与协作经验总结** | [`docs/project/PROJECT_LESSONS_LEARNED.md`](docs/project/PROJECT_LESSONS_LEARNED.md) |
| **领域模型与有界上下文** | [`CONTEXT.md`](CONTEXT.md) · [`GLOSSARY.md`](GLOSSARY.md) |
| **系统架构与分层设计** | [`docs/architecture.md`](docs/architecture.md) |
| **当前进度与缺陷跟踪** | [`docs/project/PROJECT_PROGRESS.md`](docs/project/PROJECT_PROGRESS.md) |
| **开发指南与配置合同** | [`docs/development.md`](docs/development.md) |
| **Windows 视觉验收矩阵** | [`docs/VISUAL_ACCEPTANCE_MATRIX.md`](docs/VISUAL_ACCEPTANCE_MATRIX.md) |
| **实施路线图与执行门** | [`docs/project/IMPLEMENTATION_ROADMAP.md`](docs/project/IMPLEMENTATION_ROADMAP.md) |
| **Agent 协作治理规范** | [`AGENTS.md`](AGENTS.md) |

---

## 8. 目录结构

```text
Supersonic/
├── apps/
│   ├── frontend/         # React 18 + TypeScript + Vite 前端 (六端点与平台控制台)
│   └── backend/          # FastAPI + Python 3.12 后端 (CockpitService 与平台服务)
├── contracts/            # 跨端协议合同 (gp05.v1 Pydantic / TypeScript 契约)
├── docs/                 # 决策基线、系统架构、视觉验收矩阵与演进路线
├── deliverables/         # 阶段交付物与复审记录
├── scripts/              # 本地安装、初始化与自动化验证脚本
└── tests/                # 跨端集成与 E2E 自动化测试
```

## 使用许可

本项目用于毕业设计作品展示与技术学术审查。当前未授予复制、再分发、修改或商业使用许可；第三方依赖与引用资料分别适用其原有开源许可和协议条款。
