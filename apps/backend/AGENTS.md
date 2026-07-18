# Backend rules

本目录实现 HMI 母系统运行时。除根部 `AGENTS.md` 外，遵循以下规则：

- 使用 Python 3.11、FastAPI、Pydantic和uv；类型明确，单行不超过100字符。
- 后端维护唯一可信的车辆状态、场景和Profile；前端只消费和呈现。
- HTTP用于命令和资源，WebSocket用于持续状态广播。
- Mock、API和未来外部车辆数据适配器必须共享稳定的领域模型。
- API Key只从环境变量读取；日志中不得输出密钥、完整用户输入或私人素材路径。
- 新端点、状态转换和风险规则必须配套pytest覆盖。
- 早期场景配置可使用 JSON；MySQL 只持久化演示会话、风险事件和跨屏交互审计，不作为实时状态源。

验证：

```powershell
pnpm lint:backend
pnpm test:backend
pnpm smoke
```
