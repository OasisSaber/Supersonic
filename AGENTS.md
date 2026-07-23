# Agent 项目入口

> 本文件是本仓库唯一具有约束力的通用 Agent 工作流规则来源。README、CONTRIBUTING、开发文档和模板只能解释或辅助执行，不能覆盖本文件。

## 项目事实

- 目标：智能座舱四屏协同 HMI（主仪表、HUD、中控、副驾）。
- 技术：Figma、React + TypeScript + Vite、FastAPI + Python、WebSocket、pnpm、uv、Jujutsu。
- 默认分支：`main`；验证入口：`bash scripts/validate.sh`。
- 唯一当前决策基线：`docs/project/DECISION_BASELINE.md`。
- `apps/` 内的道路风险、驾驶员监测与 LLM 是早期技术基线；除非任务明确涉及，不要把它们当作最终课题范围。

## 权威顺序

1. 系统安全、法律与平台权限；
2. 项目安全、隐私、合规和数据保护要求；
3. 受保护分支、发布、部署和破坏性操作限制；
4. 本文件中的通用工作流规则；
5. 当前 GitHub Issue 或当前会话中的明确人类授权；
6. 项目架构、冻结决策、测试和交付资料；
7. README、CONTRIBUTING、开发文档和其他辅助材料。

Issue 或授权只能界定目标、范围和验收条件，不能覆盖安全、隐私、受保护分支、发布、部署或破坏性操作限制。

## 开始工作

1. 阅读当前 Issue，或确认当前会话中的明确人类授权；
2. 阅读本文件与任务相关的 `docs/project/` 文档；进入 `apps/frontend` 或 `apps/backend` 前，读取局部 `AGENTS.md`；
3. 运行 `jj status`、`jj log -n 5`，并在新任务前运行 `jj git fetch`；
4. 确认不覆盖、删除或混入来源不明的修改。

## 两条任务路径

### 复杂任务

GitHub Issue → 一个 jj change → 实现与验证 → Agent 自审 → Pull Request → 人类决定是否 Squash Merge。

适用于跨模块、范围较大、有歧义，或涉及架构、公共接口、持久化数据、依赖、外部服务、部署与发布的工作。Issue 必须记录目标、范围、验收条件和排除项。

### 小型低风险任务

当前会话明确人类授权 → 一个 jj change → 实现与验证 → Agent 自审 → Pull Request 记录授权来源和范围 → 人类决定是否 Squash Merge。

仅适用于目标清晰、范围小、易回滚，且不涉及架构、公共接口、持久化数据、部署、发布、远端数据或破坏性操作的工作。没有 Issue 时不得伪造编号；需要扩大范围时必须停止并转为 Issue 路径。

## jj change 与工作区

- 一个任务对应一个可验证的 jj change，并使用短生命周期 bookmark；不维护长期开发分支。
- 不混入无关修改，也不覆盖来源不明的修改。
- push 前阅读完整 diff，并检查范围、误删、临时文件、缓存和无关生成物。
- 不擅自重写已发布历史。

## 项目边界与卫生

- 共享车辆状态只允许一个权威来源；四屏不能维护相互矛盾的业务状态。
- Figma Variables 映射到集中式代码 Token；组件覆盖正常、交互、禁用、告警、空数据和降级状态。
- 不为展示引入 MQTT、CAN、CARLA、ROS2、Docker 或数据库，除非需求和验收明确要求。
- 不修改 `materials/` 中学校原始文件；不提交密钥、私人素材、模型权重、缓存或构建产物。
- 默认不读取 `node_modules/`、`.pnpm-store/`、`.uv-cache/`、`.uv-python/`、`.venv/`、`tmp/`、`outputs/`、`materials/` 或 `PreDesign/idea-archive/`；仅在任务需要时按文件读取。

## 验证与自审

- 文档改动检查链接、路径、事实与术语；前端改动运行 lint、测试和构建；后端改动运行 Ruff 与 pytest；跨层或交付改动运行 `pnpm check`。运行态证据需要时再单独运行 `pnpm smoke`。
- push 前必须运行 `bash scripts/validate.sh`。失败时必须修复并重跑，不得将失败或未验证状态表述为成功。
- 创建或更新 PR 前，Agent 必须对照任务来源检查结果、阅读完整 diff、记录真实验证、确认未扩大范围、清除调试代码/临时文件/缓存/失效引用，并记录已知限制和未覆盖项。

## 外部操作与人工保留

- 当当前 Issue、当前会话或任务说明已明确记录目标远端、Issue/授权来源、bookmark、base branch、任务目标、允许文件范围以及 Agent 可 push 和创建/更新关联 PR 时，该任务级授权覆盖同一 bookmark 的首次及后续普通 push、关联 PR 的创建和范围内更新；远端、Issue、bookmark、base、PR 和任务范围未实质变化时，普通网络或非权限技术失败可重试。
- 未取得上述任务级远端授权时，Agent 可完成本地实现与验证，但在首次产生远端影响前必须请求一次明确授权，并列明远端、可见性、Issue、bookmark、base、文件范围、敏感信息检查和验证结果。
- 每次 push 前仍必须阅读完整 diff，检查范围、误删、临时文件、生成物与敏感信息，并运行当前任务要求的验证；验证失败不得 push。
- 更换远端、可见性、Issue、任务目标、bookmark、base 或目标 PR，扩大范围/敏感数据，验证失败仍拟 push，或涉及 force push、已发布历史重写、远端删除、仓库设置、分支保护或破坏性操作时，必须重新取得明确授权。
- Agent 不得自行 merge、release、删除远端数据、执行破坏性操作或扩大范围。`main` 只接受人类决定的 Squash Merge。
- 允许 push 或创建 PR 不代表允许 merge 或 release。
