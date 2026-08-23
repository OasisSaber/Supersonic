# GP22 设计来源清单

- 状态：`APPROVED_DESIGN_REFERENCE`
- 批准日期：2026-08-01
- 批准人：Oasis
- 对应决策：[`../project/DECISION_BASELINE.md`](../project/DECISION_BASELINE.md)
- 运行时协议：`gp05.v1`，不因设计版本升级而改名

本文记录 GP22 的权威来源、可追溯指纹、Figma 节点入口和引入边界。它证明设计资产已经交付并获批准，但不把 Make 生成代码、Figma 画布或未迁移的 React 页面表述为生产实现。

## 1. 权威设计入口

- 一级可编辑来源：Figma Make [Visual-Design-Specification-Plan](https://www.figma.com/make/IIunappOuZk1JYMVT7uCuL/Visual-Design-Specification-Plan)
  - file key：`IIunappOuZk1JYMVT7uCuL`
  - 2026-08-24 只读核验：98 个源文件资源与 24 个 PNG 资源；Make 生成代码和图片资源不自动进入生产范围
- 可检查设计画布：Figma Design [GP22](https://www.figma.com/design/MIUgoK0YUwDjTCJpGI6W1o/GP22?node-id=0-1)
  - file key：`MIUgoK0YUwDjTCJpGI6W1o`
  - 页面：`0:1` / `Page 1`
  - 顶层设计帧：`1:2` / `Visual Design Specification Plan`
- 发布预览：[Visual Design Specification Plan](https://revise-body-79291535.figma.site)

Figma MCP 于 2026-08-01 首次完成只读核验，并于 2026-08-24 对 Issue #67 重新核验：文件包含一个页面、一个 `1112 × 26001` 的顶层设计帧和 8,632 个后代节点，其中包括 3,557 个 Frame、2,652 个 Text、2,190 个 Vector 与 233 个 Group。Figma Make、Figma Design 与发布预览是相关但不同的来源身份，不得混写 file key 或把预览当作可编辑源。

## 2. 本地交付包指纹

交付包保存在仓库外部的受控素材目录，不将二进制设计源、AI 会话或 Make 生成物提交到 Git。

| 文件 | 字节数 | SHA-256 | 结构摘要 |
| --- | ---: | --- | --- |
| `GP22.fig` | 1,651,359 | `A7038FDE270E763F697D3556F6C5BF0C186D6EFB34A21D0D6B5F3C3B08953C7F` | Figma 容器：`canvas.fig`、`thumbnail.png`、`meta.json` |
| `visual-design-spec-plan.make` | 1,805,454 | `1BFAA51DF5FBE7B6EF69F10450BECCCEDC2797EE5ADB7236E1E938EF2ADEF807` | Make 容器：画布、缩略图、图片、AI 会话和二进制引用 |
| `Visual Design Specification Plan.zip` | 277,443 | `892913EE62407F550BDC4079101542B847A470006D2C7661D656CB3B40A1F361` | 102 个代码包条目：78 TSX、9 CSS、5 TS、5 Markdown 及构建配置 |

上述哈希用于确认后续读取的是同一份人类批准交付物；文件内容发生变化时必须重新核验并记录新的设计决策。2026-08-24 重新核验时，`.make` 与 `.fig` 的字节数和 SHA-256 与本表一致；历史 `Visual Design Specification Plan.zip` 当次不在受控素材目录中，因此只保留既有批准指纹，不声称完成了当次重算。

## 3. 仓库内持久化基线

Issue [#67](https://github.com/OasisSaber/Supersonic/issues/67) 建立了 [`../../deliverables/design-baselines/gp22/`](../../deliverables/design-baselines/gp22/)：

- [`README.md`](../../deliverables/design-baselines/gp22/README.md)：资产基线角色、边界与验证入口；
- [`PROVENANCE.md`](../../deliverables/design-baselines/gp22/PROVENANCE.md)：来源核验、外部二进制决策、权利/隐私与限制；
- [`SOURCE_INVENTORY.csv`](../../deliverables/design-baselines/gp22/SOURCE_INVENTORY.csv)：逐项分类、来源、归档路径、SHA-256 与处置；
- [`MANIFEST.sha256`](../../deliverables/design-baselines/gp22/MANIFEST.sha256)：仓库内文件完整性；
- [`screenshots/`](../../deliverables/design-baselines/gp22/screenshots/)：按节点导出的 Cluster、HUD、Center、Passenger、Storyboard 与 Extended Design Spec；
- [`tokens/gp22-design-spec.json`](../../deliverables/design-baselines/gp22/tokens/gp22-design-spec.json)：从 `1:11373` 可见规范文字规范化的派生快照；它不是 Figma Variables 导出，也不证明运行时 Token 已迁移完成。

原始 `.make`、`.fig`、AI 会话、Make 源码、字体二进制与未单独确认权利的图片仍不进入 Git。短期 MCP/下载 URL 不作为永久 provenance。

## 4. 关键节点与实施路由

| 设计区域 | Figma 节点 | 代码责任边界 |
| --- | --- | --- |
| 四屏主界面 | `1:46` | `/cluster`、`/hud`、`/center`、`/passenger` 的视觉与信息层级参考 |
| Cluster | `1:48` | 只读驾驶状态、路线与风险 |
| HUD | `1:159` | 最低认知负荷的下一驾驶行动 |
| Center | `1:220` | 路线、风险详情与允许的确认操作 |
| Passenger | `1:418` | 媒体、隐私和旅程协作 |
| 跨屏 Storyboard | `1:563` | 导航接力、风险接管、副驾协作的设计说明；步骤控制不进入产品端点 |
| VehicleVision | `1:1126` | 真实、视频与模拟来源的可见区分；不证明推理能力已实现 |
| React Implementation Reference | `1:12840` | 路由、组件、状态、字段与验收映射参考 |
| Overview | `1:4321` | `/overview` 只读总览，不挂载业务命令控件 |
| Control | `1:4911` | `/control` 本地演示与诊断，不绕过 FastAPI 权威状态 |
| Endpoint Gallery | `1:12843` | 四端点 × 四场景状态参考 |
| Navigation States | `1:12844` | 导航生命周期参考 |
| Risk Matrix | `1:12845` | 风险等级与生命周期参考 |
| System States | `1:12846` | loading、empty、offline、degraded 与 command failure 参考 |
| Extended Design Spec | `1:11373` | 色彩、排版、间距、组件状态、告警优先级、动效与命名规范 |

完整 `1:2` 设计帧超过单次 design-context 输出范围。实现任务必须按上述节点分批读取，并在每个 Issue 中记录目标节点和验收范围。

## 5. 设计系统结构边界

MCP 核验时，Figma 文件没有本地 Component、Component Set、Variable Collection、Paint Style、Text Style、Effect Style 或 Grid Style。画布中的 `Button`、`ScreenFrame` 等名称是 Frame 层命名，不等同于可复用 Figma Component。

因此：

- 不得声称 Figma Variables 已经同步到代码；
- GP22 Token 必须先从扩展设计规范与 Make CSS 中提取，再映射到现有集中式代码 Token；
- 可复用 React 组件应优先复用或深化当前项目组件，不按 Make 目录机械复制；
- 若后续在 Figma 建立 Variables 或组件库，应作为新的、可追溯的设计系统变更记录。

## 6. Make 代码包边界

代码包可作为结构和视觉参考，但不是生产代码：

- `src/app/App.tsx` 仍从历史目录 `gp12/GP12` 载入界面；`gp12/version.ts` 通过 `CURRENT_VERSION = 22` 生成可见的 `GP22 / Version 22`；
- 包内同时保留 GP04、GP06、GP08、GP09、GP11、GP12 和 GP15 过程材料；这些历史文件不自动进入当前范围；
- 包含 MUI、Radix、Tailwind、Motion 等大量通用依赖，不得因设计包存在而批量加入生产依赖；
- Storyboard 的上一步、下一步、重置与场景选择属于 `/control` 或设计说明，不属于四个产品端点；
- Make 本地状态不得成为第二套业务真相；运行时状态继续由 FastAPI snapshot 确认；
- 设计稿中的“本地编辑版本，未自行发布”等制作说明不得进入产品 React 界面。

## 7. 引入完成条件

单个 GP22 页面或组件只有同时满足以下条件，才可写成已进入运行时：

1. 对应 Issue 明确记录 Figma 节点、代码文件、验收条件和排除项；
2. 设计 Token 映射到集中式代码 Token，未形成端点私有主题真相；
3. 组件消费现有 `gp05.v1` snapshot/command 边界，不复制权威业务状态；
4. 正常、交互、禁用、告警、加载、空数据和降级状态按适用范围覆盖；
5. 自动化测试、构建、仓库验证和必要的视觉核验通过；
6. 项目进度文档准确区分设计批准、代码迁移和运行证据。

在这些条件完成前，准确表述是“GP22 已批准并具备可追溯设计源，React 迁移尚未完成”。
