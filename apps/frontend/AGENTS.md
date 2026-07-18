# Frontend rules

本目录实现可运行的 HMI 屏幕端点。除根部 `AGENTS.md` 外，遵循以下规则：

- 使用 React 19、TypeScript strict、Vite、Zustand、ECharts、Three.js / React Three Fiber。
- 业务组件放在 `src/components/`；共享状态放在 `src/stores/`；外部通信和适配逻辑放在 `src/lib/`。
- 禁止在组件中复制后端权威车辆状态；组件通过Store或明确的props读取状态。
- 将Figma Variables映射为集中Token或CSS Variables，保持四屏一致。
- Web3D必须懒加载；不能阻塞关键驾驶信息，也必须提供静态或低性能降级表现。
- 动效必须尊重信息优先级，告警不能只依赖颜色表达。
- 修改行为时补充或更新Vitest/Testing Library测试。
- 提交前删除生成的 `*.tsbuildinfo`、`vite.config.js`、`vite.config.d.ts`，这些文件不属于源码。

验证：

```powershell
pnpm --filter @cockpit/frontend lint
pnpm --filter @cockpit/frontend test --run
pnpm --filter @cockpit/frontend build
```
