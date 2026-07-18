# Task contract reference

Use schema version 2. A sealed task is immutable; revisions require a new task ID or contract version.

## Required fields

- `id`: 3–64 uppercase letters, digits, underscores, or hyphens.
- `title`: one bounded outcome.
- `lifecycle`: `DRAFT` before approval; the CLI changes it to `ACTIVE`.
- `riskLevel`: only `L0` or `L1` is delegatable.
- `authority`: `DELEGATABLE`.
- `executor`: `opencode`.
- `model`: an installed `provider/model` listed by OpenCode.
- `base`: populated and locked by `approve`; never hand-fill it.
- `approval`: `PENDING` in a draft; sealed by `approve` with identity, timestamp, and hash.
- `budget`: numeric runtime minutes, input/output tokens, cost, and correction cycles.
- `scope.inputPaths`: the smallest read context needed for the task.
- `scope.allowedPaths`: the complete writable set, including `resultPath`.
- `requirements`: outcome and non-goals phrased so a verifier can assess them.
- `verificationCommands`: structured executable, argument array, and positive timeout. Avoid shell strings, pipes, redirection, and environment mutation.
- `resultPath`: a concise execution and verification receipt written by OpenCode.

## Protected work

The CLI rejects overlap with agent policy, `.opencode-subagent/**`, `.codex/**`, OpenCode configuration, dependency manifests and lockfiles, CI configuration, and repository-level `AGENTS.md`. A project may add more `protectedPaths` in `.opencode-subagent/config.json`.

Do not delegate credentials, security-sensitive changes, release/push actions, architecture ownership, dependency changes, or work without deterministic acceptance evidence.

Before approval, run `doctor TASK-ID`. Every verification command must be both present in `verificationExecutables` and resolvable on the current machine. If PATH discovery is insufficient, map an approved name to a trusted absolute or project-relative path in `verificationBinaries`; never place command arguments or shell fragments in that map.

## Authorization model

New tasks use one bounded user approval. `approve --run --ack-external-data-sharing` seals the exact contract and base and records grants for one dispatch, the listed external data sharing, Codex review/takeover, and verified local integration. The runtime preserves `pushAuthorized: false`.

The approval does not cover a changed task version, expanded paths, a different model, more budget, additional external data, push, PR creation, release, or publication. Those require a new explicit authorization. Codex review and local integration bookkeeping are internal actions under the original grant and must not be presented as additional user gates.

Legacy manual mode retains `approve`, `prepare`, `dispatch`, `start`, and `accept`/`return`/`takeover`/`cancel` as separate commands for recovery and compatibility. Use it only when the user explicitly requests staged approvals.
