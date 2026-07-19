# AI 协作中心

该目录用于在开发者与 AI 之间共享事实与交接状态，避免依赖对话的短期记忆。

## 文件职责

| 文件 | 用途 | 更新时机 |
| --- | --- | --- |
| `CURRENT_HANDOFF.md` | 当前工作状态与交接 | 每次切换任务或结束会话 |
| `DEVELOPMENT_STANDARDS.md` | 代码、架构、设计和验证规范 | 出现重复错误或新约束时 |
| `PROJECT_DECISION_BASELINE.md` | 当前课题范围、架构、性能与验收的唯一决策基线 | 批准实质变化时 |
| `GP05_IMPLEMENTATION_TASKS.md` | GP05 工程任务依赖与验收拆分 | 基线或实施依赖变化时 |
| `DESIGN_REVIEW_CHECKLIST.md` | Make/Figma 设计审核清单 | 设计审核时 |
| `MAKE_VERSION_DELIVERY_TEMPLATE.md` | Make 版本交付模板 | Make 交付版本时 |
| `../adr/` | 长期架构决策 | 关键决策确认后 |
| `../../contracts/gp05/` | 跨端协议合同 | 协议变化时 |

## 协作原则

- 交接必须写入仓库，不以“上一个聊天里说过”为依据。
- 每个结论标注为已验证、推断或待确认。
