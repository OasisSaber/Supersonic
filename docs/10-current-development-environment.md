# 当前开发环境与系统分工

## 一句话结论

Figma 不是运行时前端，而是界面设计、组件规范和交互原型的设计源文件。真正运行的前端由 React + TypeScript 实现；后端由 FastAPI + Python 实现。

## 最终程序链路

```text
Figma 设计系统 / 四屏稿 / Prototype
                 ↓ 设计 Token、图标、图片、尺寸与交互说明
React + TypeScript + Three.js/R3F + ECharts
                 ↕ WebSocket / HTTP
FastAPI + Python HMI Runtime
                 ↓
车辆状态模拟器 / 场景控制 / Profile 管理 / JSON 或 SQLite
```

## 各层职责

### Figma：设计源文件

- 建立颜色、字体、间距、圆角、阴影和动效规范；
- 建立可复用组件及状态 Variant；
- 设计主驾驶仪表、HUD、中控屏和副驾驶屏；
- 制作关键流程原型并交付标注与素材。

Figma 不处理车辆数据、不运行 Three.js，也不承担四屏实时通信。

### React 前端：四个可运行屏幕端点

- 将 Figma 组件实现为 React 组件；
- 使用 CSS Variables / TypeScript Token 对齐 Figma Variables；
- 用 React Three Fiber 展示三维车辆与场景；
- 用 ECharts 展示能耗、行程和车辆数据；
- 接收后端状态并让四个屏幕同步更新。

### FastAPI 后端：HMI 母系统运行时

- 维护唯一可信的车辆状态；
- 模拟车速、电量、挡位、灯光、车门、导航与告警；
- 管理 Executive SUV、Business Van、Performance Car、Track Mode 等 Profile；
- 编排普通驾驶、商务行程、性能驾驶与异常降级场景；
- 通过 WebSocket 广播状态，通过 HTTP 提供控制接口；
- 必要时用 SQLite 保存用户设置、行程与场景记录。

早期不必安装 MQTT、CAN、CARLA、ROS2 或 Docker。只有当教师要求展示工业通信或外部仿真接入时，再在 FastAPI 外增加适配器。

## 当前已准备的软件与依赖

- Node.js 24 LTS；
- pnpm 11.7.0；
- Python 3.11（项目本地运行时）与 uv；
- FastAPI 后端工程；
- React 19 + TypeScript + Vite；
- Three.js + React Three Fiber + Drei；
- ECharts、Framer Motion、Zustand；
- FFmpeg 8.1.2；
- Figma Desktop；
- Git、VS Code。

## 数据存储的选择

第一阶段优先使用 JSON：车型 Profile、主题与演示场景都便于阅读、版本管理和调整。需要保存用户设置、行程历史或测试记录时，再加入 SQLite。数据库不是开工前提。

## 推荐的首个技术闭环

1. 在 Figma 完成一个速度组件及其 Normal、Warning、Critical 三种状态；
2. 在 React 中实现同名组件并绑定设计 Token；
3. FastAPI 每 100–200 ms 推送一次模拟车速；
4. 仪表与 HUD 同时显示该状态，但采用各自的信息层级；
5. 用场景控制台切换状态，验证四屏共享一个数据源。

这个闭环验证成功后，再扩展整套页面和多车型 Profile。
