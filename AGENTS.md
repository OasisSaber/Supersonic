# 项目入口

## 项目事实

- 目标：智能座舱四屏协同 HMI（主仪表、HUD、中控、副驾）。
- 技术：Figma、React + TypeScript + Vite、FastAPI + Python、WebSocket、pnpm、uv、Git。
- 唯一当前决策基线：`docs/project/DECISION_BASELINE.md`。
- `apps/` 内的道路风险、驾驶员监测与 LLM 是早期技术基线；除非任务明确涉及，不要把它们当作最终课题范围。

## 开始工作

1. 阅读与当前任务相关的 `docs/project/` 文档，运行 `git status` 和 `git log --oneline -5`。
2. 进入 `apps/frontend` 或 `apps/backend` 前，读取该目录的 `AGENTS.md`。
3. 不覆盖其他协作者的改动；发现冲突时停止并请求用户决定。
4. 每个 commit 只做一个可验证任务。未经明确授权，不 push、不创建 PR、不发布。

## 核心约束

- 共享车辆状态只允许一个权威来源；四屏不能维护相互矛盾的业务状态。
- Figma Variables 映射到集中式代码 Token；组件覆盖正常、交互、禁用、告警、空数据和降级状态。
- 不为展示引入 MQTT、CAN、CARLA、ROS2、Docker 或数据库；除非需求和验收明确要求。
- 不修改 `materials/` 中学校原始文件；不提交密钥、私人素材、模型权重、缓存或构建产物。

## 默认不读取

`node_modules/`、`.pnpm-store/`、`.uv-cache/`、`.uv-python/`、`.venv/`、`tmp/`、`outputs/`、`materials/` 和 `PreDesign/idea-archive/`。

这些目录分别是依赖/缓存、运行日志、临时或生成物、学校原件和历史设计资料；只在相关任务中按文件读取，禁止整目录加载。

## 验证

- 仅文档：检查链接、路径、事实和术语。
- 前端：`pnpm --filter @cockpit/frontend lint`、`test --run`、`build`。
- 后端：`pnpm lint:backend`、`pnpm test:backend`。
- 跨层或交付：`pnpm check`；需要运行态证据时再执行 `pnpm smoke`。
