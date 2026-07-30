# Frontend rules

本目录实现可运行的 HMI 屏幕端点。除根部 `AGENTS.md` 外，遵循以下规则：

- 核心栈为 React 19、TypeScript strict、Vite 和 Zustand；
- ECharts、Three.js 和 React Three Fiber 是按明确需求使用的可选展示工具，不是每个端点或核心闭环的硬依赖；
- 业务组件放在 `src/components/`，共享状态放在 `src/stores/`，外部通信和适配逻辑放在 `src/lib/`；
- 禁止在组件中复制后端权威车辆状态，组件通过 Store 或明确 props 读取状态；
- 将 Figma Variables 映射为集中 Token 或 CSS Variables，保持四屏一致；
- Overview 必须严格只读，不实例化命令 Hook 或可发送业务命令的控件；
- Control 必须通过 FastAPI command 修改业务状态，不直接写 Store；
- 外部 HTTP/WebSocket 数据必须通过运行时校验后才能进入 Store；
- Web3D 若实施必须懒加载，不能阻塞关键驾驶信息，并提供静态或低性能降级；
- 动效必须尊重信息优先级，告警不能只依赖颜色表达；
- 修改行为时补充或更新 Vitest/Testing Library 测试；
- 提交前删除生成的 `*.tsbuildinfo`、`vite.config.js`、`vite.config.d.ts`，这些文件不属于源码。

验证：

```powershell
pnpm --filter @cockpit/frontend lint
pnpm --filter @cockpit/frontend test --run
pnpm --filter @cockpit/frontend build
```