# GP05 设计到代码合同 v1

- 协议版本：`gp05.v1`
- 视觉来源：`GP21-VISUAL-INTERACTION-FROZEN`（协议版本仍为 `gp05.v1`）
- 发布证据：[Visual Design Specification Plan](https://revise-body-79291535.figma.site)
- 运行时无关 manifest：[`../../contracts/gp05/v1/manifest.json`](../../contracts/gp05/v1/manifest.json)
- Python 合同：[`../../apps/backend/app/contracts/v1.py`](../../apps/backend/app/contracts/v1.py)
- TypeScript 合同：[`../../apps/frontend/src/contracts/gp05-v1.ts`](../../apps/frontend/src/contracts/gp05-v1.ts)
- 已知偏差：[`GP05_DESIGN_DEVIATIONS.md`](./GP05_DESIGN_DEVIATIONS.md)

## 1. 真相分层

1. Make/Figma 冻结快照定义视觉意图；
2. 本合同与 manifest 定义跨层字段、枚举、权限和逻辑画布；
3. FastAPI 在后续任务中成为唯一实时业务状态源；
4. React 只呈现 snapshot 并提交 command，不复制权威状态；
5. MySQL 只保存会话、风险事件和交互审计，不成为实时状态源。

本任务不迁移现有早期 Demo，也不实现 WebSocket、地图、MySQL、Vision Worker、Web3D 或页面。后续实现只能扩展 `gp05.v1` 的可选数据；破坏性字段变化必须升级协议版本。

## 2. 逻辑画布与职责

| 端点 | 逻辑画布 | 不可替代职责 |
|---|---:|---|
| Cluster | 1920 × 720 | 驾驶状态、路线状态、风险等级与处置状态 |
| HUD | 1280 × 480 | 最低认知负荷的下一步驾驶决策与行动提示 |
| Center | 1920 × 1080 | 路线规划、车辆/环境控制、风险详情与确认 |
| Passenger | 1920 × 1080 | 娱乐、旅程协作输入、副驾安全反馈与许可控制 |
| Overview | 自适应编排 | 只读四屏总览，不是第五个产品端点 |
| Control | 桌面诊断布局 | 数据源、场景、性能、会话和答辩控制 |

产品端点按固定逻辑画布渲染，只允许等比缩放与安全边距适配。Overview 缩略显示四个独立客户端，不得用一张静态合成图替代。

## 3. 消息合同

所有消息只有三种：`command`、`event`、`snapshot`。共同字段为：

- `protocolVersion`：固定为 `gp05.v1`；
- `messageId`：消息 UUID；
- `correlationId`：一次意图、事件和后续 snapshot 的关联 UUID；
- `timestamp`：UTC ISO 8601；
- `source`：`endpoint` 或 `service` 及其稳定 ID；
- `target`：可为空的目标端点；
- `kind`：消息判别字段；
- `payload`：与 kind 对应的严格载荷。

`snapshot` 是四屏恢复与重连的唯一完整状态；客户端不得把未确认 command 当成最终状态。外部地图、Vision、测试注入器和控制台都先产生 command/event，再由 FastAPI 在后续任务中生成新 revision 的 snapshot。

## 4. 系统与风险状态

系统模式：

`normal | warning | takeover | stale | offline | recovery`

组件状态：

`normal | active | disabled | warning | critical | loading | empty | stale | offline`

风险生命周期：

`candidate → active → acknowledged → resolved`

单帧检测只能产生 candidate。只有经过阈值、持续时间和冷却规则的 active 风险才能改变四屏；同一事件在生命周期内更新，不重复创建。

## 5. 核心流程

1. `navigation_handoff`：Center 搜索并确认，高德 MapProvider 返回统一路线，Cluster 接管状态，HUD 提炼下一步，Passenger 可提交旅程建议；
2. `risk_takeover`：Vision 候选事件经策略层变为 active，Cluster/HUD 优先提示，Center 提供详情/确认，Passenger 暂停娱乐并提示协助；
3. `passenger_collaboration`：Passenger 提交媒体、旅程与许可座舱意图，Center 显示必要共享状态，驾驶关键端点不显示娱乐内容。

端点 command 白名单以 manifest 为准。HUD 和 Overview 无业务 command；Control 拥有完整答辩控制权限，但仍必须经过 FastAPI，不能直接改客户端 Store。

## 6. Token 合同

Day/Night 的 `--gp-*` 颜色与字体来自 2026-07-17 对已发布 GP05 CSS 的只读提取。实现文件为 [`../../apps/frontend/src/design/gp05-tokens.css`](../../apps/frontend/src/design/gp05-tokens.css)。

- 圆角：8 / 12 / 16 px；
- 中文字体：Noto Sans SC → Barlow → Segoe UI → sans-serif；
- 数字/拉丁字体：Bahnschrift → Barlow → Segoe UI → sans-serif；
- focus：cyan；success：green；warning：amber；critical：rose；
- 告警、离线和恢复必须同时提供图标/文字/位置等第二通道，不能只依赖颜色。

夜间青色只用于焦点、路线和选中状态，不建立大面积装饰性渐变。

## 7. 数据新鲜度与降级

每个主要域使用 `fresh | stale | offline`，并携带更新时间。stale 显示最后值和时间；offline 明确不可用，不伪造实时数据。导航供应商失败时使用 `local_fallback`，Vision 注入来源必须标记 `simulated_event`。

## 8. 兼容与升级规则

- 新增可选能力可放入 `capabilities` 或事件 `metadata`；
- 高频查询字段不得长期藏在 metadata；
- 删除、改名、改变字段语义或权限属于破坏性变化，升级为新协议；
- 现有 `apps/backend/app/models.py` 与 `apps/frontend/src/types.ts` 是早期 Demo 合同，在后续迁移任务完成前继续保留，不得静默冒充 GP05 v1。
