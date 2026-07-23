# 验证脚本

`bash scripts/validate.sh` 是仓库的统一验证入口。它先运行 Markdown 链接校验器单元测试，再检查 Git 跟踪的 Markdown 本地链接、YAML 语法、Shell 语法与可执行位，然后运行不降级的 `pnpm check`。Markdown 校验覆盖 inline/image/reference/HTML 链接、括号和 URL 编码路径、query/fragment，并跳过代码块、行内代码和 HTML 注释。

脚本不默认运行 `pnpm smoke`：该检查需要运行中的 FastAPI，且现有 mock HTTP/WebSocket 链不能作为 GP05 核心四屏链路的证明。运行态、跨层或明确要求的任务应单独执行 smoke。

脚本需要 Bash、Python、PyYAML、pnpm 和项目依赖。Windows 本地请在 Git Bash 或 WSL 中执行；GitHub Actions 已提供相同环境。
