# Backend rules

本目录实现 HMI 母系统运行时。除根部 `AGENTS.md` 外，遵循以下规则：

- 使用 Python 3.11、FastAPI、Pydantic 和 uv；类型明确，单行不超过 100 字符；
- 后端维护唯一可信的车辆、导航、风险、乘客、场景和 Profile 状态，前端只消费和呈现；
- HTTP 用于命令和资源，WebSocket 用于持续全量 snapshot 广播；
- Mock 与未来真实适配器必须共享稳定领域模型，并明确标记数据来源；
- 端点权限最终由服务端拥有的请求或连接上下文确定，不能只信任请求体中的 endpoint/source 字段；
- API Key 只从环境变量读取，日志中不得输出密钥、能力值、完整用户输入或私人素材路径；
- 新端点、状态转换和风险规则必须配套 pytest 覆盖；
- 早期场景配置可使用 JSON；持久化只有独立 Issue 触发后才加入，且不作为实时状态源；
- 地图、Vision、Web3D、AI 或数据库不可用时，核心 HMI 必须保持明确的 Mock/降级路径；
- 不为本地单用户原型引入通用账户系统、多租户、高可用或公共云安全平台。

验证：

```powershell
pnpm lint:backend
pnpm test:backend
```

涉及真实运行链时，运行与任务对应的 Smoke。当前 `pnpm smoke` 执行 `gp05.v1` 四端点真实进程链路；旧链路仅通过 `pnpm smoke:legacy` 显式运行。