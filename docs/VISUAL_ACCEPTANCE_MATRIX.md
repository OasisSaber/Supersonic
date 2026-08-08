# Supersonic Windows 六端点视觉验收矩阵

- 候选 PR：#45
- 候选基线：PR #45 当前 head
- 执行日期：2026-08-06、2026-08-08（Windows）
- 已有资产：72 张截图、权威快照与 `deliverables/visual-acceptance/v3/evidence.jsonl`
- 当前结论：`G1_VERIFIED`；视觉证据与 PR #45 GitHub Actions 已独立通过

## 已验证状态

| 状态 | Cluster | HUD | Center | Passenger | Overview | Control |
| --- | --- | --- | --- | --- | --- | --- |
| Night normal | pass | pass | pass | pass | pass | pass |
| Day normal | pass | pass | pass | pass | pass | pass |
| Navigation preview | pass | pass | pass | — | pass | — |
| Navigation active | pass | pass | pass | — | pass | — |
| Takeover | pass | pass | pass | pass | pass | pass |
| Acknowledged | pass | pass | pass | pass | pass | pass |
| Recovery | pass | pass | pass | pass | pass | pass |
| 数据域离线：默认无路线/无视觉 | pass | — | pass | — | pass | — |
| `systemMode=stale` | pass | pass | pass | pass | pass | pass |
| `systemMode=offline` | pass | pass | pass | pass | pass | pass |
| 后端/WebSocket 连接中断 | pass | pass | pass | pass | pass | pass |
| Control disabled | — | — | — | — | — | pass |
| 1366×768 Night normal | conditional | conditional | conditional | conditional | conditional | conditional |
| 2560×1440 Night normal | pass | pass | pass | pass | pass | pass |

## 尚未验证，不能由现有截图替代

| 状态 | 当前证据 | 需要补充 |
| --- | --- | --- |
| 1920×1080、200% 浏览器缩放 | 未执行 | 人工浏览器验证 |
| GP22 Figma 逐屏对照 | 未执行 | 节点映射、偏差和批准记录 |
| Day/Night 对比度实测 | 未执行 | 自动或人工对比度报告 |

## 证据解释

`offline-default` 快照证明的是：

- `systemMode=normal`；
- 传输连接保持 `fresh`；
- `navigation` 与 `vision` 数据域为 `offline`。

它不能证明服务离线、WebSocket 中断或 `systemMode=offline`。PR 描述、进度文档和
答辩材料必须使用“数据域离线”这一准确名称。

2026-08-08 新增证据分别证明：

- `system-stale/`：权威快照为 `systemMode=stale`，六端点连接均为 `fresh`；
- `system-offline/`：权威快照为 `systemMode=offline`，六端点连接均为 `fresh`；
- `connection-interrupted/`：后端不可达时六端点均显示连接中断提示，并保留最后一次
  权威快照；后端恢复后六端点自动连接到新的权威会话。

## 分辨率

1920×1080 与 2560×1440 未发现横向或纵向溢出。1366×768 无横向滚动，但六端点
存在纵向滚动，判定为 conditional；后续只修有截图证据的密度问题。

## G1 退出条件

本地视觉证据已完成以下事项：

1. `systemMode=offline` 六端点证据；
2. `systemMode=stale` 六端点证据；
3. 实际连接中断和恢复证据；
4. 截图、快照与 evidence.jsonl 的状态名称一致。

PR #45 GitHub Actions 独立通过前，G1 仍不得标记为最终通过。
