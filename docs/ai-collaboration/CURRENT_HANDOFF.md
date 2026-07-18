# Current handoff

- Status: `opencode_first_v1_adopted`
- Owner: `Codex`（React 实现与复核）/ `Oasis`（PR、发布与后续合同批准）
- Updated: `2026-07-18 Asia/Shanghai`
- Active task: **OpenCode-First v1 工作流落地**已完成；GP21 产品实现保持原完成状态
- Stable task name: `OPENCODE-FIRST-V1` — 叶子任务默认路由、单次批准与外部数据授权
- Version name: `GP21-VISUAL-INTERACTION-FROZEN`
- Technical trace: 已添加 `.tmp/` 忽略规则并以 `jj file untrack .tmp` 取消跟踪浏览器生成缓存；缓存仍保留在磁盘，`jj status`/`jj log` 已恢复。
- Remote: `origin/main`
- Push state: Oasis 在 P0 摘要后以 `APPROVE PUSH opencode-first-v1` 精确批准；bookmark `opencode-first-v1` 已推送至 `origin`，指向 commit `7e9818437166`。未创建 PR、未发布

## Completed

- 正式记录 `GP21-VISUAL-INTERACTION-FROZEN`：人工交互验收 P0=0、P1=0；Make/Figma 保持只读，不自行创建 GP22；`gp05.v1` 协议不改名。
- React 已新增统一 `CockpitSnapshotV1` Store 与 WebSocket/HTTP snapshot 客户端。Cluster、HUD、Center、Passenger 和 Overview 通过 URL 端点消费同一 FastAPI 权威状态；客户端拒绝旧 revision 覆盖新 snapshot。
- 实现了首轮四屏呈现：行驶状态、导航接力摘要、活动风险的告警/处置状态、离线/恢复提示、Passenger 媒体风险抑制与隐私边界、VehicleVision 来源/置信度/生命周期显示，以及 1920/1440/1280 的响应式布局规则。
- FastAPI 已实现非破坏性的 `gp05.v1` 加性 `passenger` snapshot 字段，并实现 Center/Passenger 的路线预览/确认、媒体、隐私与旅程建议命令；所有 UI 变化均等待服务端回传 snapshot。
- Control 的 `set_system_mode=takeover` 现在建立清晰标记为 `simulated_event` 的演示风险，驱动 `active → acknowledged → resolved → recovery`、VehicleVision 健康度与副驾媒体安全抑制；不冒充真实感知结果。
- 未在 React 中保留“未自行发布”表述。
- 新增一页中文速查表，覆盖启动、批准、委派、验证、交接、推送和当前项目位置。
- 将工作流规则压缩为可执行核对项，同时保留根部 `AGENTS.md`、任务合同和 handoff 作为权威来源。
- 已批准的任务合同保持不变，合同哈希没有被破坏。
- Oasis 已批准采用 OpenCode-First v1：适合委派的 L0/L1 叶子任务默认先起草 OpenCode 合同，目标占适合委派任务约 65%；Codex 继续负责架构、协议、Token、安全、集成、发布和最终复核。
- 新增外部数据授权 P0 规则：批准摘要逐项列出将发送给 DeepSeek/OpenCode 的私有路径和数据类别，只有精确 `APPROVE <TASK-ID>` 才可记录 `EXTERNAL_DATA_SHARING` 并派发一次；泛化批准不得推断为外发许可。
- `.opencode-subagent/config.json` 已增加项目级 Codex-only 路径，保护公共合同、Token、协作规范、旧编排控制面、插件源码和学校/历史材料。
- `TASK-0003` 的 dashboard 去重目标已由 Codex change `e445b4d7` 完成并验证；该草案现为过期追溯资产，不批准、不派发。
- 新增 P0 外部发布门禁：Codex 必须先展示 push/PR 的远端、可见性、revision、文件/敏感数据、验证和排除项；Oasis 分别使用精确指令批准一次 push 与一次 PR。失败或范围变化后不得自动重试。
- OpenCode-First v1 已按新 P0 门禁完成首次 push：远端返回新增 bookmark 成功回执；GitHub 提供了 PR 创建链接，但本轮没有获得 PR 批准，因此未创建 PR。

## Modified files

