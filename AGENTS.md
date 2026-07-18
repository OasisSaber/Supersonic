# Agent 项目入口

## 项目事实

- 目标：智能座舱四屏协同 HMI（主仪表、HUD、中控、副驾）。
- 技术：Figma、React + TypeScript + Vite、FastAPI + Python、WebSocket、pnpm、uv、Jujutsu。
- 唯一当前决策基线：`docs/ai-collaboration/PROJECT_DECISION_BASELINE.md`。
- `apps/` 内的道路风险、驾驶员监测与 LLM 是早期技术基线；除非任务明确涉及，不要把它们当作最终课题范围。

## 开始与边界

1. 读取 `docs/ai-collaboration/CURRENT_HANDOFF.md`，运行 `jj status` 和 `jj log -n 5`。
2. 进入 `apps/frontend` 或 `apps/backend` 前，读取该目录的 `AGENTS.md`。
3. 编排任务只读取其合同列出的输入文件和 runtime 状态；批准的 `orchestration/tasks/*.json` 不可修改。
4. 若 workspace lease 或 handoff 显示其他所有者，停止并请求用户决定；不要覆盖现有改动。
5. 所有可变版本操作使用 jj；每个 change 只做一个可验证任务。未经明确授权，不 push、建 PR 或发布。

### P0：外部推送与 PR 门禁

- Codex 只能先提议 push 或创建 PR；执行前必须展示远端及可见性/信任状态、bookmark 与 revision 范围、文件和敏感数据类别、验证结果、PR 目标与明确排除项。
- Oasis 必须分别明确批准本次 push 和本次 PR；一次批准不延续到后续 push，不自动包含 PR、发布或公开分享。
- push 失败、被平台阻止或远端状态变化后不得自动重试；必须更新摘要并重新请求批准。未经成功回执，不得在 handoff 中写成已推送或已创建 PR。

## 默认不要读取

`node_modules/`、`.pnpm-store/`、`.uv-cache/`、`.uv-python/`、`.venv/`、`orchestration/runtime/`、`tmp/`、`outputs/`、`materials/` 和 `PreDesign/idea-archive/`。

这些目录分别是依赖/缓存、运行日志、临时或生成物、学校原件和历史设计资料；只在相关任务中按文件读取，禁止整目录加载。文档入口见 `docs/README.md`。

## 核心约束

- 共享车辆状态只允许一个权威来源；四屏不能维护相互矛盾的业务状态。
- Figma Variables 映射到集中式代码 Token；组件覆盖正常、交互、禁用、告警、空数据和降级状态。
- 不为展示引入 MQTT、CAN、CARLA、ROS2、Docker 或数据库；除非需求和验收明确要求。
- 不修改 `materials/` 中学校原始文件；不提交密钥、私人素材、模型权重、缓存或构建产物。
- Codex 负责架构、公共协议、设计系统、依赖、安全、发布和最终复核；OpenCode 仅执行已批准且标为 `DELEGATABLE` 的合同。

## 验证

- 仅文档：检查链接、路径、事实和术语。
- 前端：`pnpm --filter @cockpit/frontend lint`、`test --run`、`build`。
- 后端：`pnpm lint:backend`、`pnpm test:backend`。
- 跨层、依赖或交付：`pnpm check`；需要运行态证据时再执行 `pnpm smoke`。

完成或交接前更新 `docs/ai-collaboration/CURRENT_HANDOFF.md`；详细流程见 `docs/ai-collaboration/HANDOFF_PROTOCOL.md` 与 `docs/development.md`。
