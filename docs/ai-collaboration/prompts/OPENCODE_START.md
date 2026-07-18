# OpenCode 执行与接管提示词

## 自动任务

自动任务不需要人工复制长提示词。Codex创建不可变合同、Oasis批准后，由Supervisor：

1. 检查环境锁、base commit、预算和依赖；
2. 创建独立Jujutsu sparse workspace/change；
3. 注入只读合同副本与任务级最小权限配置；
4. 调用OpenCode CLI执行；
5. 独立验证并停在`AWAITING_CODEX_REVIEW`，由Codex在原始单次批准范围内复核、接管或本地集成，不再向用户追加验收门。

```powershell
pnpm agent:status TASK-0002
pnpm agent:start TASK-0002
```

OpenCode Desktop只用于配置提供商认证、检查模型和经Oasis授权后的人工接管。自动派发由独立Supervisor调用OpenCode CLI；禁止在Desktop中直接打开Codex主工作区并要求其从backlog自行选择任务。

## Supervisor 注入的执行提示词

```text
执行 .agent-contract/contract.json 中已批准且不可变的任务。
先读取检出的 AGENTS.md。你是受限Executor，只能修改scope.allowedPaths。
禁止运行Shell、Git、Jujutsu、Web工具和sub-agent；不得改变合同、架构、模型、预算或依赖。
完成实现并写入合同要求的结果回执后停止。遇到歧义或越权需求时说明阻碍，不要猜测。
```

## 人工接管

必须先由Oasis执行：

```powershell
pnpm agent:takeover TASK-0002 --confirm=TASK-0002
```

确认runtime状态为`USER_OWNED`后，才可在该任务的独立workspace继续开发：

```text
Oasis已经通过控制CLI接管当前任务。读取.agent-contract/contract.json、相关AGENTS.md、
runtime状态和现有diff。保持同一Jujutsu change，不重置、不重新派发、不扩大范围。
先汇报未完成内容和验证状态，再等待Oasis指示。
```

人工接管不等于验收、集成或推送授权。
