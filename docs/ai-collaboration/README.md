# AI 协作中心

该目录用于让Codex、OpenCode和人类开发者共享事实与交接状态，避免依赖某个对话窗口的短期记忆。

## 文件职责

| 文件 | 用途 | 更新时机 |
| --- | --- | --- |
| `CURRENT_HANDOFF.md` | Codex主工作区与控制面交接 | 每次切换Leader或结束会话 |
| `HANDOFF_PROTOCOL.md` | 交接和所有权规则 | 流程发生长期变化时 |
| `OPENCODE_FIRST_WORKFLOW.md` | OpenCode 默认路由、外部数据批准、预算与失败边界 | 委派策略或安全边界变化时 |
| `DEVELOPMENT_STANDARDS.md` | 代码、架构、设计和验证规范 | 出现重复错误或新约束时 |
| `PROJECT_DECISION_BASELINE.md` | 当前课题范围、架构、性能与验收的唯一决策基线 | Oasis 批准实质变化时 |
| `GP05_IMPLEMENTATION_TASKS.md` | GP05 工程任务依赖、权限等级与验收拆分 | 基线或实施依赖变化时 |
| `prompts/OPENCODE_START.md` | 自动执行与人工接管边界 | 工作流发生变化时 |
| `../../orchestration/tasks/` | 用户批准后不可变的任务合同 | Codex规划、用户批准时 |
| `../../orchestration/runtime/` | 本地lease、心跳、日志、状态与成本 | Supervisor运行时，禁止提交 |
| `../../orchestration/results/` | 可提交的执行与验收回执 | 任务结束或人工决定后 |
| `../adr/` | 不应只存在聊天中的长期架构决策 | 关键决策确认后 |

## OpenCode + DeepSeek V4 准备

项目配置位于根目录 `opencode.json`，默认使用：

- 主模型：`deepseek/deepseek-v4-pro`；
- 小任务模型：`deepseek/deepseek-v4-flash`；
- 会话分享：关闭；
- OpenCode内部快照：关闭，以Jujutsu作为唯一版本历史；
- 外部目录访问：禁止；
- 自动任务的Shell、Web、外部目录和sub-agent：默认禁止；
- 推送、集成和用户接管：分别确认。

首次使用：

1. 安装或升级到 OpenCode `1.14.24` 或更高版本；
2. 可在 OpenCode Desktop 中执行 `/connect`，选择 `deepseek`，并在 OpenCode 自己的凭据界面输入 DeepSeek API Key；Desktop 在本工作流中只用于认证配置与人工查看；
3. 自动任务始终由独立 Supervisor 调用 OpenCode CLI，不依赖 OpenCode Desktop 窗口、Codex Desktop 会话或人工粘贴提示词；
4. 输入 `/models`，确认主模型为DeepSeek V4 Pro；
5. 运行零Token编排测试与环境锁预检；
6. 由Codex创建合同、Oasis批准后，通过`pnpm agent:start <TASK-ID>`派发。

API Key不得写入 `.env`、`opencode.json`、提示词、日志或任何版本文件。

## 跨项目 OpenCode 子代理插件

本仓库中的 `tools/opencode-subagent/` 是用户级个人插件 `opencode-subagent` 的可版本化源码。它把当前项目已经验证的不可变合同、独立 Supervisor、Jujutsu sparse workspace、预算、权限审计、独立验证和人工门禁抽成了项目无关的 `delegate-to-opencode` skill 与 CLI。

- 用户级插件源：`<user-plugin-root>/opencode-subagent`；
- 个人 marketplace：`<agent-home>/plugins/marketplace.json`；
- 当前安装：`opencode-subagent@personal`；
- 新项目初始化：在新 Codex 线程中要求使用 `$delegate-to-opencode`，skill 会在目标仓库创建独立的 `.opencode-subagent/` 控制面；
- 新任务默认使用 `.opencode-subagent/` schema v2 单次批准控制面；原有 `orchestration/` 与 `pnpm agent:*` 仅保留旧任务兼容，不混用合同或 runtime，也不消费旧任务的执行授权。
- 项目已采用 [`OPENCODE_FIRST_WORKFLOW.md`](./OPENCODE_FIRST_WORKFLOW.md)：适合委派的 L0/L1 叶子任务默认先起草合同，外部数据路径必须在精确批准前逐项披露。

更新插件时，先修改并验证 `tools/opencode-subagent/`，运行 `tools/opencode-subagent/scripts/self-test.mjs`，再同步用户级插件、运行 plugin-creator 的 cachebuster helper，并从 `personal` marketplace 重新安装。不要手改 Codex 插件缓存或 marketplace 安装状态。

## 协作原则

- 一个任务一个独立Jujutsu workspace/change和lease；
- 默认串行，只有Codex明确授权时最多双并发；
- 可以由另一个Agent只读审查，但不得同时编辑相同文件；
- 交接必须写入仓库，不以“上一个聊天里说过”为依据；
- 每个结论标注为已验证、推断或待确认；
- 工具能力不同不改变完成标准。
