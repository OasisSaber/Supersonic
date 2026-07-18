# Agent dashboard rules

本目录是开发工作流的本地只读仪表板，不属于最终汽车 HMI 产品界面。

- 第一版只使用 Node.js 内置模块和原生 HTML/CSS/JavaScript，不新增运行时依赖。
- 服务只绑定 `127.0.0.1`，默认端口 `4174`；不得监听公网地址。
- 页面数据来自 `orchestration/` 下的结构化文件，不修改任务状态，不执行 Agent。
- API 只返回仪表板需要的字段，不暴露环境变量、凭据、原始模型日志或任意文件内容。
- 文件缺失或 JSON 损坏时提供可理解的降级信息，不能让整个页面崩溃。
- 禁止使用外部 CDN、远程字体、跟踪脚本和网络素材。
- 为状态读取、异常降级和 HTTP API 添加 Node 测试。

验证：

```powershell
pnpm --filter @cockpit/agent-dashboard check
```
