# 项目进度

- 最后更新：2026-07-22
- 证据原则：本文件以当前源码、合同和测试为主。旧工作流中的命令结果只作为历史验证证据，不等同于当前验证。

## 当前阶段

- `FROZEN` — GP21 视觉与交互基线。依据：[`DECISION_BASELINE.md`](./DECISION_BASELINE.md) 的冻结约束；本次未重新进行视觉人工验收。
- `IMPLEMENTED_WITH_KNOWN_DEFECTS` — `GP05-IMPL-01` 合同、Token 与领域模型。依据：`contracts/gp05/v1/`、前后端 `gp05.v1` 合同和合同测试；运行态合同容错仍有风险。
- `IMPLEMENTED_WITH_KNOWN_DEFECTS` — `GP05-IMPL-02` FastAPI 单一状态权威、HTTP 命令和 WebSocket 快照。依据：`apps/backend/app/cockpit_state.py`、`apps/backend/app/main.py` 与对应测试；存在新会话 revision 和端点连通性风险。
- `PARTIAL` — `GP05-IMPL-03` 四端 React 壳层与设计系统。依据：`/cluster`、`/hud`、`/center`、`/passenger`、`/overview`、`/control` 路由及 `CockpitScreen`；`/control` 当前回退至 Center 画面，未形成独立控制台。
- `PARTIAL` — `GP05-IMPL-04` 导航接力、风险接管和副驾协作。依据：后端命令状态转换及 Center/Passenger UI；仅覆盖确定性本地演示流程。
- `NOT_IMPLEMENTED` — `GP05-IMPL-05` 高德 MapProvider。当前仅有 `local_fallback` 路线与 degraded 状态。
- `NOT_IMPLEMENTED` — `GP05-IMPL-06` MySQL 持久化与审计。
- `NOT_IMPLEMENTED` — `GP05-IMPL-07` 与 `GP05-IMPL-08` VehicleVision Worker 和真实视觉推理。当前风险事件明确标记为 `simulated_event`，不得视为真实视觉能力。
- `PENDING_VERIFICATION` — `GP05-IMPL-09` Web3D。未在当前前端源码和本次运行证据中确认可用实现或性能结果。
- `PARTIAL` — `GP05-IMPL-10` 控制台和全链路集成。权威快照与命令链路存在，但独立控制台、真实外部服务和完整诊断指标未完成。
- `NOT_IMPLEMENTED` — `GP05-IMPL-11` 性能、故障恢复与答辩证据包。
- `GATED` — `GP05-IMPL-12` 受约束 AI 语音，等待核心门槛完成后再评估。

## 已实现产品能力

- 版本化 `gp05.v1` TypeScript/Pydantic 合同，包含端点、命令、快照、风险生命周期、数据健康和乘客状态。
- FastAPI 内存权威状态、命令权限校验、HTTP snapshot/command API，以及端点 WebSocket 全量 snapshot 广播。
- Cluster、HUD、Center、Passenger 和 Overview 页面消费同一快照；Center 可进行本地路线预览/确认与风险处置，Passenger 可控制媒体、隐私和旅程建议。
- `takeover` 仅生成带 `simulated_event` 来源标签的演示风险，并驱动 `active → acknowledged → resolved → recovery` 和媒体抑制。

## 历史验证证据

- 2026-07-19 的历史验证记录曾运行 `pnpm check`，报告后端 22 项、前端 8 项测试及前端构建通过。
- 该结果来自已删除的旧状态记录，仅保留为历史证据；以下“本次实际验证结果”才是当前结论。

## 本次实际验证结果

- 2026-07-22 23:01:10 +08:00：执行 `pnpm check` 并通过。后端 Ruff 与前端 ESLint 通过；后端 pytest 为 22 通过（1 条第三方弃用警告）；前端 Vitest 为 5 个文件、8 个测试通过；前端生产构建通过。
- 2026-07-22 23:02 +08:00：在本地启动 FastAPI 后执行 `pnpm smoke` 并通过，覆盖 mock `/api/health`、`/api/events`、`/api/trips/demo`、mock report 与 `/ws/simulation` 的两条消息序列。该命令仅验证旧 mock HTTP/WebSocket 链，不证明 GP05 核心四屏链路通过。
- 2026-07-22 23:03 +08:00：完成 Git 跟踪 Markdown 本地链接与路径检查、旧工作流关键词和路径残留搜索，以及 Git diff 范围检查。工作流残留检查已在本轮清理后完成；未发现旧开发工作流、Agent 编排或失效路径残留。
- 已确认：本轮修正仅修改文档与工作流残留，未修改产品源码、协议或产品测试。

## 已知产品缺陷与风险

- Store 仅按 revision 拒绝旧 snapshot；新 session 若 revision 较低，可能被前端拒绝。
- `reset_session` 后客户端对端点连通性的旧状态可能错误保留为 offline。
- `/control` 当前经通用端点回退为 Center 页面，未形成独立控制台。
- 已确认缺陷：`/overview` 直接复用可交互的 Center 和 Passenger 组件；Center 以 `center` 身份发送命令，Passenger 以 `passenger` 身份发送命令，而 overview 合同权限为空，因此可绕过 overview 的只读设计。
- `pnpm smoke` 现有范围未证明 GP05 核心 WebSocket/四屏链路。
- navigation data health 与本地降级路线状态可能不一致。
- 前端运行时合同校验覆盖不完整，WebSocket JSON 解析缺少异常保护。

## 待确认事项

- 三档分辨率的运行态视觉回归、截图和人工可读性结论。
- 真实高德凭据、MySQL、VehicleVision、Web3D、性能和故障恢复的实施范围与验收证据。
- 指导教师对创新点、AIGC 声明和最终答辩提交格式的正式要求。