- `apps/frontend/src/App.tsx`
- `apps/frontend/src/components/CockpitScreen.tsx`
- `apps/frontend/src/lib/useCockpitSnapshot.ts`
- `apps/frontend/src/lib/useCockpitCommand.ts`
- `apps/frontend/src/stores/cockpit.ts`
- `apps/frontend/src/stores/cockpit.test.ts`
- `apps/frontend/src/styles.css`
- `apps/backend/app/cockpit_state.py`
- `apps/backend/app/contracts/v1.py`
- `apps/backend/tests/test_cockpit_state.py`
- `apps/frontend/src/contracts/gp05-v1.ts`
- `contracts/gp05/v1/example.snapshot.json`
- `contracts/gp05/v1/manifest.json`
- `docs/ai-collaboration/PROJECT_DECISION_BASELINE.md`
- `docs/design/GP05_DESIGN_TO_CODE_CONTRACT.md`
- `docs/ai-collaboration/CURRENT_HANDOFF.md`
- `docs/ai-collaboration/WORKFLOW_QUICK_REFERENCE.md`

OpenCode-First v1 落地文件：

- `AGENTS.md`
- `.opencode-subagent/config.json`
- `docs/README.md`
- `docs/development.md`
- `docs/ai-collaboration/CURRENT_HANDOFF.md`
- `docs/ai-collaboration/HANDOFF_PROTOCOL.md`
- `docs/ai-collaboration/OPENCODE_FIRST_WORKFLOW.md`
- `docs/ai-collaboration/README.md`
- `docs/ai-collaboration/WORKFLOW_QUICK_REFERENCE.md`

## Verification

- `pnpm check` — passed：后端 22 tests、前端 8 tests、编排 tests 与前端构建均通过。
- `pnpm smoke` — passed：本地 FastAPI 的 HTTP、Mock 风险行程与旧 WebSocket smoke 链路均通过；验证结束后停止了临时服务。
- 前端单项 `lint`、`test --run`、`build` 已由 `pnpm check` 覆盖并通过。
- pytest 的 `.pytest_cache` 写入权限警告未影响 22 项测试结果。
- 文档链接、路径、任务术语与当前 handoff 已核对。
- OpenCode 项目环境与 `TASK-0003` 合同诊断通过；采用项目级保护路径后再次运行项目 `doctor` 也通过，OpenCode、Jujutsu 和 `pnpm` 可解析。
- OpenCode-First v1 落地 change 的 Markdown 链接、配置 JSON、术语和 jj 文件范围已核对；`pnpm check` 通过：后端 22 tests、前端 8 tests、旧编排 25 tests、lint 与前端 build 全部通过。pytest cache 写入警告不影响结果。
- P0 push/PR 门禁新增内容的 Markdown 链接与批准术语已再次核对；本次只修改 Agent/文档规则，未因该补丁重复运行产品测试。

## Confirmed boundaries

- 本页为速查摘要，不替代根部 `AGENTS.md`、局部 `AGENTS.md`、不可变任务合同或 `CURRENT_HANDOFF.md`。
- OpenCode-First v1 已通过 `opencode-first-v1` bookmark 推送，远端 commit 为 `7e9818437166`；没有创建 PR 或发布。
- `orchestration/tasks/*.json` 是已批准的不可变合同，本轮没有修改。
- 本轮保持 `gp05.v1` 协议名与任务编号；只增加向后兼容的 snapshot 乘客状态字段，未修改任何 `orchestration/tasks/*.json`。

## Token-cost documentation cleanup

- Stage B completed: simplified root `README.md` and `AGENTS.md`; added `docs/architecture.md`, `docs/development.md`, `docs/README.md`, and `docs/archive/README.md` as task-oriented entry points.
- Historical design evidence remains in `PreDesign/idea-archive/`; its index now declares it low-frequency and points to the authoritative decision baseline.
- No runtime source, configuration, contract, school material, lockfile, or generated asset was changed.
- Verification: local document links and paths checked; `pnpm check` run for the existing project validation suite.

## Next action

1. 执行 GP21 1920、1440、1280 三档运行态视觉回归，形成截图证据并修复任何裁切、重叠或横向溢出。此前 Windows 浏览器自动化未能可靠识别地址栏 URL；后续无头 Edge 批量截图也未按时退出，均未产生可采信的视觉结论。
2. 对视觉回归中可确定复现的局部修复，使用新的 TASK-ID 起草 OpenCode 合同；视觉裁决、跨屏一致性和最终复核仍由 Codex 负责。未经授权不 push、发布或创建 PR。

## Auxiliary workspace utility

- Added `scripts/windows-display-off/` with a double-click Windows launcher and PowerShell implementation.
- The utility turns off the displays, temporarily prevents system sleep while they are off, and restores the existing power policy after keyboard or mouse input.
- PowerShell syntax was validated without invoking the display-off action; no product runtime or approved task contract was changed.
