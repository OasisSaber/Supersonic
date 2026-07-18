# Agent 交接协议

## 目标

任何Agent在没有前一段聊天记录时，都应能在5分钟内回答：当前任务是什么、谁在负责、改了什么、验证到哪里、下一步是什么。

## 所有权与状态来源

- `CURRENT_HANDOFF.md` 记录Codex主工作区和控制面工作；
- 新版 OpenCode 子代理任务的不可变定义以 `.opencode-subagent/tasks/<TASK-ID>.json` 为准，运行状态以 `.opencode-subagent/runtime/tasks/<TASK-ID>.json` 为准；
- 旧版任务仍分别以 `orchestration/tasks/<TASK-ID>.json` 和 `orchestration/runtime/tasks/<TASK-ID>.json` 为准；两个控制面不得混用合同或 runtime；
- 一个OpenCode任务必须拥有独立Jujutsu workspace/change；
- workspace lease是写权限的唯一运行时凭据，`TAKEOVER`后OpenCode不得重新获取；
- 只读审查可以并行，但必须在handoff中记录，且不得编辑；
- 同一文件出现并行修改时立即停止，由用户决定保留或合并方案。

## 接手流程

1. 读取根部与相关局部 `AGENTS.md`；
2. 读取任务合同、runtime状态和`CURRENT_HANDOFF.md`；
3. 核对合同哈希、环境锁、base commit和依赖；
4. Supervisor创建独立workspace并获取lease；
5. 运行 `jj status`、`jj log -n 5` 和必要的 `jj diff`；对自动 OpenCode Executor，这些检查由 Supervisor 在启动 Executor 前代为完成，Executor 本身不获得 Shell 或 Jujutsu 权限；
6. 用`jj describe`确保change描述准确；
7. 再开始编辑。

## 交出流程

更新 `CURRENT_HANDOFF.md` 的所有字段，尤其是：

- 中文任务名称、稳定任务编号、语义化版本名称，以及收纳在技术追溯字段中的 change ID、父提交和 change 描述；
- 修改过的文件及每个文件的作用；
- 已确认决策与仍为假设的内容；
- 实际运行的命令、通过/失败结果；
- 未完成工作和下一条可执行命令；
- 是否允许下一个Agent继续编辑；
- 是否已推送远程。

OpenCode完成后释放运行lease但保留workspace，新任务状态进入`AWAITING_CODEX_REVIEW`。Oasis对不可变合同的一次`APPROVE`已授权Codex复核、合同内接管和验证后的本地集成，不再要求额外`ACCEPT`或`INTEGRATE`。推送、PR、发布以及合同范围/模型/预算/外部数据类别变化仍需新的明确授权。旧版手动门控任务可继续进入`AWAITING_USER`。如果工作暂停，必须保留现场，不得伪装成`READY`或干净状态。

新版合同批准前必须展示并逐项列出将发送给外部 DeepSeek/OpenCode 的输入路径和数据类别。用户回复精确的 `APPROVE <TASK-ID>` 后，CLI 才可使用 `--ack-external-data-sharing` 记录该授权并执行一次派发。未展示数据清单、泛化批准或合同已过期时均不得外发；平台和操作系统自己的安全确认不由合同绕过。

push 与 PR 是独立的 P0 外部门禁。Codex 必须分别展示完整摘要并取得 `APPROVE PUSH <bookmark>` 与 `APPROVE PR <head> -> <base>`；任务批准、本地集成、历史授权或其中一项批准都不能代替另一项。失败或平台阻止后不得自动重试，必须记录真实状态、更新摘要并重新批准。只有远端返回成功证据后，handoff 才能写“已推送”或“已创建 PR”。

Oasis选择`RETURN`后，当前合同和change保持`RETURNED`终态，不在原合同上改写或继续执行。Codex应根据退回原因起草新的不可变合同版本并重新请Oasis批准；在版本化runtime尚未实现前，新版本使用新的`TASK-ID`，避免与已终止的runtime状态冲突。

## 失败和冲突

- handoff与`jj status`不一致：以Jujutsu和文件系统为准，先修正handoff；
- 测试失败：记录完整命令和最小错误摘要；
- 上下文不足：读取ADR和相关方向文档，不扫描所有历史材料；
- 无法确定某项改动归属：停止修改并询问用户；
- Agent输出声称完成但无文件或测试证据：视为未完成。
- 心跳超时或PID消失：进入`INTERRUPTED`，必须由用户选择恢复、重试、接管或取消；
- base或环境变化：分别进入`STALE_BASE`或`ENVIRONMENT_DRIFT`，不得自动rebase或升级；
- Token或成本达到合同上限：进入`BUDGET_EXHAUSTED`，不得自动追加预算。
- 草案目标已由其他 change 完成：标记为过期追溯资产，不批准、不派发；使用新的实际目标和 TASK-ID 重新起草。
