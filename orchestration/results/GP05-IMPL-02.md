# GP05-IMPL-02 执行回执

- 任务名称：建立 GP05 FastAPI 权威座舱状态与 WebSocket 快照通道
- 状态：`COMPLETE`
- authority：`CODEX_ONLY`
- executor：`codex`
- 版本名称：`gp05-impl-02-authoritative-state`
- 技术追溯：change `qyypnkok`，commit `ace5ad98`
- 锁定基线：`gp05-impl-01-design-code-contracts`（change `lkqvsuzu` / commit `39381db2af79f316a7abb939de081b78301cb0ed`）
- 合同哈希：`237062c4e2aea6f55ffdc4e1687544f4e3b1adecb67c24298fe07b30f8197efb`

## 完成内容

- 新增 `CockpitStateAuthority`，由 FastAPI 进程维护唯一 `CockpitSnapshotV1`。
- revision 在状态改变、端点首次连接/最后断开及会话重置时单调递增；幂等命令不增加 revision。
- 新增 `GET /api/v1/snapshot` 与 `POST /api/v1/commands`。
- command 严格校验来源、端点权限、支持范围和参数；错误以稳定 `error.code` 返回且不改变状态。
- 本阶段实现 `set_theme`、`set_system_mode`、`reset_session`；其他已保留命令返回 `command_not_implemented`。
- 新增 `/ws/v1/cockpit?endpoint=...`，连接和重连立即获得最新完整 snapshot。
- WebSocket 连接按逻辑端点计数；慢消费者队列上限为 1，只保留最新完整 snapshot。
- 保留全部旧 HTTP API 与 `/ws/simulation` 行为。

## 验证

- Ruff：通过。
- 后端 pytest：`20/20` 通过。
- 前端 ESLint：通过。
- 前端 Vitest：`7/7` 通过。
- TypeScript：app 与 node 配置均通过无输出类型检查。
- Vite production build：通过，输出写入隔离临时目录后已清理。
- 编排测试：`25/25` 通过。
- `pnpm check` 包装进程在当前受限沙箱中两次无子任务输出并挂起；已逐项运行其全部组成检查，结果全部通过。
- `pnpm smoke` 未计入通过：该脚本要求已有本地服务监听，当前未启动服务，因此连接失败；合同不要求启动长期服务。
- 非阻断 warning：FastAPI TestClient 提示未来迁移 `httpx2`。

## 范围审计

- 未新增依赖、API Key、地图、MySQL、Vision、Web3D、风险持久化或前端迁移。
- 未修改旧 `models.py`、`risk_engine.py`、前端源码、包清单或 lockfile。
- 本轮临时 build 与 TypeScript 缓存文件已删除。
- 当前 change 栈已按 Oasis 授权推送；远程历史引用为 `push-qyypnkokxvkp`，本地可读版本名称为 `gp05-impl-02-authoritative-state`。未创建 PR，未发布。
