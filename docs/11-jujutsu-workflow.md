# Jujutsu 项目管理工作流

## 仓库形态

本项目使用 Jujutsu（`jj`）作为主要版本管理界面，并采用 colocated Git 后端：

```text
<PROJECT_ROOT>/
├── .jj/       # Jujutsu 操作日志、工作区与变更信息
├── .git/      # Git 兼容层，供 GitHub 和现有工具使用
└── 项目文件
```

日常变更使用 `jj` 命令。Git 命令尽量只用于只读检查或兼容性操作，避免 Git 与 Jujutsu 同时改写分支状态。

## Jujutsu 与 Git 的关键区别

- 工作区本身始终对应一个可修改的 change，不需要 `git add`；
- `jj status` 或其他命令会自动快照工作区；
- 用 `jj describe` 给当前 change 命名；
- 用 `jj new` 结束当前 change 并开始下一项工作；
- 用 `jj squash`、`jj split` 和 `jj rebase` 整理历史；
- 用 `jj undo` 撤销最近一次仓库操作，用 `jj op log` 查找更早状态；
- Git 的 branch 在 Jujutsu 中对应 bookmark。

## 推荐的毕业设计节奏

每个 change 只承载一个可说明、可验证的任务：

```powershell
# 1. 查看当前工作
jj status
jj diff

# 2. 给当前 change 写可读名称：任务编号 + 一句话结果
jj describe -m "feat(GP05-IMPL-02): 建立座舱权威状态"

# 3. 修改并运行验证
pnpm check

# 4. 开始下一项工作
jj new
```

推荐描述前缀：

| 前缀 | 用途 |
| --- | --- |
| `design:` | Figma、视觉规范、交互原型 |
| `feat:` | 新的运行时功能 |
| `fix:` | 缺陷修复 |
| `docs:` | 报告、调研和设计文档 |
| `data:` | Profile、场景与演示数据 |
| `chore:` | 环境、依赖和工程配置 |

## 人类可读命名

Jujutsu 会自动生成 `qyypnkok` 一类 change ID。它是不可修改的内部追溯标识，不是任务名称，也不应单独出现在面向人的工作流摘要中。

- 主名称使用合同中的中文 `title`，例如“建立 GP05 FastAPI 权威座舱状态与 WebSocket 快照通道”；
- 稳定短编号使用 `GP05-IMPL-02`，用于命令、文件名和确认操作；
- change 描述使用 `<类型>(<任务编号>): <可读结果>`；
- bookmark 使用小写语义名，例如 `gp05-impl-02-authoritative-state`；
- change ID 和 commit ID 仅放入“技术详情”“锁定基线”或审计记录，不充当标题。

历史 change ID 不做改写。已推送的历史 bookmark 也不直接删除；建立语义化 bookmark 后，在获得明确 push 授权时再迁移远程引用。

## 并行探索

当两种界面方案需要并行比较时，不必复制整个项目目录：

```powershell
# 从当前父提交创建两个方案
jj new @- -m "design: explore minimal cluster"
jj bookmark create cluster-minimal -r @

jj new @-- -m "design: explore performance cluster"
jj bookmark create cluster-performance -r @

# 查看两条方案线
jj log
```

确定方案后可用 `jj abandon` 放弃无效 change，或用 `jj squash` 将有效内容整理进目标 change。操作前后都可以通过 `jj op log` 与 `jj undo` 恢复。

## GitHub 同步（建立远程后使用）

```powershell
jj git remote add origin <repository-url>
jj git fetch

# 首次为稳定基线建立 main bookmark
jj bookmark create main -r @-
jj git push --bookmark main
```

不要直接推送仍在频繁修改的空工作区 change。先运行 `pnpm check`，再把稳定 change 指向 bookmark。

## 大文件策略

Jujutsu 当前不支持 Git LFS，因此：

- 可重新下载的演示视频不纳入历史，并在 `SOURCE.md` 记录来源；
- 学校要求、报告与小型 PDF 可以纳入历史；
- 三维模型、视频、数据集和构建产物放在忽略目录或外部素材归档；
- 不要为了追踪一个大型素材而无限提高 `snapshot.max-new-file-size`。

当前仓库只将上限提高到 5 MiB，用于保存学校 PDF，不追踪约 20 MiB 的行车视频。

## 常用恢复命令

```powershell
jj undo                 # 撤销最近一次 jj 操作
jj op log               # 查看所有仓库操作
jj op show <operation>  # 检查某次操作
jj restore <path>       # 恢复文件内容
jj abandon <change>     # 放弃指定 change
```

不要把 `git reset --hard` 作为日常回退方式；Jujutsu 的 operation log 能更完整地保留操作历史。
