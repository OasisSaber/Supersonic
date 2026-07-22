# Figma 设计到代码工作流

## Figma 文件建议结构

```text
00 Cover & Decisions
01 Foundations
02 Components
03 Cluster
04 HUD
05 Center Display
06 Passenger Display
07 Vehicle Profiles
08 Prototype Flows
09 Change Log
```

## 设计系统先行

先在 `Foundations` 中建立颜色、排版、间距、圆角、描边、阴影、透明度和动效时长等 Variables；再在 `Components` 中建立按钮、状态卡片、速度、挡位、导航指令、媒体、空调、告警等组件及 Variant。四个屏幕只组合这些组件，不分别维护四套互不相干的样式。

## 命名映射

| Figma | 代码 |
| --- | --- |
| `Color/Surface/Primary` | `--color-surface-primary` |
| `Space/16` | `--space-16` |
| `Motion/Fast` | `--motion-fast` |
| `Vehicle/Speed` | `VehicleSpeed` React 组件 |
| `Alert/Critical` Variant | `severity="critical"` 属性 |

## 每个组件的交付条件

- 有明确用途与所属屏幕；
- 有默认、交互、禁用、告警和异常状态；
- 使用 Variables，不散落临时颜色与尺寸；
- Auto Layout 与约束可适配目标屏幕；
- 标出数据字段、单位、刷新频率和空数据行为；
- 代码中存在同名组件或明确的实现任务。

## 开发循环

```text
定义场景与信息优先级
→ Figma低保真线框
→ 组件与Variables
→ 四屏高保真与Prototype
→ React组件实现
→ FastAPI模拟数据联调
→ 视觉/交互/性能核对
→ 回写设计决策与变更记录
```

不要把 Figma 自动生成的页面代码直接当作最终工程。设计稿提供结构、规范与资产，React 代码负责语义、状态、性能和可维护性。
