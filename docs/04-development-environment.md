# 开发环境

## 当前检查结果（2026-07-15）

| 项目 | 当前状态 | 说明 |
|---|---|---|
| 操作系统 | Windows NT 10.0.26200.0，x64 | 当前开发主机 |
| CPU | 20逻辑处理器 | 未能读取精确型号，不影响开发 |
| 内存 | 约32 GB | 满足Mock和基础视觉推理开发 |
| GPU | NVIDIA GeForce RTX 4070 Laptop，8 GB | 驱动610.74，CUDA UMD 13.3；当前不安装CUDA工具包 |
| Node.js | 24.17.0（Krypton LTS） | 可运行；该版本线已进入LTS，符合项目要求（状态以Node.js官方发布页为准） |
| pnpm | 11.7.0 | 已安装，已生成锁文件 |
| Python | 项目本地CPython 3.11.15 | 位于`apps/backend/.venv`，由uv管理 |
| uv | 0.11.23 | 已安装 |
| Git | 2.54.0 | 已安装；当前`.git`目录不是有效仓库 |
| FFmpeg | 未安装/未加入PATH | Mock模式不依赖；真实视频阶段再安装 |

Node.js版本状态参考：[Node.js Releases](https://nodejs.org/en/about/previous-releases)。

## 安装

Windows：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

macOS/Linux：

```bash
sh scripts/setup.sh
```

安装脚本把Python、虚拟环境、uv缓存和pnpm依赖保留在项目目录，不修改全局Python和CUDA。

## 启动

```bash
pnpm dev
```

- HMI：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8000`
- API文档：`http://127.0.0.1:8000/docs`

单独启动：

```bash
pnpm dev:backend
pnpm --filter @cockpit/frontend dev
```

## 依赖分层

- 当前必需：FastAPI、Pydantic、Uvicorn、React、Vite、ECharts、Zustand；
- 开发测试：pytest、Ruff、Vitest、ESLint；
- 后续视觉可选：OpenCV、MediaPipe、Ultralytics YOLO；
- 后续语音可选：FFmpeg、ASR、TTS；
- 后续LLM可选：OpenAI兼容客户端。

视觉依赖已经写入`apps/backend/pyproject.toml`的`vision`可选组，确认数据和模型许可后再执行：

```bash
uv --cache-dir .uv-cache sync --project apps/backend --extra vision
```

## CPU与GPU方案

默认CPU：Mock事件或小尺寸视频，优先保证功能正确和离线演示。

可选GPU：确认PyTorch版本与显卡驱动兼容后，在项目虚拟环境中安装对应构建。不要按`nvidia-smi`显示的最高CUDA版本盲装系统工具包。GPU仅用于加速视觉推理，系统逻辑不能依赖GPU才能运行。

## Mock模式

无需模型、视频和LLM密钥。事件来自`demo-data/mock/events.json`，车辆状态由后端模拟。`.env.example`中的`APP_MODE=mock`为默认值。

## 常见故障

| 现象 | 处理 |
|---|---|
| `uv`缓存拒绝访问 | 命令加`--cache-dir .uv-cache`，安装脚本已处理 |
| pnpm阻止esbuild脚本 | 运行`pnpm approve-builds esbuild` |
| 前端显示“正在连接后端” | 检查8000端口、后端日志和`VITE_WS_URL` |
| 端口被占用 | 关闭旧进程，或同时修改脚本和前端环境变量 |
| 中文乱码 | 所有文本使用UTF-8；不要用旧版ANSI编辑器保存 |
| 无FFmpeg | 继续使用Mock；真实视频阶段再安装并运行检查脚本 |
| GPU不可用/显存不足 | 切换CPU、小模型、降低分辨率和采样率 |

## 平台差异

- Windows脚本使用PowerShell；macOS/Linux使用Shell；
- 摄像头设备编号和权限因平台不同，需要单独配置；
- FFmpeg安装方式不同，但调用接口保持一致；
- 路径处理使用跨平台库，不在代码中写死盘符；
- 展演版本优先冻结到实际展示用Windows电脑并做离线验证。
