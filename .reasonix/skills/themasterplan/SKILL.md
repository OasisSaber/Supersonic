---
name: themasterplan
description: >-
  TheMasterplan 单一交付责任人的 AI 辅助代码交付治理协议（GitHub Flow +
  Jujutsu 适配，含 Git/jj Profile 与 Generic/Trellis Adapter）。当用户调用
  /TheMasterplan，或项目包含根部 AGENTS.md、core/、profiles/、
  .aw/state.json 等采用特征时使用。
---

# TheMasterplan 工作流

`/TheMasterplan` 是唯一规范的用户可见 Skill 入口。

本 Skill 是 TheMasterplan 的客户端加载入口，不复制完整规则正文。

## 检测顺序

```text
根部 AGENTS.md
core/policy.md + core/workflow.md
profiles/<profile>.md
adapters/<adapter>.md（可选）
.aw/state.json（采用状态，可选）
```

采用项目自身文件的规则优先于本 Skill 的一般说明。

## 权威来源

1. `AGENTS.md`：入口与加载顺序；
2. `core/workflow.md`：任务、验证与交接；
3. `core/policy.md`：权限、审批与发布；
4. `profiles/`：Git / jj 命令；
5. `adapters/`：Harness 映射。

## 内部兼容标识

品牌与 Skill 命令迁移后，以下内部实现暂不同时迁移：

- `.aw/`
- `.aw/bin/aw.py`
- `<!-- AW:BEGIN MANAGED -->`
- `<!-- AW:END MANAGED -->`
- Python 内部 `AwError` 等符号

这些是存储和代码兼容接口，不是用户调用命令。

## 缺失处理

缺失根部 `AGENTS.md`、`core/` 或所选 Profile 时，报告
“TheMasterplan 未完整安装”，不得静默推断完整规则。
