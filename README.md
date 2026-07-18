# 智能座舱多屏协同 HMI 设计与交互原型

毕业设计项目：以 Figma 为设计源，使用 React + TypeScript、FastAPI 和 WebSocket 验证主驾驶仪表、HUD、中控屏与副驾驶屏的共享状态和跨屏交互。

## 快速开始

```powershell
.\scripts\setup.ps1
pnpm dev
```

常用验证：

```powershell
pnpm lint
pnpm test
pnpm build
pnpm smoke
```

## 项目入口

| 需要了解的内容 | 入口 |
| --- | --- |
| 当前课题范围、架构与验收决策 | `docs/ai-collaboration/PROJECT_DECISION_BASELINE.md` |
| 系统概览 | `docs/architecture.md` |
| 开发、验证与版本协作 | `docs/development.md` |
| Agent 最小工作说明 | `AGENTS.md` |
| 当前工作交接 | `docs/ai-collaboration/CURRENT_HANDOFF.md` |
| 毕设设计依据与历史资料 | `docs/README.md` |

## 目录

- `apps/`：运行时前端、后端与 Agent dashboard。
- `contracts/`：跨端协议合同。
- `docs/`：当前说明、决策、设计与毕业设计证据。
- `PreDesign/`：设计规范和早期演示；`idea-archive/` 是低频历史资料。
- `deliverables/`：阶段交付文档。学校原始材料与内部方向截图不进入公开仓库。
- `scripts/`、`tests/`：开发和验证工具。

默认不要读取 `node_modules/`、`.pnpm-store/`、`.uv-*`、`.venv/`、`orchestration/runtime/`、`tmp/` 或 `outputs/`；它们是依赖、缓存、运行记录或生成物。道路风险、驾驶员监测和 LLM 内容属于早期技术基线，不自动代表最终课题范围。

## 使用许可

本仓库用于毕业设计作品展示与技术审查。当前未授予复制、再分发、修改或商业使用许可；第三方依赖与引用资料分别适用其原有许可和条款。
