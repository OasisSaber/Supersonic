# Apple 设计资产引入评估（D:\Project\Asset）

- 研究日期：2026-08-02
- 研究对象：`D:\Project\Asset` 下的 Apple 设计资产归档与项目自有设计交付物
  - `apple-design-archive/`：HIG 全文（171 个章节 JSON）、SF Symbols 8、SF Pro/SF Mono/NY 等字体、iOS 27 图标模板、tvOS 18/visionOS 2 模板、Bezel 设备外壳、Glyph/Icon/Logo 素材、Figma/Sketch 云端库链接
  - `GP22.fig`、`Visual Design Specification Plan.make/.zip`：本项目自有设计源（与 Apple 无关）
- 方法：只使用 Apple 官方一手来源核验许可（developer.apple.com 页面内嵌许可全文、SF-Symbols-8.dmg 包内官方 License.rtf、Design Resources 页面条款）；对照本项目设计基线（`docs/design/GP22_SOURCE_MANIFEST.md`、`PreDesign/01-设计依据与原则.md`、`PreDesign/04-组件与内容规范.md`、`apps/frontend/package.json`）评估匹配度。
- 目的：判断该归档中的 Apple 设计资产是否适合引入本项目，以及存在哪些版权风险。

## 结论摘要

**不建议引入** SF Symbols、SF 字体（SF Pro/SF Mono/NY 及变体）、Apple 平台设计模板和 Bezel/Logo 营销素材；**仅 HIG 文档适合作为设计原则的引用式参考**（本地阅读、提炼原则并注明出处，不将全文复制进仓库或随交付物分发）。

理由（许可依据见下文"许可证据"）：

1. **SF Symbols 与 SF 字体的许可明确限定"仅用于 Apple 平台应用的用户界面"**，并明文禁止用于非 Apple 操作系统、禁止嵌入软件产品、禁止向第三方分发（含素材的 mock-up 与模板）。本项目是运行在浏览器/车载设备上的汽车座舱 HMI（非 Apple 平台），且答辩与演示需要可复制、可分发的资产，直接引入即违反 Apple 许可条款。
2. 本项目**已有合规替代且无缺口**：图标使用 `lucide-react`（ISC 许可，可商用可分发）；字体策略为系统字体（`Microsoft YaHei UI` / `Noto Sans SC`），GP22 设计稿代码包（`Visual Design Specification Plan.zip`，仓库外受控交付物）CSS 使用 Inter（SIL OFL）与 Noto——均与 Apple 资产无依赖。
3. **HIG 的汽车相关章节（CarPlay）与基础原则（色彩、排版、布局、无障碍、图标）** 对本项目四屏 HMI 有真实参考价值，可作为类似 `PreDesign/01-设计依据与原则.md` 引用 Google Android Auto 原则的方式引用；但 HIG 内容是 Apple 版权作品，只能"读后提炼、注明出处"，不得把 `docs/hig/` 的 JSON/页面数据复制进仓库或随论文、答辩材料分发。
4. 模板、Bezel、Logo 等营销素材面向 Apple 平台应用开发与 Apple 产品营销场景，与本项目无关，且受 Apple 商标与营销素材指南限制。

## 一、归档内容与许可状态总览

| 资产 | 归档位置 | 许可/版权状态（官方依据） | 对本项目适用性 |
| --- | --- | --- | --- |
| HIG 全文（171 个章节 JSON） | `docs/hig/` | © Apple Inc. All rights reserved；可阅读参考，禁止整体复制分发 | **可作引用式参考**（CarPlay、typography、color、layout、accessibility、sf-symbols 章节） |
| SF Symbols 8 | `assets/sf-symbols/SF-Symbols-8.dmg`（442MB） | EA1702：仅限 Apple 平台应用 UI mock-up；禁止非 Apple 平台、禁止分发/嵌入/再包装；beta 版含保密义务 | **不引入**（许可冲突 + lucide-react 已覆盖） |
| SF Pro / SF Mono / NY / 变体字体 | `assets/fonts/`（约 388MB） | EA1370 等：仅限 Apple iOS/OS X/tvOS（Compact 限 watchOS）UI mock-up；禁止嵌入、禁止非 Apple 平台 | **不引入**（许可冲突 + 系统字体/Inter/Noto 已覆盖） |
| iOS 27 图标模板、tvOS 18、visionOS 2 模板（均为官方发布版本，年份新旧不一） | `assets/templates/`（约 66MB） | Apple 官方模板，面向 Apple 平台应用开发 | **不引入**（场景无关） |
| Bezel 设备外壳、Glyph、Icon、Logo、Keynote 素材 | `assets/marketing/`（约 1.7GB） | App Store Marketing Resources and Identity Guidelines；Apple 商标/品牌使用限制 | **不引入**（场景无关 + 商标限制） |
| Figma/Sketch 云端库链接 | `links/` | 仅为 URL 索引，无资产文件 | 无版权问题；Apple Design Resources 面向 Apple 平台设计，场景无关 |
| `GP22.fig`、`Visual Design Specification Plan.*` | 归档根目录 | 本项目自有交付物（指纹见 `docs/design/GP22_SOURCE_MANIFEST.md`） | 与 Apple 资产无关，保持现状 |

