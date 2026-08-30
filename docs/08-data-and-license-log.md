# 数据与许可记录

> 当前仅录入一段 CC0 城市行车视频；没有录入个人测试数据或模型权重。新增材料前必须完成本表。

## 视频与数据

| 视频/数据名称 | 来源URL或提供方 | 授权方式 | 人脸/车牌 | 隐私处理 | 标注情况 | 可否公开展示 | 保存位置 | 备注 |
|---|---|---|---|---|---|---|---|---|
| Mock事件集 | 本项目自建 | 自有 | 无 | 不适用 | 规则场景标注 | 可 | `demo-data/mock/events.json` | 不代表真实检测结果 |
| Dashcam Recording (urban)，480p VP9转码 | Wikimedia Commons，作者 Fernost | CC0 1.0 Universal | 可能包含远处车辆/车牌，未见可识别人脸 | 采用480p转码并在HMI中裁切显示；正式公开前再做逐帧复核 | 无真实目标标注；界面检测框为Mock叠加 | 可，CC0允许复制、修改、分发及公开展示 | `PreDesign/demo/assets/urban-dashcam-480p.webm` | 来源与哈希见同目录`SOURCE.md`；不得表述为本项目真实检测结果 |
| 【待填写】 | 【待填写】 | 【待填写】 | 有/无 | 【模糊、裁剪、同意等】 | 【待填写】 | 是/否/仅校内 | 【待填写】 | 【待填写】 |

## 模型与权重

| 模型/权重 | 版本 | 来源 | 许可证 | 商用/展示限制 | 是否修改/训练 | 本地路径 | 引用方式 |
|---|---|---|---|---|---|---|---|
| Ultralytics YOLO（当前未采用） | 已从 `pyproject.toml` 与 `uv.lock` 移除；未来版本待定 | [Ultralytics 官方许可页](https://www.ultralytics.com/license) | AGPL-3.0 或 Enterprise/R&D 路线，重新加入前必须核验 | 当前不适用；未启用、未部署、未分发 | 不适用 | 无；不得提交权重 | 重新加入前记录准确版本、模型来源、许可文本和授权证据，并更新 `THIRD_PARTY_NOTICES.md` |
| MediaPipe（可选依赖，未安装） | 0.10.35（`uv.lock` 锁定） | Google / PyPI | Apache-2.0（上游声明；分发前必须以已安装 wheel 的 dist-info 证据复核） | 保留许可声明 | 不训练 | 未安装、未启用、未分发 | 官方文档 |
| OpenCV（opencv-python，可选依赖，未安装） | 4.13.0.92（`uv.lock` 锁定） | OpenCV / PyPI | Apache-2.0（上游声明；分发前必须以已安装 wheel 的 dist-info 证据复核） | 保留许可声明 | 不训练 | 未安装、未启用、未分发 | 官方文档 |
| OpenAI 客户端库（可选依赖，未安装） | 1.109.1（`uv.lock` 锁定） | OpenAI / PyPI | MIT（上游声明；分发前必须以已安装 wheel 的 dist-info 证据复核） | 调用外部 LLM 服务时另行遵守服务条款 | 不训练 | 未安装、未启用、未分发；不提交密钥和用户敏感信息 | 官方文档 |

## 依赖与许可溯源

> 本节与 `apps/backend/pyproject.toml`、`apps/backend/uv.lock` 以及
> [G5 依赖清单](../deliverables/g5-review/G5_DEPENDENCY_INVENTORY.md) 保持同步；版本为锁文件
> 解析值。许可证据取自本地安装包 `*.dist-info` 元数据（`License` / `License-Expression` /
> classifier）与捆绑的 `licenses/` 文本；许可声明全文归类见 `THIRD_PARTY_NOTICES.md`。

### 运行时直接依赖（随本地后端运行时分发）

| 包 | 锁定版本 | 来源 | 许可证 | 许可证据 | 分发状态 |
|---|---|---|---|---|---|
| alembic | 1.18.5 | PyPI | MIT | 安装包 `License-Expression: MIT` + dist-info `licenses/` | 随本地运行时分发 |
| fastapi | 0.139.0 | PyPI | MIT | 安装包 `License-Expression: MIT` + dist-info `licenses/` | 随本地运行时分发 |
| pydantic | 2.13.4 | PyPI | MIT | 安装包 `License-Expression: MIT` + dist-info `licenses/` | 随本地运行时分发 |
| psycopg[binary] | 3.3.4 | PyPI | LGPL-3.0-only | 安装包 `License-Expression: LGPL-3.0-only` + dist-info `licenses/` | 随本地运行时分发；使用未修改的官方 wheel；任何再分发前必须复核 LGPL-3.0 义务（见 `THIRD_PARTY_NOTICES.md`） |
| python-dotenv | 1.2.2 | PyPI | BSD-3-Clause | 安装包 `License: BSD-3-Clause` 字段 + dist-info `licenses/` | 随本地运行时分发 |
| SQLAlchemy | 2.0.51 | PyPI | MIT | 安装包 `License: MIT` 字段 + dist-info `licenses/` | 随本地运行时分发 |
| uvicorn[standard] | 0.51.0 | PyPI | BSD-3-Clause | 安装包 `License-Expression: BSD-3-Clause` + dist-info `licenses/` | 随本地运行时分发 |
| pwdlib[argon2] | 0.3.0 | PyPI | MIT | 捆绑 `dist-info/licenses/LICENSE`（MIT 全文见 `THIRD_PARTY_NOTICES.md`）；安装元数据的 `License` / `License-Expression` 字段未声明，仅 `Classifier: License :: OSI Approved :: MIT License` | 随本地运行时分发 |

### 开发依赖（不随任何运行时或交付物分发）

| 包 | 锁定版本 | 许可证 | 许可证据 |
|---|---|---|---|
| httpx | 0.28.1 | BSD-3-Clause | 安装包 `License` 字段 + MIT/BSD classifier |
| pytest | 8.4.2 | MIT | 安装包 `License` 字段 + MIT classifier |
| pytest-asyncio | 1.4.0 | Apache-2.0 | 安装包 `License-Expression: Apache-2.0` |
| ruff | 0.15.21 | MIT | 安装包 `License-Expression: MIT` |

### 可选依赖（已声明并锁定；当前未安装、未启用、未分发）

| 包 | 锁定版本 | 上游声明许可 | 分发状态与启用前置条件 |
|---|---|---|---|
| opencv-python（`vision` extra） | 4.13.0.92 | Apache-2.0 | 未安装、未启用、未分发；启用或分发前必须以已安装 wheel 的 dist-info 许可证据复核，并更新本表与 `THIRD_PARTY_NOTICES.md` |
| mediapipe（`vision` extra） | 0.10.35 | Apache-2.0 | 同上 |
| openai（`llm` extra） | 1.109.1 | MIT | 客户端库未安装、未启用、未分发；调用外部 LLM 服务时另行遵守服务条款，不提交密钥 |

### 前端与工具链依赖

前端直接依赖逐项记录在 [G5 依赖清单](../deliverables/g5-review/G5_DEPENDENCY_INVENTORY.md)；
版本与完整性由 `pnpm-lock.yaml` 固定，本表不重复。

## 数据治理检查

- [ ] 已获得使用和展示授权；
- [ ] 已确认是否包含人脸、车牌、位置或声音；
- [ ] 已完成最小化、脱敏和保存期限说明；
- [ ] 用户测试已取得知情同意；
- [ ] 数据和权重未提交Git；
- [ ] 论文和展板标明来源；
- [ ] 离线演示包不包含无权公开的数据。
