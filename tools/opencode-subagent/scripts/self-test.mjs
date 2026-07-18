import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createJjWorkspaceAdapter } from "../skills/delegate-to-opencode/scripts/adapters.mjs";
import { loadProjectConfig } from "../skills/delegate-to-opencode/scripts/project.mjs";

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cli = path.join(pluginRoot, "skills", "delegate-to-opencode", "scripts", "cli.mjs");
const jj = process.env.JJ_BIN;
assert.ok(jj, "Set JJ_BIN to a working Jujutsu executable");

const sandbox = await mkdtemp(path.join(tmpdir(), "opencode-subagent-plugin-"));
const repo = path.join(sandbox, "sample-project");
run(jj, ["git", "init", "--colocate", repo], sandbox);
await writeFile(path.join(repo, "AGENTS.md"), "Keep changes inside the approved task scope.\n", "utf8");
await writeFile(path.join(repo, ".gitignore"), ".agent-contract/\n", "utf8");
await writeFile(path.join(repo, "secret.txt"), "must not enter the sparse task workspace\n", "utf8");
run(jj, ["describe", "-m", "test base"], repo);
run(jj, ["status"], repo);

run(process.execPath, [cli, "init", `--root=${repo}`, "--identity=Test User", "--model=deepseek/deepseek-v4-pro"], repo);
run(process.execPath, [cli, "new", "TASK-TEST", "--title=Create a scoped test artifact", `--root=${repo}`], repo);
run(process.execPath, [cli, "new", "TASK-BAD", "--title=Reject an unresolved verifier", `--root=${repo}`], repo);
run(process.execPath, [cli, "new", "TASK-BUDGET", "--title=Hand budget stops to Codex", `--root=${repo}`], repo);

const draftPath = path.join(repo, ".opencode-subagent", "drafts", "TASK-TEST.json");
const draft = JSON.parse(await readFile(draftPath, "utf8"));
draft.scope.inputPaths = ["AGENTS.md"];
draft.scope.allowedPaths = ["work/**", ".opencode-subagent/results/TASK-TEST.md"];
draft.resultPath = ".opencode-subagent/results/TASK-TEST.md";
draft.requirements = ["Create a scoped test artifact and receipt."];
await writeFile(draftPath, `${JSON.stringify(draft, null, 2)}\n`, "utf8");

const budgetDraftPath = path.join(repo, ".opencode-subagent", "drafts", "TASK-BUDGET.json");
const budgetDraft = JSON.parse(await readFile(budgetDraftPath, "utf8"));
budgetDraft.scope.inputPaths = ["AGENTS.md"];
budgetDraft.scope.allowedPaths = ["budget-work/**", ".opencode-subagent/results/TASK-BUDGET.md"];
budgetDraft.resultPath = ".opencode-subagent/results/TASK-BUDGET.md";
budgetDraft.requirements = ["Exercise the budget handoff path."];
await writeFile(budgetDraftPath, `${JSON.stringify(budgetDraft, null, 2)}\n`, "utf8");

const configPath = path.join(repo, ".opencode-subagent", "config.json");
const projectConfig = JSON.parse(await readFile(configPath, "utf8"));
projectConfig.verificationExecutables.push("definitely-missing-verifier-5f9c");
await writeFile(configPath, `${JSON.stringify(projectConfig, null, 2)}\n`, "utf8");
const badDraftPath = path.join(repo, ".opencode-subagent", "drafts", "TASK-BAD.json");
const badDraft = JSON.parse(await readFile(badDraftPath, "utf8"));
badDraft.scope.allowedPaths = ["work/**", ".opencode-subagent/results/TASK-BAD.md"];
badDraft.resultPath = ".opencode-subagent/results/TASK-BAD.md";
badDraft.requirements = ["This task must not be sealed because its verifier is unavailable."];
badDraft.verificationCommands = [{ executable: "definitely-missing-verifier-5f9c", args: ["--version"], timeoutSeconds: 10 }];
await writeFile(badDraftPath, `${JSON.stringify(badDraft, null, 2)}\n`, "utf8");
run(jj, ["describe", "-m", "configure OpenCode subagent test"], repo);
run(jj, ["new"], repo);

