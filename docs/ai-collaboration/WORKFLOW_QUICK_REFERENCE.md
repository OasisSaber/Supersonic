# 开发协作工作流速查表

> 用途：开始、批准、执行、验证、交接和推送前的快速核对。项目规则以根目录 `AGENTS.md`、任务合同和 `CURRENT_HANDOFF.md` 为准；本页只做易读摘要。

## 1. 先看什么

1. 读 `docs/ai-collaboration/CURRENT_HANDOFF.md`：当前任务、所有者、已验证内容和下一步。
2. 如为编排任务，读 `orchestration/tasks/<TASK-ID>.json` 与本地 runtime 状态。
3. 运行 `jj status`、`jj log -n 5`，确认 change、父提交和未完成修改。
4. 只读合同列出的输入文件和必要规范；发现 workspace lease 属于他人，立即停下。
5. 实现前按 [`OPENCODE_FIRST_WORKFLOW.md`](./OPENCODE_FIRST_WORKFLOW.md) 路由：满足 L0/L1、有界路径和确定性验证的叶子任务，默认先起草 OpenCode 合同。

## 2. 一项新任务如何开始

| 步骤 | 要做什么 | 负责人 |
|---|---|---|
| 定义 | 写清目标、范围、验收、验证命令和禁止范围 | Codex + Oasis |
| 批准 | Codex 展示外部数据、范围、模型、预算、验证和排除项；Oasis 对不可变合同回复 `APPROVE <TASK-ID>` | Oasis |
| 建立 change | 用 `jj new` 创建一个独立、可描述的 change | Codex |
| 执行 | 尽早 `jj describe -m "type(TASK-ID): 可读结果"` | 执行者 |
| 交接 | 写回执行回执与 `CURRENT_HANDOFF.md` | Codex |

合同的人类显示顺序是：**中文任务名称 → 稳定任务编号 → 技术追溯 ID**。例如：

> 建立 GP05 FastAPI 权威座舱状态与 WebSocket 快照通道 → `GP05-IMPL-02` → change `qyypnkok`

`qyypnkok` 一类 Jujutsu change ID 不可重命名，只用于追溯；用 `gp05-impl-02-authoritative-state` 一类语义化 bookmark 作为可读版本名称。

## 3. 哪些事必须找 Oasis 批准

必须明确批准：

- 新任务的不可变合同；
- 合同范围、模型、预算、外部数据类别或权限的实质变化；
- `push`、PR、发布；
- 删除远程 bookmark、覆盖他人改动、改变课题范围或验收边界。

不需要再拆分确认：已批准合同内的派发、Codex 复核、合同内修正、验证和本地集成。

OpenCode 合同的批准只有在摘要已经逐项列出将发送给外部 DeepSeek/OpenCode 的私有仓库路径与数据类别时才有效。泛化的“批准了，下发”不能推断为外部数据共享许可；执行时必须记录 `EXTERNAL_DATA_SHARING` grant。平台或操作系统仍可执行自身的安全确认。

P0 外部发布门禁：Codex 必须先展示远端/可见性、bookmark 与全部未推祖先、文件和敏感数据类别、验证与排除项。Oasis 以 `APPROVE PUSH <bookmark>` 批准一次 push；以 `APPROVE PR <head> -> <base>` 单独批准一次 PR。push 失败或范围变化后必须重新摘要和批准，不能自动重试。

## 4. Codex 与 OpenCode 的边界

| 事项 | Codex | OpenCode |
|---|---|---|
| 架构、公共协议、设计系统、依赖、安全、发布 | 负责 | 不得修改 |
| 任务合同 | 起草、复核、接管 | 只能执行已批准的不可变合同 |
| 执行位置 | 主工作区 | 独立 Jujutsu workspace/change + lease |
| 完成后 | 复核并本地集成 | 停在 `AWAITING_CODEX_REVIEW` |

OpenCode 只可执行标为 `DELEGATABLE` 且处于 `READY` 的任务；不能自行领任务、扩范围、换模型、加预算、创建子 Agent 或自动重试。

默认由 OpenCode 承担约 65% 的适合委派叶子任务。草案对应实现已完成、base 漂移或验收失效时，草案立即过期，不得派发。当前详细路由、预算档位和失败处理见 [`OPENCODE_FIRST_WORKFLOW.md`](./OPENCODE_FIRST_WORKFLOW.md)。

## 5. 完成不等于“写完代码”

完成需要同时具备：

1. 合同范围内的可运行实现；
2. 与改动层级相符的验证；
3. 可追溯的结果回执与交接记录。

| 改动类型 | 最低验证 |
|---|---|
| 仅文档 | 链接、路径、事实、术语一致性 |
| 前端 | 对应测试 + `pnpm --filter @cockpit/frontend build` |
| 后端 | `pnpm lint:backend` + `pnpm test:backend` |
| 跨层/依赖/交付前 | `pnpm check`；需要运行态证据时再做 `pnpm smoke` |

未运行的检查必须如实写为“未验证”，不能表述成通过。

## 6. 交接与推送

交接时更新 `CURRENT_HANDOFF.md`，至少记录：任务名称/编号、change 与父提交、修改文件、已验证与未验证项、边界、下一步、是否已推送。

推送前确认：

- Codex 已展示本次完整 push 摘要，你已回复精确的 `APPROVE PUSH <bookmark>`；
- 推送的是语义化 bookmark；
- 未创建 PR、未发布，除非你也明确授权；
- 未删除或覆盖任何现有远程引用。

## 7. 当前项目位置

GP21 四屏 React 第二阶段与 dashboard 稳定编号去重已经完成。当前下一项产品工作是 1920、1440、1280 三档运行态视觉回归；其中可确定复现的局部裁切、重叠和样式修复可以拆为新的 OpenCode 叶子合同，视觉裁决、跨屏一致性和最终复核仍由 Codex 负责。
