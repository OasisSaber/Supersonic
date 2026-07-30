# 系统架构

## 项目上下文

本系统是用于毕业设计开发和答辩的本地多屏 HMI 原型。默认环境是一台可信 Windows 主机、一个 FastAPI 进程和多个本地浏览器页面。当前不面向公共互联网、多租户、量产车辆网络或企业级高可用部署。

工程标准应优先保证：

- 四屏状态一致；
- 命令权限与端点职责一致；
- 重启、重置、断线和错误输入可恢复；
- Mock、真实来源和降级状态可区分；
- 主要演示流程可确定性重演。

## 当前目标

主驾驶仪表、HUD、中控屏和副驾驶屏共享同一权威车辆状态。Overview 用于只读四屏编排，Control 用于本地答辩场景和会话控制。

Figma/Make 是冻结的视觉意图参考；运行时实现以 React + TypeScript 前端、FastAPI 后端和 WebSocket 全量快照广播为核心。

## 分层

| 层 | 职责 | 入口 |
| --- | --- | --- |
| 设计与合同 | GP21 视觉参考、Token、端点、状态和消息合同 | `docs/design/`、`contracts/gp05/` |
| 前端 | 四屏呈现、交互、只读 Overview、Control、降级和错误恢复 | `apps/frontend/` |
| 后端 | 权威状态、命令处理、HTTP/WebSocket、确定性 Mock 场景 | `apps/backend/` |
| 项目治理 | 当前范围、进度、优先级、验证证据和开放 Issue | `docs/project/` |
| 条件性适配器 | 真实地图、持久化、Vision、Web3D、AI | 仅在独立 Issue 触发后加入 |

## 默认运行拓扑

```text
Control / Center / Passenger commands
                  │
                  ▼
        FastAPI authoritative state
          │        │        │
          │ HTTP   │ WS     │ deterministic Mock/events
          ▼        ▼        ▼
      resources   full snapshots
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    Cluster/HUD   Center     Passenger
        │
        └──────────────► Overview (read-only composition)
```

所有产品业务状态都由 FastAPI 确认。前端不得通过本地猜测、乐观写入或独立计数器形成第二套业务真相。

## 核心不变量

1. **单一权威状态**：四屏不能维护相互矛盾的车辆、导航、风险或乘客状态。
2. **Session-aware 顺序**：revision 只在同一 session 内比较；新 session 必须能够替换旧 session。
3. **完整快照恢复**：重连后通过最新 snapshot 恢复，不依赖旧事件重放。
4. **服务端端点边界**：端点权限最终由服务端拥有的请求/连接上下文决定，不只信任客户端自报字段。
5. **Overview 只读**：Overview 不能挂载可发送命令的 Center/Passenger 控件。
6. **Control 不绕过状态机**：Control 发送与正常界面相同的 command，不直接修改 Store 或屏幕状态。
7. **来源明确**：`LIVE CAMERA`、`VIDEO INFERENCE`、`SIMULATED EVENT` 和本地路线降级不能混淆。
8. **错误数据隔离**：非法 JSON、错误协议或不完整 snapshot 不能进入 Store。
9. **降级不伪造**：stale/offline 显示最后权威值和明确提示，不生成看似实时的替代值。
10. **增强不阻断核心**：地图、数据库、Vision、Web3D 或 AI 失败不能阻断 Cluster、HUD 和关键告警。

## 当前端点

| 路由 | 角色 | 当前状态 |
| --- | --- | --- |
| `/cluster` | 主驾驶仪表 | 已实现，继续修复状态与风险一致性 |
| `/hud` | 最低认知负荷提示 | 已实现，继续修复风险一致性 |
| `/center` | 路线、详情和确认操作 | 已实现本地演示流程 |
| `/passenger` | 媒体、隐私和旅程协作 | 已实现本地演示流程 |
| `/overview` | 四屏只读编排 | 存在命令边界缺陷，Issue #7 |
| `/control` | 本地答辩控制 | 当前回退为 Center，Issue #17 |

其他已编号架构缺陷见 [`project/PROJECT_PROGRESS.md`](project/PROJECT_PROGRESS.md)。

## 条件性组件

### VehicleVision

核心稳定后优先加入一个真实疲劳/分心场景。Vision Worker 只提交候选事件，不直接操作屏幕；风险策略和 FastAPI 决定最终状态。

### 持久化

只有历史查询、论文或指导教师明确要求时才加入。数据库不是实时状态源，失败时不能阻断四屏。

### 地图

当前本地确定性路线用于验证跨屏接力。真实地图 Provider 只在答辩必须展示地点检索时实施。

### Web3D 和 AI

两者均为增强能力。Web3D 必须有静态 fallback；AI 只能复用受约束 command。它们都不是当前核心架构的硬依赖。

## 架构非目标

当前不建设：

- 多租户、企业账户和公共身份平台；
- 多节点高可用、分布式状态或消息中间件；
- ROS2、CARLA、MQTT 或量产车总线接入；
- 公共 API 网关、WAF 或云运维平台；
- 通用插件沙箱和不可信代码执行；
- 全平台安装包和发行基础设施。

若运行模型从本地可信环境变为公共或多人部署，必须通过新的架构 Issue 重新评估安全和部署边界。