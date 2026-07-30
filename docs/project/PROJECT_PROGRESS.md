# 项目进度

- 最后更新：2026-07-31
- 当前分支基线：`main` 已包含 PR #15 与 PR #16
- 项目形态：本地、单用户、可信环境的毕业设计 HMI 原型
- 证据原则：可运行代码、测试、CI 与实际工具输出优先于规划文档；接口占位、模拟数据和历史方案不得写成已完成功能。

## 当前阶段

| 模块 | 状态 | 当前证据与边界 |
| --- | --- | --- |
| GP21 视觉与交互基线 | `FROZEN_DESIGN_REFERENCE` | Figma/Make 视觉意图已冻结；这不代表 React 运行时没有缺陷或所有功能均已完成。 |
| `gp05.v1` 合同与 Token | `IMPLEMENTED_WITH_KNOWN_DEFECTS` | TypeScript/Pydantic 合同、端点、命令、风险生命周期、数据健康与 Day/Night Token 已进入源码。运行时校验完整性由 Issue #19 跟踪。 |
| FastAPI 权威状态与广播 | `IMPLEMENTED_WITH_KNOWN_DEFECTS` | 内存权威状态、HTTP snapshot/command 与 WebSocket 全量广播已实现。Session/reset 一致性由 Issue #11 跟踪。 |
| React 产品端点 | `PARTIAL` | Cluster、HUD、Center、Passenger 与 Overview 已存在；Overview 只读边界由 Issue #7 跟踪，独立 Control 由 Issue #17 跟踪。 |
| 三条本地演示流程 | `PARTIAL` | 本地路线接力、模拟风险接管、副驾媒体/隐私协作可运行；风险选择一致性由 Issue #12 跟踪，导航健康一致性由 Issue #18 跟踪。 |
| 主题运行时 | `VERIFIED` | Issue #9 / PR #15 已加载设计 Token，并将 React 根主题绑定到服务端权威 snapshot。 |
| 根目录环境配置 | `VERIFIED` | Issue #10 / PR #16 已统一前后端根 `.env` 配置，并拒绝未实现的运行模式。 |
| 核心 `gp05.v1` 集成 Smoke | `NOT_IMPLEMENTED` | 当前 `pnpm smoke` 仍只验证旧 Mock 链；四端连接、命令收敛、重置与重连由 Issue #14 跟踪。 |
| 高德 MapProvider | `CONDITIONAL_NOT_IMPLEMENTED` | 当前仅有确定性 `local_fallback`。只有答辩或论文明确需要真实地点检索时才提升为核心工作。 |
| 持久化与审计 | `CONDITIONAL_NOT_IMPLEMENTED` | 当前没有 MySQL。只有论文、指导教师或行程报告需要历史查询时才实施。 |
| VehicleVision | `PLANNED_DIFFERENTIATOR` | 当前风险事件明确标记为 `simulated_event`。核心 HMI 稳定后优先评估一个真实疲劳/分心场景；其他场景为增强项。 |
| Web3D | `CONDITIONAL_NOT_VERIFIED` | 依赖存在，但当前前端源码和验证证据未证明可用实现；不得阻塞核心 HMI。 |
| AI 语音 | `GATED` | 仅在核心 HMI、恢复和主要创新证据稳定后单独评估。 |

## 已实现产品能力

- 版本化 `gp05.v1` TypeScript/Pydantic 合同；
- FastAPI 内存权威状态、命令权限矩阵、HTTP snapshot/command API 与端点 WebSocket 全量 snapshot 广播；
- Cluster、HUD、Center、Passenger 和 Overview 消费同一权威快照；
- Center 可执行本地路线预览/确认与风险处置；
- Passenger 可控制媒体、隐私和旅程建议；
- `takeover` 只生成明确标记为 `simulated_event` 的演示风险，并驱动 `active → acknowledged → resolved → recovery`；
- GP21 Day/Night Token 已加载，主题由权威 snapshot 控制；
- 前后端统一读取仓库根目录 `.env`，当前只接受 `APP_MODE=mock`；
- GitHub Actions 执行 PR 结构验证、Markdown/YAML/Shell 检查、Lint、测试和前端构建。

## 开放工作队列

### P0 — 状态完整性与恢复

- Issue #11：Session-aware revision 排序与 reset 后连接状态重建。

### P1 — 核心产品正确性与答辩功能

- Issue #7：Overview 严格只读，不再被视觉重设计阻塞；
- Issue #12：统一主要风险选择和 Passenger 媒体安全抑制；
- Issue #17：实现独立 Control 端点，不再回退为 Center；
- Issue #19：拒绝损坏 WebSocket/合同数据并安全重连。

### P2 — 近期可靠性、内部权限与证据

- Issue #18：导航 route/provider/data-health 状态一致性；
- Issue #13：基于服务端拥有的本地请求上下文确定端点权限，不建设通用认证平台；
- Issue #14：真实 FastAPI 进程和四客户端 `gp05.v1` Smoke，并接入 CI。

### 条件性或核心稳定后评估

- 一个真实驾驶员疲劳/分心 VehicleVision 场景；
- 持久化和历史查询；
- 高德真实地点检索；
- Web3D 状态可视化；
- 额外 Vision 场景；
- AI 语音、桌面封装和公开发行基础设施。

这些工作当前不得阻塞 P0/P1 队列，除非指导教师、学校交付或明确部署方式提出新的硬要求。

## 验证证据

### 已合并产品修复

- PR #15：前端主题/Token 修复记录显示前端 lint、11 项测试、构建和 `scripts/validate.sh` 通过；
- PR #16：根配置修复记录显示后端 30 项、前端 12 项测试、构建和 `scripts/validate.sh` 通过；
- 两个 PR 均已 Squash Merge 至 `main`。

### 当前 Smoke 边界

当前 `pnpm smoke` 验证：

- `/api/health`；
- `/api/events`；
- `/api/trips/demo`；
- Mock report；
- `/ws/simulation` 消息序列。

它不验证：

- `/api/v1/snapshot`；
- `/api/v1/commands`；
- `/ws/v1/cockpit`；
- 四端并发收敛；
- reset/reconnect；
- 完整端点权限边界。

在 Issue #14 完成前，不得把 `pnpm smoke` 写成完整多屏集成测试。

## 当前验收标准

核心 HMI 可进入答辩冻结前，至少需要：

1. Issue #11、#7、#12、#17 和 #19 完成；
2. 四个产品端点与 Control 使用同一权威 session 和 revision；
3. 三条本地确定性流程可重复执行和重置；
4. Issue #14 的真实进程多客户端 Smoke 通过 CI；
5. 所有 Mock、真实来源、降级状态和未实现能力有明确标签；
6. 关键操作具备错误、离线和恢复表现；
7. 文档、代码和展示口径一致。

真实地图、MySQL、Web3D、多场景 Vision 和 AI 语音不是上述核心验收的默认硬依赖。

## 待外部确认

- 指导教师对创新点、数据库必要性、AIGC 声明和最终提交格式的要求；
- 最终答辩设备数量和物理安装方式；
- 核心 HMI 稳定后，选择哪一个 VehicleVision 场景作为主要工程创新；
- 是否存在必须使用真实地图、数据库或安装包的学校要求。