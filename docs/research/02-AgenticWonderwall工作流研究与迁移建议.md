# AgenticWonderwall 工作流研究与迁移建议

- 研究日期：2026-08-01
- 研究对象：[OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)
- 固定上游基线：[`794b083e816e84f271e991aed84a5a5f4e9c74fc`](https://github.com/OasisSaber/AgenticWonderwall/commit/794b083e816e84f271e991aed84a5a5f4e9c74fc)（2026-07-30，研究时 `main` 的 HEAD）
- 方法：只使用上游仓库源码、模板、脚本、CI 与 Git 历史，以及本仓库当前文件和 Git 历史；未使用二手教程。
- 目的：判断 AgenticWonderwall 当前工作流中哪些部分已经采用、哪些加固值得迁移、哪些内容必须保留为项目定制或暂不迁移。

## 结论摘要

本项目不是从零部署 AgenticWonderwall。现有采用记录表明，本项目已在 2026-07-23 采用上游 `v1.0.0` 对应的 commit `689d4edb8aacc1fc7a277da89efed05199b75edb`，并在根部规则、项目验证、PR 模板和远端授权边界上做了 HMI 项目化定制。[本项目采用记录](../development.md#agenticwonderwall-采用记录)和[第三方声明](../../THIRD_PARTY_NOTICES.md#agenticwonderwall-workflow-materials)是当前证据。

研究时的上游 `main` 相比该采用基线又增加了 13 个加固提交，新增或强化了复杂任务 Issue Form、完整 Jujutsu 生命周期、依赖任务 Draft PR、统一校验入口、PowerShell 委托入口、CI 最小权限与确定性状态名、采用边界和平台兼容性声明。[固定比较](https://github.com/OasisSaber/AgenticWonderwall/compare/689d4edb8aacc1fc7a277da89efed05199b75edb...794b083e816e84f271e991aed84a5a5f4e9c74fc)

Issue #28 的当前 change 已按本研究结论实现“选择性同步当前 `main` 的加固项”，没有整套覆盖现有工作流；在关联 PR 由人类 Squash Merge 前，不得表述为 `main` 已部署：

1. 保留本项目根部 [`AGENTS.md`](../../AGENTS.md) 作为唯一通用权威，并保留其更严格的远端授权、HMI 范围和验证要求。
2. 优先迁移复杂任务 Issue Form、Jujutsu 冲突/发布历史处理、PR 正文校验修复、统一入口对校验器测试的覆盖，以及 CI 安全加固。
3. PowerShell 委托入口和依赖任务 Draft PR 工作流按真实需要采用；在真实 Windows/Jujutsu 演练前不得声明为 `VERIFIED`。
4. 不复制上游通用 README、通用技术验证脚本或仓库设置结论来覆盖项目事实；上游当前 `main` 也尚未形成 `v1.0.0` 之后的新 tag，部署时必须记录完整 SHA `794b…`，不能把这些增量笼统称为 `v1.0.0`。

本次差异的状态分类如下：

| 状态 | 内容 |
| --- | --- |
| **已部署** | `v1.0.0`/`689d4ed…` 的单一权威入口、复杂 Issue/低风险授权双路径、一任务一 change/bookmark、项目化验证、PR 自审、Squash Merge 人工保留，以及本项目更严格的远端授权边界 |
| **Issue #28 当前实现范围** | 当前 `main`/`794b083…` 中的复杂任务 Issue Form、完整 Jujutsu 冲突与发布历史生命周期、PR 注释解析修复、权威入口覆盖全部校验器测试，以及 CI 凭据、Action SHA、并发和状态名加固；待关联 PR 验证与人工合并 |
| **不应直接复制** | 上游通用 README/AGENTS/技术验证脚本、未经本机演练的 PowerShell 7 支持声明、无显式 Issue 依赖链时的 Draft PR 队列，以及任何自动 merge/release/远端删除/仓库设置操作 |

## 一、上游版本与证据边界

上游仓库将自己定义为面向个人开发者的“单 Agent GitHub Flow + Jujutsu 轻量工作流模板”，明确排除 Agent 服务、多 Agent 编排、自动发布机器人和项目管理系统。[README](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/README.md)

当前发布面与开发面不同：

| 版本面 | 固定证据 | 含义 |
| --- | --- | --- |
| 最新 Release/tag | [`v1.0.0` → `689d4ed…`](https://github.com/OasisSaber/AgenticWonderwall/releases/tag/v1.0.0) | 本项目当前已记录采用的发布基线 |
| 研究时默认分支 | [`main` → `794b083…`](https://github.com/OasisSaber/AgenticWonderwall/tree/794b083e816e84f271e991aed84a5a5f4e9c74fc) | 比 `v1.0.0` 多 13 个尚未以新 tag 发布的加固提交 |
| 增量范围 | [`689d4ed…794b083` compare](https://github.com/OasisSaber/AgenticWonderwall/compare/689d4edb8aacc1fc7a277da89efed05199b75edb...794b083e816e84f271e991aed84a5a5f4e9c74fc) | 用于选择性回移，不代表新的正式 Release |

上游采用指南要求记录实际使用的 Release tag 或完整 commit SHA，并明确“只复制 `AGENTS.md`”时必须替换项目事实、验证命令和不存在的链接。[采用指南](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/docs/adoption-guide.md)

## 二、AgenticWonderwall 当前工作流

### 1. 任务来源和权威顺序

根部 `AGENTS.md` 是唯一具有约束力的通用规则入口；README、CONTRIBUTING 和采用指南只能辅助解释。权威顺序先保护系统安全、项目安全、受保护分支和破坏性操作边界，再到通用工作流、当前 Issue/明确人类授权、项目资料和辅助文档。Issue 或会话授权只能界定目标、范围和验收，不能覆盖安全、发布、部署和破坏性操作限制。[上游 AGENTS.md](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/AGENTS.md)

任务有两条默认路径：复杂任务必须用 Issue 记录目标、范围、验收条件和排除项；小型低风险任务可以使用当前会话中的明确授权，但不得伪造 Issue 编号，扩大范围时必须转为 Issue。上游还提供一个可选的依赖任务队列，但只允许用于 Issue 已明确写出 `A → B → C` 依赖链的情况。[复杂任务 Issue Form](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/.github/ISSUE_TEMPLATE/complex-task.yml)、[依赖任务工作流](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/docs/dependent-task-workflow.md)

### 2. Jujutsu change 生命周期

上游坚持“一个任务 = 一个 jj change = 一个短生命周期 bookmark = 一个 PR”，不维护长期开发分支。开始前必须 fetch、查看 `jj status`、远端 bookmark 和最近日志；如果 `main`、`main@origin` 或任务 bookmark 冲突，则停止而不是猜测目标或强推。[CONTRIBUTING](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/CONTRIBUTING.md)

其关键生命周期边界是：

- 新任务从 `main` 创建单一 change，再创建 `codex/issue-<number>-<name>` 或授权任务 bookmark；
- 验证前确认 bookmark 仍指向当前 change，因为 Jujutsu 没有“当前 bookmark”，创建子 change 后 bookmark 不会自动前进；
- 首次 push 后 change 属于已发布历史，restack 或内容更新都可能重写历史，必须先取得明确授权；
- push 拒绝、bookmark 冲突或 rebase 文件冲突时不得强推或继续发布；
- 人类 Squash Merge 后默认只用 `jj bookmark forget` 清理本地 bookmark；删除仍存在的远端 bookmark 是独立人工决定，并要求先 dry-run。

这些规则均来自上游完整命令生命周期和停止条件。[CONTRIBUTING](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/CONTRIBUTING.md)

### 3. 验证、自审和 CI

上游只有一个权威 Bash 入口 `bash scripts/check.sh`。该入口检查所有受跟踪 Python 校验脚本的语法，运行 `scripts/test_*.py`，再委托 `scripts/validate.sh` 完成 Markdown 链接、Shell 可执行位、YAML 和 Shell 语法检查。[check.sh](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/check.sh)、[validate.sh](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/validate.sh)

PowerShell 入口不维护第二套规则，只定位兼容 Bash 并委托 `check.sh`。[check.ps1](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/check.ps1) 上游明确把 Ubuntu Actions 上的 Bash 和 PowerShell 委托路径标为 `VERIFIED`，把真实 Windows 与 macOS 标为 `PARTIAL`，并要求采用仓库完成真实平台烟雾测试后才可升级状态。[验证说明](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/README.md)

创建或更新 PR 前，Agent 必须对照任务来源、阅读完整 diff、记录真实验证、确认未扩大范围、清除调试/临时/缓存/误删/失效引用，并说明已知限制和未覆盖内容。[上游 AGENTS.md](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/AGENTS.md)、[PR 模板](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/.github/pull_request_template.md)

上游 CI 使用只读 `contents` 权限、`persist-credentials: false`、固定完整 commit SHA 的 Actions、并发取消和显式 job 名 `check`；PR 正文校验从事件载荷读取，不额外授予写权限。[check.yml](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/.github/workflows/check.yml)

### 4. PR 与人工保留

Agent 可以在已记录范围内实现、验证、push 和维护 PR，但不得自行 merge、release、删除远端数据、执行破坏性操作或扩大范围。允许 push/建 PR 不等于允许 merge/release；`main` 只接受人类决定的 Squash Merge。[上游 AGENTS.md](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/AGENTS.md)

仓库文件不能自行建立 GitHub 服务器端保护。上游要求人类配置：`main` 必须经 PR、要求 `check` 通过、禁止 force push/删除、尽可能禁止绕过、只启用 Squash Merge、禁用 auto-merge，且 Agent 凭据不得拥有 admin/merge/release 权限。[仓库设置说明](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/docs/repository-settings.md)

## 三、与本项目当前工作流的差异

### 已经对齐且应保留

| 主题 | 本项目当前证据 | 判断 |
| --- | --- | --- |
| 单一权威入口 | [`AGENTS.md`](../../AGENTS.md) 明确自身是唯一通用规则来源 | 已对齐，不应由上游文件覆盖 |
| 两条任务路径 | [`AGENTS.md`](../../AGENTS.md#两条任务路径) 已区分复杂 Issue 与小型会话授权 | 已对齐 |
| 一个任务一个 change/bookmark | [`AGENTS.md`](../../AGENTS.md#jj-change-与工作区)、[`CONTRIBUTING.md`](../../CONTRIBUTING.md) | 已对齐 |
| 项目化验证 | [`scripts/validate.sh`](../../scripts/validate.sh) 继续运行 Markdown/YAML/Shell 检查和不降级的 `pnpm check` | 比直接复制上游通用校验更适合本项目 |
| PR 自审与视觉证据 | [本项目 PR 模板](../../.github/PULL_REQUEST_TEMPLATE.md) 增加 HMI/视觉证据、范围、风险和未验证项 | 项目化增强，应保留 |
| 人工保留与远端授权 | [`AGENTS.md`](../../AGENTS.md#外部操作与人工保留) 要求明确远端、bookmark、base、范围和验证，边界变化时重新授权 | 比上游通用表述更具体，应保留 |
| 许可与来源 | [`docs/development.md`](../development.md#agenticwonderwall-采用记录)、[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) | 已有发布基线和 MIT 派生声明 |

### 当前缺口或弱点

1. **缺少复杂任务 Issue Form。** 本项目 `.github/` 当前没有 Issue Form，复杂任务虽被 [`AGENTS.md`](../../AGENTS.md#复杂任务) 要求记录目标、范围、验收和排除项，却没有机械化入口。上游表单还要求依赖顺序和“merge/release/远端删除等仍需人工决定”的确认，值得按本项目术语迁移。[上游表单](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/.github/ISSUE_TEMPLATE/complex-task.yml)

2. **Jujutsu 日常生命周期文档过薄。** 本项目规则已有 `jj status`、`jj log`、`jj git fetch` 和“不得擅自重写已发布历史”，但没有记录 bookmark 跟踪、fetch 后冲突、push 拒绝、已发布 restack、Squash Merge 后本地清理和远端删除 dry-run 的具体路径。[本项目 AGENTS.md](../../AGENTS.md#jj-change-与工作区)、[本项目 CONTRIBUTING.md](../../CONTRIBUTING.md) 与[上游 CONTRIBUTING](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/CONTRIBUTING.md)存在明显细化差异。

3. **Jujutsu 版本匹配，但端到端工作流演练仍需补证。** 本机实际版本为 Jujutsu `0.43.0`、Git `2.54`，仓库存在 `.jj/`；这与上游核对过的 Jujutsu 基线一致。本次环境中 `jj` 需要通过已定位的实际可执行文件调用，普通 PowerShell PATH 解析并不稳定。因此可以把“命令版本基线匹配”记为已验证，但仍需用本项目真实 Issue/change/bookmark/PR/Squash Merge 完成端到端采用 smoke，才能证明整个生命周期已经部署。

4. **本地权威验证没有覆盖 PR 正文校验器测试。** [`scripts/validate.sh`](../../scripts/validate.sh) 运行 Markdown 校验器测试，但没有运行 [`scripts/test_validate_pr_body.py`](../../scripts/test_validate_pr_body.py)；后者只在 [GitHub Actions](../../.github/workflows/check.yml) 中单独执行。因此“push 前权威入口通过”不能单独证明 PR 正文门禁仍工作。上游 `check.sh` 通过 `unittest discover` 覆盖全部 `test_*.py`，这一思想应合并进现有 `validate.sh`，而不是替换项目验证链。

5. **PR 模板与本地校验器存在 HTML 注释语义风险。** [本项目 PR 模板](../../.github/PULL_REQUEST_TEMPLATE.md)把明确授权路径保留在 HTML 注释中；[本地校验器](../../scripts/validate_pr_body.py)没有先去除 HTML 注释。本次按校验器同一正则对“只把 Issue 占位符填为 `Closes #123`”的模板做只读检查，得到 `issue_paths_seen=1`、`authorization_parents_seen=1`，即校验器会把注释内备用路径也视为存在，进而判定两条任务来源同时出现。上游当前校验器先用 `HTML_COMMENT` 删除注释，并新增了相关单元测试，可作为定向修复依据。[上游校验器](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/validate_pr_body.py)、[上游测试](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/test_validate_pr_body.py)

6. **CI 仍有可移植的加固增量。** [本项目 workflow](../../.github/workflows/check.yml)使用版本 tag 而不是完整 Action SHA，没有 `persist-credentials: false`、并发取消和显式 job `name: check`。上游当前版本已具备这些设置。迁移时需为本项目额外使用的 Node、pnpm、uv Action 分别从其第一方发布记录核对固定 SHA，不能只复制上游 Python-only 的列表。

7. **Windows 上的 Bash 验证已通过，但上游 PowerShell 7 wrapper 当前不可用。** 本机为 Windows PowerShell `5.1`，没有 `pwsh` 7；PATH 中的 `bash` 优先解析到 WSL，而不是 Git for Windows。通过显式 Git Bash 调用时，`bash scripts/validate.sh` 已于 2026-08-01 完整通过。这足以证明本项目 Git Bash 权威验证入口当前可用，但不能证明上游 `#requires -Version 7.0` 的 `check.ps1` 可用，也不能证明从普通 PowerShell 直接键入 `bash` 会进入相同环境。[上游平台验证说明](https://github.com/OasisSaber/AgenticWonderwall/blob/794b083e816e84f271e991aed84a5a5f4e9c74fc/scripts/README.md) 因此当前应记录“Git Bash 验证入口已验证；PowerShell 7 委托入口不可用；完整 Windows 采用生命周期仍待 smoke”，而不是笼统标记整个 Windows 平台为 `VERIFIED`。

8. **服务器端保护无法从仓库文件证明。** 当前文件表达了 `main`、Squash Merge 和人工保留规则，但模板文件不会自动配置 GitHub ruleset/branch protection。迁移必须包含一次由人类执行并记录的服务器设置审计，不能用增加 Markdown 代替保护设置。

## 四、建议部署方案

### 第一批：应迁移的最小加固

1. 新增项目化复杂任务 Issue Form，保留“目标、范围、验收条件、排除项、依赖与顺序、权限边界确认”，并引用本项目 `AGENTS.md` 的权威顺序。
2. 定向修复 PR 正文校验器：忽略 HTML 注释、为 Issue 路径保留明确的 closing reference 语义，并补齐注释、占位符作用域和互斥任务来源测试；不要用上游较简化的模板覆盖本项目 HMI 证据/风险字段。
3. 让 `bash scripts/validate.sh` 同时运行 PR 正文与 Markdown 校验器测试，保持它仍是唯一权威入口；CI 继续只额外校验实时 PR body。
4. 扩充本项目 `CONTRIBUTING.md` 的 Jujutsu 生命周期：记录实际 `jj`/Git 版本、远端跟踪、conflicted bookmark 停止条件、已发布历史重写授权、push 拒绝处理、人工 Squash Merge 后本地清理和远端删除独立授权。
5. 加固 CI：固定第一方 Actions 的完整 SHA、关闭 checkout credential persistence、加入同 PR/分支并发取消、显式固定 job 名 `check`，同时保留 Node/pnpm/uv 与 `pnpm check` 项目验证。
6. 更新采用记录时同时保留两层 provenance：原始采用为 `v1.0.0`/`689d4ed…`，本次选择性同步来源为当前 `main`/`794b083…`；第三方声明只列实际派生的文件。

### 第二批：有条件迁移

- **PowerShell 7 委托入口：** 当前主机只有 Windows PowerShell 5.1 且没有 `pwsh` 7，不应直接复制上游 wrapper 并宣称可用。若以后安装 PowerShell 7，应显式定位 Git for Windows Bash（避免 PATH 优先进入 WSL），确认 pnpm、uv 与项目依赖后再运行完整验证并记录结果。
- **依赖任务 Draft PR：** 仅当 Issue 明确存在有序依赖链时采用。每项仍须独立 Issue/change/bookmark/PR；下游保持 Draft，以上游 bookmark 为 base；上游 Squash Merge 后必须取得已发布历史重写授权，再 restack、逐项完整验证和检查 diff。
- **审查意见三分法：** “合并前必须修复 / 建议本次修复 / 可以后续处理”有助于稳定 review 语义，但属于沟通规范，不是当前安全缺口。

### 不应直接迁移

- 不要整体覆盖根部 `AGENTS.md`、README 或项目开发文档；这会丢失四屏状态权威、素材隐私、Figma Token、Smoke 边界和任务级远端授权等项目约束。
- 不要用上游通用 `scripts/validate.sh` 替换当前项目校验；它不包含 React/FastAPI/pnpm/uv 的项目验证。
- 不要把上游的 `VERIFIED` 状态自动继承到真实 Windows 或本仓库当前 Jujutsu 版本。
- 没有显式 Issue 依赖链时，不要引入依赖任务队列；它会增加 base、restack 和已发布历史重写风险。
- 不要让 Agent 自动配置仓库保护、merge、release、删除远端 bookmark 或执行 force push。仓库设置变更与所有人工保留操作继续单独授权。
- 不要声称迁移了不存在的新 Release；当前 13 个加固提交只能用完整 SHA `794b…` 记录。

## 五、建议复杂任务 Issue 契约

以下内容可直接用于新的复杂任务 Issue；创建 Issue 本身以及后续 push/PR 仍须按根部
[`AGENTS.md`](../../AGENTS.md) 取得远端授权。

### 标题

`chore(workflow): selectively sync AgenticWonderwall hardening`

### 目标

在保留 HMI 项目权威规则、产品验证链和人工保留边界的前提下，选择性同步
AgenticWonderwall `794b083e816e84f271e991aed84a5a5f4e9c74fc` 中已证实适用于本仓库的
Issue、Jujutsu、PR 校验与 CI 加固，使复杂任务入口、push 前验证和远端 required check 使用同一组
可机械验证的约束。

### 范围

- 新增项目化 `.github/ISSUE_TEMPLATE/complex-task.yml`；
- 定向修复 `scripts/validate_pr_body.py` 与测试：忽略 HTML 注释、收紧 closing reference、限定占位符作用域；
- 让 `scripts/validate.sh` 本地覆盖 PR 正文和 Markdown 两组校验器测试，并继续执行完整 `pnpm check`；
- 加固 `.github/workflows/check.yml`：最小权限、checkout 不持久化凭据、Action 完整 SHA、并发取消和显式 `check` job 名；
- 在 `CONTRIBUTING.md` 补齐适用于 Jujutsu `0.43.0` 的 bookmark 跟踪、冲突停止、已发布历史重写授权、push 拒绝与合并后清理；
- 更新 `THIRD_PARTY_NOTICES.md` 和采用研究记录，逐文件记录 `689d4ed…` 原始采用与 `794b083…` 选择性同步来源。

建议允许文件：

- `.github/ISSUE_TEMPLATE/complex-task.yml`
- `.github/workflows/check.yml`
- `CONTRIBUTING.md`
- `scripts/validate.sh`
- `scripts/validate_pr_body.py`
- `scripts/test_validate_pr_body.py`
- `THIRD_PARTY_NOTICES.md`
- `docs/research/02-AgenticWonderwall工作流研究与迁移建议.md`

### 验收条件

- 复杂任务 Issue Form 强制目标、范围、验收、排除项、依赖顺序和人工权限确认；
- PR 模板中的备用授权 HTML 注释不会被当作第二条活动任务来源；
- Issue 路径只接受单一 closing reference，授权路径仍要求来源、目标、范围全部存在；
- `scripts/validate.sh` 在一次调用中运行两组验证器测试、Markdown/YAML/Shell 检查和 `pnpm check`；
- CI 使用从第一方来源核对的 Action commit SHA、`persist-credentials: false`、只读权限、并发取消和固定状态名 `check`；
- Jujutsu 文档覆盖 fetch、bookmark 跟踪、冲突、发布后 restack 授权、push 拒绝、Squash Merge 后本地清理和远端删除独立授权；
- 显式 Git Bash 入口在当前 Windows 主机完整通过；没有 PowerShell 7 时不添加或宣称已验证 PowerShell 7 wrapper；
- 完整 diff 不包含 `apps/`、`contracts/`、设计 Token、产品测试、依赖锁文件或生成物；
- `git diff --check`、校验器聚焦测试和 `bash scripts/validate.sh` 全部通过，并记录真实输出。

### 排除项

- 不修改前后端产品代码、协议、视觉设计、产品测试或依赖版本；
- 不整体覆盖根部 `AGENTS.md`、README 或当前项目验证链；
- 不在本 Issue 引入依赖任务 Draft PR 队列或 PowerShell 7 wrapper；
- 不修改 GitHub ruleset、分支保护、可见性、Secrets、权限或 merge 设置；
- 不执行 merge、release、远端 bookmark 删除、force push 或已发布历史重写；
- 不修复 PR #23–#27 的产品实现，也不把开放 PR 记为 `main` 已完成。

### 依赖与执行顺序

- 当前 `main` 为 `49b33339`；开始实现前必须重新 fetch 并确认 `main == main@origin`；
- PR #26 同时修改 `docs/development.md`，因此本任务第一批文件不包含该文件，避免并行冲突；采用记录以
  `THIRD_PARTY_NOTICES.md` 和本研究记录为准，待相关 PR 合并后再单独对齐开发文档；
- 新任务必须使用独立 Issue、单一 jj change、短期 bookmark 和 Draft PR；
- 任何现有 PR 合并导致 `main` 前进时，按已发布历史边界取得授权后 restack、完整重验和自审；
- 合并、服务器设置审计和远端 bookmark 清理仍由人类分别决定。

## 六、部署风险与控制

| 风险 | 影响 | 控制 |
| --- | --- | --- |
| 直接覆盖项目规则 | 丢失 HMI 范围、安全和验证边界 | 只做条款级合并，以本项目 `AGENTS.md` 为权威 |
| 使用未发布的上游 `main` | provenance 模糊，后续难复核 | 固定 `794b…`，逐文件记录实际派生范围 |
| 已发布 jj change 被 restack | 远端 PR 历史重写、审查失效 | 先列明受影响 change/bookmark 并取得人类授权，重跑完整验证和 diff 审查 |
| Windows 环境被误标为已验证 | 答辩机上入口或依赖失败 | 在真实目标机完成 smoke，记录 `jj`、Git、pwsh、Bash、pnpm、uv 版本 |
| CI Action 仅固定 tag | 上游 tag 移动或供应链风险 | 从各 Action 第一方 release 固定完整 commit SHA，并定期人工更新 |
| PR 校验器与模板不一致 | 合法 PR 被 CI 拒绝或错误正文漏检 | 模板和校验器同一 change 更新，增加 fixture/单测，跑本地与 CI |
| 只写仓库设置文档 | `main` 实际仍可绕过或 force push | 人类在 GitHub 服务器端核查 ruleset、merge 方式和 Agent 凭据 |

## 七、建议验收证据

选择性部署完成后，至少应有以下可复核证据：

- 采用记录同时写明原始 `v1.0.0` 基线和本次同步的完整 commit `794b…`，派生文件与 MIT notice 一致；
- 复杂任务 Issue Form 可创建一条包含目标、范围、验收、排除项、依赖顺序和权限确认的真实低风险 Issue；
- 在真实采用环境记录 `jj --version`、`git --version`，完成 fetch、单 change/bookmark、验证、push、Draft PR、人工 Squash Merge 和本地 bookmark 清理演练；
- `bash scripts/validate.sh` 覆盖两个校验器测试、仓库技术检查与 `pnpm check`，且本地和 CI 都通过；
- PR 正文的 Issue 路径与明确授权路径分别有成功 fixture，保留两条路径或仅保留注释时的行为有明确测试；
- GitHub workflow 的 Action SHA、只读权限、credential persistence、并发与确定性 `check` 名称经过完整 diff 审查；
- 人类记录 `main` 的 PR/required check/force-push/delete/merge method/auto-merge/Agent token 权限设置；
- PR 正文如实记录未执行的真实 Windows、视觉或运行态 Smoke，不用 Ubuntu CI 代替这些证据。

完成上述证据前，可以表述为“已采用 `v1.0.0`，正在选择性同步当前 `main` 加固”，不应表述为“当前 AgenticWonderwall 工作流已完整部署并验证”。
