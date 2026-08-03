# Supersonic：智能座舱多屏协同 HMI

Supersonic 是面向毕业设计的智能座舱多屏协同 HMI：以 Figma 为设计源，使用 React + TypeScript、FastAPI 和 WebSocket 验证主驾驶仪表、HUD、中控屏与副驾驶屏的共享状态和跨屏交互。

## 项目定位

本仓库是面向作者本人和答辩现场的**本地、单用户、可信环境原型**，主要运行方式是一台 Windows 主机启动 FastAPI 与多个浏览器端点。它不是公共互联网服务、量产车载系统或企业级多租户平台。

当前工程重点是：

- 保证一个 FastAPI 权威状态驱动四屏；
- 让导航接力、风险接管和副驾协作可确定性演示；
- 明确区分真实能力、Mock、降级数据和未实现能力；
- 保证重启、重置、断线和错误输入不会让四屏显示相互矛盾的状态；
- 为毕业设计提供可重复的代码、测试和展示证据。

当前阶段不以多租户、公共 API、高可用、企业 SSO、代码签名、公证、容器隔离或完整供应链治理为开发阻断项。只有在明确出现公共部署、安装包分发或学校交付要求时，才单独评估这些条件性工作。

## 当前能力

`main` 当前已具备：

- 版本化 `gp05.v1` TypeScript/Pydantic 合同；
- FastAPI 内存权威状态、HTTP 命令和 WebSocket 全量快照；
- Cluster、HUD、Center、Passenger 与 Overview 页面；
- 本地确定性路线预览/确认、模拟风险生命周期和副驾媒体/隐私协作；
- GP21 Day/Night Token 与服务端权威主题绑定；
- 仓库根目录统一 `.env` 配置；
- Ruff、ESLint、pytest、Vitest、构建和 GitHub Actions 验证入口。

尚未完成或仍有已知缺陷的能力以 [`docs/project/PROJECT_PROGRESS.md`](docs/project/PROJECT_PROGRESS.md) 和开放 Issue 为准。真实高德地图、MySQL、VehicleVision、Web3D 和 AI 语音均不应被描述为当前已实现功能。

## 快速开始

```powershell
Copy-Item .env.example .env
.\scripts\setup.ps1
pnpm dev
```

运行时配置统一放在仓库根目录 `.env`。该文件已被 Git 忽略；不要提交密钥、模型路径或私人素材路径。当前后端只实现 `APP_MODE=mock`，`local`、`api` 和其他值会明确拒绝启动。`VITE_API_URL` 控制 `gp05.v1` 前端访问 FastAPI 的 HTTP 与 WebSocket 基地址；`VITE_WS_URL` 仅保留给旧 simulation Hook。LLM、模型和视频变量仍是保留名称，不代表对应能力已经实现。

完整配置合同见 [`docs/development.md`](docs/development.md)。

## 验证

```powershell
pnpm lint
pnpm test
pnpm build
pnpm check
pnpm smoke
```

- `pnpm check` 是当前静态检查、单元测试和前端构建入口。
- `pnpm smoke` 运行 `gp05.v1` 真实进程 Smoke，覆盖四个产品端点、命令广播、权限拒绝、会话重置和 HUD 重连。
- 该 Smoke 证明当前确定性本地链路成立；真实地图、数据库、VehicleVision、AI 语音和多显示部署仍需各自的验收证据。

## 当前工作队列

推荐实施顺序：

1. 状态完整性：Issue #11；
2. 核心端点正确性：Issues #7、#12、#17、#19；
3. 近期可靠性与内部权限：Issues #18、#13；
4. 核心运行态证据：Issue #14；
5. 核心稳定后，再按毕业设计收益评估一个真实 VehicleVision 场景、持久化、真实地图或 Web3D。

详细优先级与条件性工作见 [`docs/project/IMPLEMENTATION_ROADMAP.md`](docs/project/IMPLEMENTATION_ROADMAP.md)。

## 项目入口

| 需要了解的内容 | 入口 |
| --- | --- |
| 当前课题范围、工程标准与非目标 | `docs/project/DECISION_BASELINE.md` |
| 当前产品进度、验证和开放缺陷 | `docs/project/PROJECT_PROGRESS.md` |
| 可执行工作队列与条件性能力 | `docs/project/IMPLEMENTATION_ROADMAP.md` |
| 系统边界与可信运行模型 | `docs/architecture.md` |
| 开发、验证与版本协作 | `docs/development.md` |
| Agent 工作规则 | `AGENTS.md` |
| 毕设设计依据与历史资料 | `docs/README.md` |

## 目录

- `apps/`：运行时前端与后端；
- `contracts/`：跨端协议合同；
- `docs/`：当前说明、决策、设计与毕业设计证据；
- `PreDesign/`：设计规范和早期演示，`idea-archive/` 是低频历史资料；
- `deliverables/`：阶段交付文档；
- `scripts/`、`tests/`：开发和验证工具。

默认不要读取 `node_modules/`、`.pnpm-store/`、`.uv-*`、`.venv/`、`tmp/` 或 `outputs/`；它们是依赖、缓存或生成物。道路风险、驾驶员监测和 LLM 内容中的早期技术基线不自动代表最终课题范围。

## 使用许可

本仓库用于毕业设计作品展示与技术审查。当前未授予复制、再分发、修改或商业使用许可；第三方依赖与引用资料分别适用其原有许可和条款。