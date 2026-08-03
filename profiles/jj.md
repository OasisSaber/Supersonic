# jj Profile：发布事务确认与验证

> 本文件规定 Jujutsu 下发布事务的准备与验证方式，是 `core/policy.md` 的
> profile 层。发布事务的远端写入（创建并 push tag、创建 Release）以
> [profiles/git.md](git.md) 为准；jj 侧负责确认候选 change 对应的 Git
> commit、检查远端状态、固定精确 SHA 与发布后验证。
>
> `v1` 兼容线已冻结：tag-only 发布不推进稳定 bookmark、不执行 @v1 smoke、
> 不要求 v1 与候选对齐。

## 职责

- 确认候选 change 对应的 Git commit 等于最新 `origin/main`；
- 检查远端状态与 tag 对应 commit；
- 禁止通过含糊 revision 创建发布；
- 发布前固定精确 commit SHA；
- 发布后验证 tag 和 Release 对齐（不涉及 v1）。

## 阶段 A：发布前检查（只读）

```bash
jj git fetch --remote origin

# 1. 候选 change → 精确 Git commit，并确认其等于最新 origin/main：
#    禁止用 @、main、工作副本等含糊 revision 作为发布候选
jj log -r <candidate-change> --no-graph -T 'commit_id'
git ls-remote origin "refs/heads/main"

# 2. 本地 tag 与远端 tag
jj tag list
git ls-remote --tags origin

# 3. 候选 commit 存在于远端
git ls-remote origin | grep "<candidate-sha>"
```

发布前必须把候选解析并固定为完整 commit SHA（必须等于最新 `origin/main`），
写入最终发布审核（`profiles/git.md` 的 `APPROVED_CANDIDATE_SHA`）；任何
含糊 revision（`@`、`main`、change ID 前缀）都不得出现在审核中作为发布
目标。tag-only 发布不需要记录稳定分支 SHA。

## 阶段 C：执行（jj 侧）

jj 侧不承担远端发布写入；创建并 push tag、创建 Release 使用
`profiles/git.md` 的命令。若审核已批准使用 jj 本地 tag 工具：

```bash
# 本地 tag 已存在即停止（jj tag set 会静默移动已存在的 tag，
# 与"禁止覆盖现有 tag"冲突；存在时由人类判断，不自行移动）
jj tag list "$TAG" 2>/dev/null | grep -q . \
  && { echo "tag already exists locally: $TAG" >&2 && exit 1; } || true
jj tag set "$TAG" -r <candidate-sha>
```

远端 tag 的 push 仍通过 Git 完成：

```bash
git push origin "$TAG"
```

## 阶段 D：发布后验证

```bash
jj git fetch --remote origin

# 1. tag 指向候选 commit（annotated tag 需用 peeled 引用取 commit SHA，
#    完整命令见 profiles/git.md 阶段 D）
jj tag list
git ls-remote --tags origin "refs/tags/$TAG^{}"

# 2. Release 状态（tagName == $TAG 且已发布非 Draft；不要求
#    targetCommitish == 候选，对齐以 peeled SHA 为准）
gh release view "$TAG" --json tagName,isDraft,isPrerelease

# 3. 候选 commit 存在且可解析
jj log -r <candidate-sha> --no-graph -T 'commit_id'
```

必须确认：

- tag 的 peeled commit SHA 等于候选 commit（见 [profiles/git.md](git.md) 阶段 D）；
- Release 的 `tagName` 等于 tag 且 `isDraft == false`；
- 不存在意外 tag 或额外修改；
- `v1` 兼容线保持冻结（不参与本发布验证）。

任何差异都构成停止条件：停止并重新提交审核，不猜测、不重试、不掩盖。

## 禁止

- 用含糊 revision（`@`、`main`、change ID 前缀）创建发布；
- 未固定候选 commit SHA 就请求发布授权；
- 跳过发布后验证；
- 推进或移动稳定 bookmark（`v1` 兼容线冻结；需要强推时按
  `core/policy.md` 停止并重新审核）。