## 二、许可证据（官方一手来源）

### 1. SF 字体许可（EA1370，developer.apple.com/fonts/ 页面内嵌全文）

- "THE APPLE SAN FRANCISCO FONT IS TO BE USED SOLELY FOR CREATING MOCK-UPS OF USER INTERFACES TO BE USED IN SOFTWARE PRODUCTS RUNNING ON APPLE'S iOS, OS X OR tvOS OPERATING SYSTEMS"
- "You may not install, use or run the Apple Font for the purpose of creating mock-ups of user interfaces to be used in software products running on any non-Apple operating system"
- "You may not embed the Apple Font in any software programs or other products"
- 使用前提：注册 Apple Developer，否则需 Apple 书面许可；禁止复制、反编译、修改、衍生与未经授权再分发。

### 2. SF Symbols 许可（EA1702，2020-06-18，SF-Symbols-8.dmg 包内官方 License.rtf）

- 标题即限定："BETA SOFTWARE LICENSE AGREEMENT FOR THE APPLE SF SYMBOLS APP — For iOS, iPadOS, macOS, tvOS and watchOS application uses only"
- 2A Limited License for Symbols：仅允许"creating mock-ups of user interfaces to be used in software products running on the applicable Apple Platforms"
- 2D No Distribution of Templates and Mock-Ups：不得向第三方分发（a）模板、（b）含 Symbols 的 mock-up、（c）嵌入修改模板的软件产品
- 2E Other Use Restrictions："you agree not to install, use or run the Apple Software, Symbols or Templates for the purpose of creating mock-ups of user interfaces to be used in software products running on any non-Apple operating system"；不得嵌入；不得用于制作文档、网站内容或其他作品
- 4 Confidentiality：预发布软件视为保密信息，不得披露、发布或传播
- 5 Termination：不再注册 Apple Developer 或违反条款时许可自动终止

### 3. Design Resources 与营销素材

- `developer.apple.com/design/resources/` 对 Product Bezels 明确指引："When using product bezels in your marketing materials, be sure to review these Marketing Resources and Identity Guidelines"；Badges/Logos 走 `apple.com/licensing-trademarks/`。
- 这些素材用于"在营销材料中展示 Apple 产品界面"，本项目（汽车座舱 HMI）无此场景。

### 4. HIG 版权

- 官方页面底部统一标注 "Copyright © Apple Inc. All rights reserved. Terms of Use"。
- 设计**原则、数值与思想**不受版权保护，可学习借鉴并注明出处；**文字表达与页面数据**（如 `docs/hig/data/*.json` 的整页内容）受版权保护，不应整体复制进入本仓库或随答辩材料/论文全文分发。

## 三、对本项目的影响与建议

1. **不引入** SF Symbols / SF 字体 / Apple 模板 / Bezel/Logo 素材；保持 `lucide-react` + 系统字体/Inter/Noto 现状。理由：许可冲突（非 Apple 平台 + 禁止分发/嵌入）、场景不匹配、项目已有替代。
2. **HIG 仅作引用式参考**：如需借鉴 CarPlay 或基础章节的设计原则，按 `PreDesign/01-设计依据与原则.md` 引用 Google Android Auto 的方式，在文档中记录"来源：Apple HIG（URL/章节）"，不复制原文段落。
3. **归档位置保持外部**：`D:\Project\Asset` 是仓库外受控素材目录，符合 `AGENTS.md` "不提交密钥、私人素材"与 `docs/08-data-and-license-log.md` 的材料记录要求；无需（也不应）把任何 Apple 二进制资产提交进仓库。
4. 若未来确实需要在非 Apple 平台使用 SF Symbols/SF Pro，唯一合规路径是联系 Apple 获得书面许可（许可文本中均保留"as otherwise expressly permitted by Apple in writing"的例外），在此之前按"未获授权"处理。

## 四、已知限制与未覆盖项

- Apple 2023 年后针对"网页使用"发布过 SF 字体与 SF Symbols 的单独许可（web 版本），本次调研未能在官方页面取得该许可的完整文本（developer.apple.com/fonts/ 当前仅展示 EA1370/EA1371 等平台许可）。即便该网页许可存在，其适用对象是网站内容，而本项目是**应用软件**（且以可分发形式交付），结论不受影响；如需精确引用网页许可条款，应另行向 Apple 官方索取。
- 本评估不构成法律意见；涉及公开分发或商业使用时，建议按学校要求与专业法律意见复核。
