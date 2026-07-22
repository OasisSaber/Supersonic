# 系统架构

## 当前目标

四个同等重要的 HMI 端点共享同一权威车辆状态：主驾驶仪表、HUD、中控屏和副驾驶屏。Figma 是设计源；运行时实现以 React + TypeScript 前端、FastAPI 后端和 WebSocket 状态广播为核心。

## 分层

| 层 | 职责 | 入口 |
| --- | --- | --- |
| 设计与合同 | 视觉 Token、端点、状态与消息合同 | `docs/design/`、`contracts/gp05/` |
| 前端 | 四屏呈现、只读状态消费、降级表现 | `apps/frontend/` |
| 后端 | 权威状态、命令处理、HTTP/WebSocket | `apps/backend/` |
| 项目决策与进度 | 冻结范围、实施路线、验证证据与已知风险 | `docs/project/` |

## 不变量

- 共享状态只有一个权威来源；前端不复制或推断相互冲突的业务状态。
- HTTP 面向命令和资源；WebSocket 面向持续快照广播。
- 设计 Token 必须可映射到实现；不能在页面散落无来源的临时样式。
- 早期道路风险、驾驶员监测和 LLM 模块仅作技术基线。

详细且可追溯的决策以 `project/DECISION_BASELINE.md` 为准；当前实现范围、验证证据和已知风险见 `project/PROJECT_PROGRESS.md`。历史方案仅在任务明确涉及时阅读 `archive/` 或 `PreDesign/idea-archive/`。
