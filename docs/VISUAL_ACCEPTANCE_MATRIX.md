# Supersonic Windows 六端点视觉验收矩阵

- 资产包：Supersonic Next-Phase Quality Pack v3
- 基线：`main@e8610d8712f2fc878525ee2e62cd88693dbc7396`
- 任务 change：`mzwouxuy` / bookmark `codex/task-quality-pack-v3`（合并后以 main 上的 squash commit 为准）
- 执行日期：2026-08-06（Windows）
- 执行方式：真实 `pnpm dev` 前后端进程 + Chromium（playwright-cli，headless），命令驱动后端状态机
- 截图集：`deliverables/visual-acceptance/v3/<状态>/<端点>.png`（54 张）
- 快照证据：`deliverables/visual-acceptance/v3/evidence.jsonl`（每个状态的权威 session/revision/theme/mode/dataHealth/risks/endpointConnectivity）

## 截图记录字段

每张截图对应：任务 change `mzwouxuy`、URL（`http://127.0.0.1:5173/<endpoint>`）、viewport、theme、session ID、revision、system mode、数据来源、与 GP22 Figma 的偏差、结论。session/revision/theme/mode 等运行时事实见 `evidence.jsonl`，全部六端点共享同一权威快照。

## 状态矩阵

| 状态 | Cluster | HUD | Center | Passenger | Overview | Control |
| --- | --- | --- | --- | --- | --- | --- |
| Night normal | pass | pass | pass | pass | pass | pass |
| Day normal | pass | pass | pass | pass | pass | pass |
| Navigation preview | pass | pass | pass | — | pass | — |
| Navigation active | pass | pass | pass | — | pass | — |
| Takeover | pass | pass | pass | pass | pass | pass |
| Acknowledged | pass | pass | pass | pass | pass | pass |
| Recovery | pass | pass | pass | pass | pass | pass |
| Offline（默认无路线/无视觉） | pass | — | pass | — | pass | — |
| Control disabled | — | — | — | — | — | pass |
| 1366×768 Night normal | conditional | conditional | conditional | conditional | conditional | conditional |
| 2560×1440 Night normal | pass | pass | pass | pass | pass | pass |
| 1920×1080 200% 浏览器缩放 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 | 未执行 |

## 状态链证据（同一 session）

| 状态 | session 前缀 | revision | theme | system mode | vehicle | navigation | vision | risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| night-normal | 793ddaf2 | 12 | night | normal | fresh | offline | offline | — |
| navigation-preview | 793ddaf2 | 13 | night | normal | fresh | stale | offline | — |
| navigation-active | 793ddaf2 | 14 | night | normal | fresh | stale | offline | — |
| takeover | 793ddaf2 | 15 | night | takeover | fresh | stale | fresh | active/critical |
| acknowledged | 793ddaf2 | 16 | night | takeover | fresh | stale | fresh | acknowledged/critical |
| recovery | 793ddaf2 | 17 | night | recovery | fresh | stale | offline | resolved/critical |
| offline-default | f2f4a8c7 | 18 | night | normal | fresh | offline | offline | — |
| day-normal | f2f4a8c7 | 19 | day | normal | fresh | offline | offline | — |

全部状态下六个端点连接均为 `fresh`（6/6）。Overview 只读预览，无命令控件；Control 在 `CONTROL_ENABLED=true` 下可发命令，默认配置下为禁用态。

## 分辨率与滚动检查

1920×1080 与 2560×1440：六个端点 `scrollWidth == clientWidth` 且 `scrollHeight == clientHeight`，无横向或纵向溢出。

1366×768：`scrollWidth == clientWidth`（无横向滚动），但全部六个端点存在纵向滚动（scrollHeight 789–989 vs clientHeight 768）。驾驶关键内容不被折叠或遮挡，控件可操作；判定为 conditional，建议后续评估是否压缩 768p 高度下的垂直密度。

## 已知偏差与未覆盖项

- GP22 Figma 逐屏像素对照未执行：当前执行环境无 Figma 访问（未安装 Figma MCP / 无会话），`docs/APPLE_HIG_INSPIRED_DESIGN_SPEC.md` 的通用原则已由静态规则与截图核验覆盖。
- 1920×1080 200% 浏览器缩放未执行：playwright-cli 无浏览器 zoom API，未用 deviceScaleFactor 冒充缩放。
- Day/Night 对比度实测（无障碍仪器测量）未执行。
- 开发服务器 favicon 404：`/favicon.ico` 未提供，属于 dev 环境噪音，不影响六端点功能。
- WebSocket 首次连接偶发“closed before established”警告：前端 500ms 起指数退避自动重连，HTTP bootstrap 快照兜底，最终全部端点 `fresh`。

## 结论

核心状态矩阵通过：六端点 Night/Day normal、navigation、takeover、acknowledged、recovery、offline、Control disabled/enabled 均渲染正常，同一 session/revision，数据来源与降级标签明确，无横向溢出，Overview 无业务命令，destructive 重置具备二次确认（`ControlScreen`）。1366×768 为 conditional（纵向滚动）。Figma 对照与 200% 缩放列入后续待办。
