# GP05 设计与实现偏差记录

## 已接受偏差

| ID | 来源 | 决策 | 理由与影响 |
|---|---|---|---|
| GP05-D01 | GP04 结构归档 | Center 从 1600×1000 调整为 1920×1080；Passenger 从 1600×720 调整为 1920×1080 | 以 2026-07-17 grilling 后的 GP05 实施基线为准；旧尺寸只保留历史证据 |
| GP05-D02 | GP04 字体实验 | 数字字体优先 Bahnschrift，缺失时回退 Barlow/Segoe UI | Bahnschrift 在历史 Figma 环境不可用；代码必须保证确定性 fallback |
| GP05-D03 | GP05 Make 代码 | 不整包复制 Make 生成的 React/CSS | Make 代码只作视觉与交互参考；生产代码必须适配单一 FastAPI 状态源和现有仓库 |
| GP05-D04 | GP05 导航演示 | 高德供应商数据为正式能力，本地路线只作明确降级 | 覆盖旧的“离线预设路线为主”方案；新增 MapProvider 与密钥边界 |
| GP05-D05 | OpenCV 原型 | 页面中的 Live/Video 切换不构成真实推理证据 | 真实摄像头、视频推理和风险状态机留给 GP05-IMPL-07/08 |

## 过渡期模型

现有 `apps/backend/app/models.py`、`apps/frontend/src/types.ts`、`/ws/simulation` 和 Zustand simulation Store 属于早期城市通勤 Demo。GP05-IMPL-01 只新增 `gp05.v1` 合同，不修改旧链路，避免在公共协议尚未被权威状态实现消费前破坏可运行基线。

后续 GP05-IMPL-02/03 必须显式完成迁移、兼容适配或删除计划；在此之前不得声称旧 `SimulationFrame` 就是 GP05 snapshot。

## Token 提取说明

- 来源：用户提供的 GP05 发布站点；
- 方式：只读提取发布 CSS 中的 `--gp-*` 与字体变量；
- 已确认：Day/Night 页面、面板、表面、文本、边框、raised、overlay 及字体栈；
- Tailwind 状态色映射冻结为 cyan/green/amber/rose 语义 Token；
- 未复制 Make 组件源码、业务逻辑或项目依赖。

## 尚未实现，不属于偏差

- FastAPI 权威状态与 WebSocket `gp05.v1` 广播；
- 高德 API 与本地 fallback；
- MySQL 会话、风险事件和交互审计；
- Vision Worker 与三类真实识别；
- Web3D 及 2D fallback；
- 四端页面迁移与 144/100/60 FPS 实测。

这些项目已经在 [`../project/IMPLEMENTATION_ROADMAP.md`](../project/IMPLEMENTATION_ROADMAP.md) 排序，不得在本合同任务中提前实现。
