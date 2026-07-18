# Local Agent orchestration

这里保存可审计、可提交的任务契约与简短结果。原始模型事件、锁和进程状态保存在 `runtime/`，不会进入版本历史。

## 任务命名

面向人的界面和交接记录统一按“中文任务名称 → 稳定任务编号 → 技术追溯 ID”的顺序展示：

- 中文任务名称来自不可变合同的 `title`；
- `GP05-IMPL-02` 或 `TASK-0002` 是稳定任务编号；
- `qyypnkok` 一类 Jujutsu change ID 只用于底层追溯，不作为任务名；
- 新 change 描述使用 `type(TASK-ID): 可读结果`，bookmark 使用语义化短名。

## 三层状态

- `tasks/`：用户批准后不可变的任务合同；
- `runtime/`：本地心跳、租约、PID、会话和成本，不进入版本历史；
- `results/`：可提交的执行摘要、验证与人工决定。

核心状态机为 `READY → RUNNING → VERIFYING → AWAITING_USER`。异常状态包括 `INTERRUPTED`、`STALE_BASE`、`ENVIRONMENT_DRIFT`、`BUDGET_REVIEW`、`BUDGET_EXHAUSTED`、`PERMISSION_BLOCKED` 和 `VERIFICATION_FAILED`。

只有用户可以把 `AWAITING_USER` 任务进一步标记为接受、退回、接管或取消。`ACCEPT`、`INTEGRATE` 与 `PUSH` 是三个独立权限动作。

## 命令

```powershell
pnpm agent:approve-contract TASK-0002 --confirm=TASK-0002
pnpm agent:prepare TASK-0002
pnpm agent:status TASK-0002
pnpm agent:dispatch TASK-0002 --confirm=TASK-0002
pnpm agent:start TASK-0002
pnpm agent:status TASK-0002
pnpm agent:audit TASK-0002
pnpm agent:dashboard
```

`prepare`只创建`READY`运行态，不会调用模型。只有Oasis执行`dispatch`后，`start`才会启动OpenCode CLI；批准合同、放行执行和完成后验收是三个独立人工门禁。

## 模型选择策略

- 新草案可设置`complexity`为`LOW`、`MEDIUM`或`HIGH`；未设置时按`LOW`处理。
- `LOW`与`MEDIUM`默认选择`deepseek/deepseek-v4-flash`，优先控制Token与费用。
- 只有`HIGH`复杂度的可委派任务选择`deepseek/deepseek-v4-pro`。
- 模型由Codex合同批准器写入并封存；OpenCode不能自行修改复杂度、模型或策略版本。
- 策略升级前已经封存的旧合同保持可审计兼容，不会被原地改写。

人工决定必须重复输入任务ID：

```powershell
pnpm agent:accept TASK-0002 --confirm=TASK-0002
pnpm agent:return TASK-0002 --confirm=TASK-0002
pnpm agent:takeover TASK-0002 --confirm=TASK-0002
pnpm agent:cancel TASK-0002 --confirm=TASK-0002
```

接管任务完成后，`accept`会把`USER_OWNED`推进到`READY_TO_INTEGRATE`。Codex完成实际Jujutsu合入后，再用`agent:integrated ... --change=<id> --commit=<id>`记录证据；实际推送完成后才可单独使用`agent:pushed ... --remote=<ref>`。这些记录命令不会替代真实的版本管理动作。

OpenCode原始JSON事件位于`orchestration/runtime/logs/<task-id>.jsonl`，状态、lease和审计事件也只保存在`runtime/`。GitHub只保留任务合同、执行摘要、验收记录和最终change/commit关联。

`RETURNED`是当前合同的终态，不得原地修改合同后重跑。Codex需根据退回意见生成新合同版本并再次请Oasis批准；当前应使用新`TASK-ID`保持runtime隔离。