const deniedApproval = runResult(process.execPath, [cli, "approve", "TASK-BAD", "--confirm=TASK-BAD", `--root=${repo}`], repo);
assert.notEqual(deniedApproval.status, 0, "approve must reject an unresolved verification executable");
assert.match(deniedApproval.stderr, /Unable to resolve approved verification executable/);
assert.equal(existsSync(path.join(repo, ".opencode-subagent", "tasks", "TASK-BAD.json")), false);
run(process.execPath, [cli, "approve", "TASK-BUDGET", "--confirm=TASK-BUDGET", "--run", "--ack-external-data-sharing",
  "--foreground", "--executor=fake-budget", `--root=${repo}`], repo);
const budgetState = JSON.parse(await readFile(path.join(repo, ".opencode-subagent", "runtime", "tasks", "TASK-BUDGET.json"), "utf8"));
assert.equal(budgetState.status, "AWAITING_CODEX_REVIEW");
assert.equal(budgetState.reviewOutcome, "BUDGET_EXHAUSTED");
assert.deepEqual(budgetState.nextActions, ["CODEX_REVIEW"]);
run(process.execPath, [cli, "approve", "TASK-TEST", "--confirm=TASK-TEST", "--run", "--ack-external-data-sharing",
  "--foreground", "--executor=fake-success", `--root=${repo}`], repo);

const state = JSON.parse(await readFile(path.join(repo, ".opencode-subagent", "runtime", "tasks", "TASK-TEST.json"), "utf8"));
assert.equal(state.status, "AWAITING_CODEX_REVIEW");
assert.equal(state.approvalMode, "SINGLE_APPROVAL");
assert.deepEqual(state.nextActions, ["CODEX_REVIEW"]);
assert.equal(state.pushAuthorized, false);
assert.equal(state.verification.ok, true);
assert.ok(state.changedPaths.includes("work/fake-output.txt"));
assert.ok(state.changedPaths.includes(".opencode-subagent/results/TASK-TEST.md"));

const config = await loadProjectConfig(repo);
const contract = JSON.parse(await readFile(path.join(repo, ".opencode-subagent", "tasks", "TASK-TEST.json"), "utf8"));
const adapter = createJjWorkspaceAdapter(repo, config);
assert.equal((await adapter.checkBase(contract)).ok, true);
const realWorkspace = await adapter.create(contract);
assert.equal(existsSync(path.join(realWorkspace, "AGENTS.md")), true);
assert.equal(existsSync(path.join(realWorkspace, "secret.txt")), false);
assert.equal(existsSync(path.join(realWorkspace, ".agent-contract", "contract.json")), true);
assert.deepEqual(await adapter.changedPaths(realWorkspace), []);

run(process.execPath, [cli, "review", "TASK-TEST", "--confirm=TASK-TEST", "--verdict=pass", `--root=${repo}`], repo);
run(process.execPath, [cli, "integrate", "TASK-TEST", "--confirm=TASK-TEST", "--revision=@", `--root=${repo}`], repo);
const integratedState = JSON.parse(await readFile(path.join(repo, ".opencode-subagent", "runtime", "tasks", "TASK-TEST.json"), "utf8"));
assert.equal(integratedState.status, "INTEGRATED");
assert.equal(integratedState.pushAuthorized, false);
assert.deepEqual(integratedState.nextActions, ["PUSH_REQUIRES_EXPLICIT_AUTHORIZATION"]);

console.log(JSON.stringify({ ok: true, sandbox, status: integratedState.status, changedPaths: state.changedPaths, realWorkspace }, null, 2));

function run(executable, args, cwd) {
  const result = runResult(executable, args, cwd);
  assert.equal(result.status, 0, `${executable} ${args.join(" ")}\n${result.stderr || result.stdout}`);
  return result.stdout;
}

function runResult(executable, args, cwd) {
  return spawnSync(executable, args, {
    cwd,
    encoding: "utf8",
    windowsHide: true,
    env: { ...process.env, JJ_BIN: jj }
  });
}
