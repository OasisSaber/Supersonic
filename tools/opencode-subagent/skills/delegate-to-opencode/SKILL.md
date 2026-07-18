---
name: delegate-to-opencode
description: Initialize and operate a controlled local OpenCode worker for any Jujutsu-backed repository. Use when the user asks Codex to use OpenCode as a subagent, delegate a bounded coding task to OpenCode, install or enable the OpenCode collaboration workflow in another project, monitor a delegated task, recover an interrupted OpenCode run, or review and accept its result.
---

# Delegate to OpenCode

Use the bundled CLI for deterministic state changes. Resolve `scripts/cli.mjs` relative to this `SKILL.md`; pass the target repository with `--root=<absolute-path>` when the current directory is elsewhere.

## Establish the project

1. Read the repository's `AGENTS.md` files and ownership/handoff state before making changes.
2. Run the repository's Jujutsu status and recent log. Stop on another owner's lease or overlapping work.
3. If `.opencode-subagent/config.json` is absent, run:

   `node scripts/cli.mjs init --root=<repo> --identity=<user> --model=<provider/model>`

4. Run `node scripts/cli.mjs doctor --root=<repo>`. Resolve missing Jujutsu, OpenCode, provider authentication, or model availability before creating a live task.

Initialization writes only `.opencode-subagent/`. Its `runtime/` is ignored; drafts, sealed contracts, and result receipts remain reviewable project artifacts.

## Plan a delegation

Delegate only a concrete, low-risk implementation that can be described with explicit inputs, writable paths, budgets, and deterministic verification. Keep architecture, agent policy, credentials, dependency manifests, CI/release configuration, integration, pushing, and ambiguous/high-risk work with Codex.

Read [contract-reference.md](references/contract-reference.md) before authoring or reviewing a contract.

1. Run `node scripts/cli.mjs new TASK-ID --title="..." --root=<repo>`.
2. Edit `.opencode-subagent/drafts/TASK-ID.json`. Replace every placeholder and keep the result receipt inside `scope.allowedPaths`.
3. Run `node scripts/cli.mjs doctor TASK-ID --root=<repo>` so every contract verification executable is resolved before approval. Use `verificationBinaries` in project config only for explicit trusted path overrides.
4. Freeze the intended project base in Jujutsu and leave a new working-copy change for the sealed task metadata. The default approval base is `@-`; never pin a mutable working-copy commit.
5. Show the user one approval summary containing the outcome, scope, model, budgets, verification, frozen base revision, external data categories, automatic local actions, and exclusions.
6. Ask for exactly one decision: `APPROVE TASK-ID`. Make clear that this authorizes one execution of the sealed contract, external sharing of the listed task context, automatic Codex review/takeover, and local integration after verification. It never authorizes push, publication, a wider scope, a different model, or more budget.

After that single explicit approval, run:

`node scripts/cli.mjs approve TASK-ID --confirm=TASK-ID --base=@- --run --ack-external-data-sharing --root=<repo>`

The command seals the contract, records the bounded grants, prepares the runtime, consumes one dispatch authorization, and starts the supervisor. Do not ask the user for separate `DISPATCH`, external-data, `ACCEPT`, `TAKEOVER`, or `INTEGRATE` decisions for that exact contract.

## Dispatch and monitor

Poll with `status`; use `audit` if the supervisor appears stale.

The detached supervisor owns the worker lifecycle. Do not launch OpenCode directly in the main checkout. It creates a sparse Jujutsu workspace, injects a read-only sealed contract, passes the actual requirements and writable paths to OpenCode, denies shell/web/external-directory/subagent access, meters usage with pre-turn headroom, audits changed paths, runs independently resolved verification commands, and hands the preserved result to `AWAITING_CODEX_REVIEW`.

If interrupted, budget-limited, or verification fails, inspect the preserved workspace as Codex first. Repair or take over within the approved contract when possible. Ask again only if completion requires a changed contract, model, budget, data-sharing category, or permission boundary.

## Review the result

At `AWAITING_CODEX_REVIEW`, inspect the task workspace diff, result receipt, changed-path audit, budget record, and verifier output. Codex owns this review and any in-contract repair. After independent verification passes, record:

`node scripts/cli.mjs review TASK-ID --confirm=TASK-ID --verdict=pass --root=<repo>`

Perform the repository's Jujutsu-only local integration procedure, verify the integrated revision, then record:

`node scripts/cli.mjs integrate TASK-ID --confirm=TASK-ID --revision=<integrated-jj-revision> --root=<repo>`

Do not turn these internal bookkeeping commands into new user gates. Report the final result and evidence. Push, PR creation, release, publication, and any expansion of the sealed contract still require explicit new authorization.

Legacy manually gated contracts remain readable and controllable with `prepare`, `dispatch`, `start`, `accept`, `return`, `takeover`, and `cancel`; do not use that mode for new tasks unless the user specifically requests staged approvals.
