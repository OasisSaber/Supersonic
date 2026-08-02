# 项目进度

- 最后更新：2026-08-02
- 远端主线：`main@origin = 38e3689acf74f83296f03d312760b3cc8183759a`
- 当前阶段：核心基线已建立，进入 GP22 资产迁移与平台化积极迭代期
- 方向共识：见 [`PROJECT_DIRECTION.md`](./PROJECT_DIRECTION.md)
- 权威范围：见 [`DECISION_BASELINE.md`](./DECISION_BASELINE.md)
- 执行路线：见 [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md)

## 1. 远端与合并状态

截至本次项目审计，PR #31–#37 已合并，最新主线 `38e3689a` 的 GitHub `Check` 已通过；当前没有待处理的产品 PR。此前的核心正确性、端点上下文、导航健康、`gp05.v1` 真实进程 Smoke 以及全量代码评审的三个修复均已进入主线。

合并事实：

| PR | 对应能力 | 状态 |
| --- | --- | --- |
| #31 | Issue #18，导航健康一致性 | 已合并 |
| #32 | Issue #17，独立 Control 端点 | 已合并 |
| #33 | Issue #14，`gp05.v1` 真实进程 Smoke | 已合并 |
| #34 | 2026-08-02 方向评审结论采纳 | 已合并 |
| #35 | review Critical #1，`destinationName` 超长原子拒绝 | 已合并 |
| #36 | review #2/#3，高信号降级为 medium、媒体状态参数防护 | 已合并 |
| #37 | review 安全发现，旅程建议长度上限 200 | 已合并 |

产品主线不再停留在 PR 门禁恢复阶段；后续工作重点转为 GP22 实现、平台基础设施和最终验收能力。

## 2. 当前模块状态

| 模块 | 状态 | 当前证据与边界 |
| --- | --- | --- |
| GP22 视觉与交互基线 | `APPROVED_DESIGN_REFERENCE` | Figma/Make 与本地交付包已核验；React 迁移尚未完成。 |
| Figma 持续资产 intake | `P0_READY_TO_START` | 已确认版本、节点、变更、映射和回归流程；尚待建立资产清单与首轮迁移证据。 |
| `gp05.v1` 合同与运行时 | `IMPLEMENTED_BASELINE` | 合同、权限矩阵、FastAPI 权威状态、HTTP/WebSocket 和 Smoke 已进入主线。 |
| React 四屏与 Control | `IMPLEMENTED_BASELINE_WITH_GP22_MIGRATION_PENDING` | Cluster、HUD、Center、Passenger、Overview 和 Control 可运行；GP22 视觉迁移仍是当前 P0。 |
| 三条本地核心流程 | `VERIFIED_BASELINE` | 导航接力、风险处置和副驾协作已有可重复实现；最终平台还需真实地图、持久化和 VehicleVision。 |
| PostgreSQL 平台数据层 | `P1_PLANNED` | 已确认正式数据库、schema、迁移、RBAC、审计、备份和恢复范围；尚未实现。 |
| 多用户与 RBAC | `P1_PLANNED` | `admin/operator/viewer`、登录、会话撤销、最小权限和角色界面已纳入最终验收；尚未实现。 |
| 真实地图/地点搜索 | `FINAL_ACCEPTANCE_PLANNED` | 需要 Provider 适配层、凭据隔离、服务失败和本地 fallback；当前仍以确定性本地路线为降级。 |
| 持久化与审计历史 | `FINAL_ACCEPTANCE_PLANNED` | PostgreSQL 负责持久化和查询，FastAPI/WebSocket 仍是实时状态权威；尚未实现。 |
| VehicleVision | `FINAL_ACCEPTANCE_PLANNED` | 首个真实疲劳/分心场景为主要创新；当前模拟事件必须继续标记为 `simulated_event`。 |
| 受限 AI 语音 | `FINAL_ACCEPTANCE_PLANNED_LATE` | 仅允许白名单 command、确认和失败反馈；不做自主驾驶决策。 |
| 多显示启动与部署 | `FINAL_ACCEPTANCE_PLANNED` | 必须可重复启动四屏；是否采用 Electron/Tauri 仍取决于现场部署需求。 |
| Web3D | `FINAL_ACCEPTANCE_PLANNED_LATE` | 后置时间盒实现，必须懒加载、绑定权威状态并有静态 fallback。 |

## 3. 当前执行队列

### P0：未来 4–6 周 GP22 与 Figma 资产闭环

- 迁移四屏基础框架、共享 Token、核心组件和正常/禁用/告警/空数据/降级状态；
- 建立 Figma 版本、节点范围、变更说明、影响屏幕和代码映射清单；
- 每次 Figma 产出执行“导入—校验—实现—回归—更新基线”；
- 产出四屏运行演示、视觉回归证据和资产清单。

### P1：并行平台基础设施

- PostgreSQL schema、迁移、索引和备份恢复演练；
- 登录、RBAC、会话撤销和服务端最小权限；
- 命令、风险、恢复结果和操作者审计；
- 数据库集成测试与恢复证据。

### 后续最终验收队列

1. 真实地图/地点搜索；
2. 持久化审计和恢复记录完善；
3. 一个真实 VehicleVision 疲劳/分心场景；
4. 受限 AI 语音；
5. 四屏多显示启动与部署编排；
6. 后置 Web3D。

## 4. 完成定义与运行质量

每项能力只有同时具备运行实现、自动化测试或可重复步骤、展示证据、准确的 Mock/真实/降级标记和同步文档，才能标记完成。

最终平台质量基线：

- 四屏启动和部署可重复；
- 本地命令确认延迟目标 P95 ≤ 500 ms；
- WebSocket 断线后自动恢复目标 ≤ 5 秒；
- 共享车辆状态不出现屏间分叉；
- 命令、风险和恢复事件审计完整率 100%；
- 关键错误具有日志、告警或可见安全降级；
- `bash scripts/validate.sh`、CI、数据库迁移/恢复测试和必要的目标机验证通过。

## 5. 最终验收与旗舰演示

2027 年 4 月最终验收必须同时覆盖 GP22、PostgreSQL/RBAC/审计、真实地图、持久化恢复、VehicleVision、受限 AI 语音、多显示部署和后置 Web3D。Web3D 可以后期完成，但不能豁免。

旗舰演示流程为：`operator` 登录 → 启动四屏 → 查看真实地图 → VehicleVision 触发受控风险 → 四屏联动降级 → 操作者确认恢复 → 写入审计 → `viewer` 查看历史 → `admin` 查看会话/审计 → Web3D 展示并静态回退。

## 6. 已知限制

- 当前 GP22 仍是设计批准和待迁移基线，不得表述为全部 React 功能已完成；
- 当前阶段不建设公共 SSO、复杂多租户、公共互联网网关、量产车辆安全认证或高可用集群；
- VehicleVision 不保存连续原始视频/音频，不做身份识别或情绪推断；
- 地图、语音、模型和 Web3D 外部服务必须提供安全降级；
- 第二个及更多 Vision 场景、桌面封装、正式发行和签名属于剩余时间或外部要求触发的增强项。
