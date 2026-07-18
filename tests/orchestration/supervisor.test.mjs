import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import {
  acquireLease,
  atomicWriteJson,
  auditLease,
  computeContractHash,
  createInitialState,
  findScopeViolations,
  loadRuntimeState,
  releaseLease,
  runtimePaths,
  selectExecutorModel,
  transitionState,
  validateActiveContract,
  writeRuntimeState
} from "../../scripts/agent/core.mjs";
import { createFakeEnvironment, createFakeExecutor, createFakeVerifier, createFakeWorkspaceAdapter } from "../../scripts/agent/fake.mjs";
import { runSupervisor } from "../../scripts/agent/supervisor.mjs";
import { buildOpenCodePrompt, createJjWorkspaceAdapter } from "../../scripts/agent/adapters.mjs";

test("sealed active contract detects tampering", async () => {
  const contract = makeContract();
  assert.doesNotThrow(() => validateActiveContract(contract, contract.id));
  contract.title = "tampered";
  assert.throws(() => validateActiveContract(contract, contract.id), /hash mismatch/);
});

test("contract approval identity and status are mandatory", () => {
  const contract = makeContract();
  contract.approval.status = "PENDING";
  contract.approval.contractHash = computeContractHash(contract);
  assert.throws(() => validateActiveContract(contract, contract.id), /approved and sealed/);

  contract.approval.status = "APPROVED";
  contract.approval.approvedBy = "opencode";
  contract.approval.contractHash = computeContractHash(contract);
  assert.throws(() => validateActiveContract(contract, contract.id), /approved and sealed/);
});

test("Codex-only paths and high-risk work cannot be delegated", () => {
  const protectedScope = makeContract();
  protectedScope.scope.allowedPaths.push("docs/ai-collaboration/**");
  protectedScope.approval.contractHash = computeContractHash(protectedScope);
  assert.throws(() => validateActiveContract(protectedScope, protectedScope.id), /Codex-only paths/);

  const highRisk = makeContract();
  highRisk.riskLevel = "L2";
  highRisk.approval.contractHash = computeContractHash(highRisk);
  assert.throws(() => validateActiveContract(highRisk, highRisk.id), /reserved for Codex/);
});

test("OpenCode model policy defaults to Flash and reserves Pro for high complexity", () => {
  assert.deepEqual(selectExecutorModel(), {
    complexity: "LOW",
    model: "deepseek/deepseek-v4-flash",
    defaultApplied: true
  });
  assert.equal(selectExecutorModel("medium").model, "deepseek/deepseek-v4-flash");
  assert.equal(selectExecutorModel("HIGH").model, "deepseek/deepseek-v4-pro");
  assert.throws(() => selectExecutorModel("EXTREME"), /Unsupported task complexity/);
});

test("sealed model policy rejects executor-side model switching while legacy contracts remain valid", () => {
  const governed = makeContract();
  governed.complexity = "MEDIUM";
  governed.model = "deepseek/deepseek-v4-flash";
  governed.modelPolicy = { version: 1, selectedBy: "codex-contract-approval", defaultApplied: false };
  governed.approval.contractHash = computeContractHash(governed);
  assert.doesNotThrow(() => validateActiveContract(governed, governed.id));

  governed.model = "deepseek/deepseek-v4-pro";
  governed.approval.contractHash = computeContractHash(governed);
  assert.throws(() => validateActiveContract(governed, governed.id), /does not match MEDIUM complexity policy/);

  const legacy = makeContract();
  assert.doesNotThrow(() => validateActiveContract(legacy, legacy.id));
});

test("successful fake execution stops at AWAITING_USER", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture);
  assert.equal(state.status, "AWAITING_USER");
  assert.equal(state.verification.ok, true);
  assert.deepEqual(state.nextActions, ["ACCEPT", "RETURN", "TAKEOVER", "CANCEL"]);
  assert.equal((await auditLease(fixture.root, fixture.contract.id)).exists, false);
});

test("scope violation is blocked before user review", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture, { scenario: "scope-violation" });
  assert.equal(state.status, "PERMISSION_BLOCKED");
  assert.deepEqual(state.violations, ["forbidden-by-contract.txt"]);
});

test("deterministic verification failure receives one correction and can pass", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture, { verifier: createFakeVerifier([false, true]) });
  assert.equal(state.status, "AWAITING_USER");
  assert.equal(state.correctionCycles, 1);
  assert.deepEqual(state.usage, { inputTokens: 240, outputTokens: 80, cost: 0.002 });
});

test("correction usage is cumulative and can exhaust the task budget", async () => {
  const fixture = await makeFixture({ maxInputTokens: 200 });
  const state = await runFake(fixture, { verifier: createFakeVerifier([false, true]) });
  assert.equal(state.status, "BUDGET_EXHAUSTED");
  assert.equal(state.usage.inputTokens, 240);
});

test("missing executor usage telemetry fails closed", async () => {
  const fixture = await makeFixture();
  const base = createFakeExecutor("success");
  const executor = {
    async execute(args) {
      const result = await base.execute({ ...args, onUsage: undefined });
      return { ...result, usage: { inputTokens: 0, outputTokens: 0, cost: 0 }, usageReported: false };
    }
  };
  const state = await runFake(fixture, { executor });
  assert.equal(state.status, "BUDGET_EXHAUSTED");
  assert.match(state.budgetReason, /telemetry missing/);
});

test("correction prompt contains deterministic verification details", () => {
  const contract = makeContract();
  const verification = {
    ok: false,
    results: [{ executable: "node", args: ["--test"], exitCode: 1, stderr: "assertion failed" }]
  };
  const prompt = buildOpenCodePrompt(contract, true, verification);
  assert.match(prompt, /node/);
  assert.match(prompt, /assertion failed/);
  assert.match(prompt, /Do not expand scope/);
});

test("second verification failure stops at VERIFICATION_FAILED", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture, { verifier: createFakeVerifier([false, false]) });
  assert.equal(state.status, "VERIFICATION_FAILED");
  assert.equal(state.correctionCycles, 1);
});

test("environment drift prevents executor start", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture, { environment: createFakeEnvironment(false) });
  assert.equal(state.status, "ENVIRONMENT_DRIFT");
});

test("stale base prevents executor start", async () => {
  const fixture = await makeFixture();
  const workspace = createFakeWorkspaceAdapter(fixture.workspacePath, { staleBase: true });
  const state = await runFake(fixture, { workspace });
  assert.equal(state.status, "STALE_BASE");
});

test("reported token overage stops at BUDGET_EXHAUSTED", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture, { scenario: "budget" });
  assert.equal(state.status, "BUDGET_EXHAUSTED");
});

test("executor failure becomes INTERRUPTED and never auto-retries", async () => {
  const fixture = await makeFixture();
  const state = await runFake(fixture, { scenario: "interrupted" });
  assert.equal(state.status, "INTERRUPTED");
  assert.equal(state.correctionCycles, 0);
});

test("runtime timeout stops execution", async () => {
  const fixture = await makeFixture({ maxRuntimeMinutes: 0.001 });
  const state = await runFake(fixture, { scenario: "timeout" });
  assert.equal(state.status, "BUDGET_EXHAUSTED");
  assert.match(state.budgetReason, /runtime exceeded/);
});

test("lease is exclusive and dead PID is reported stale", async () => {
  const fixture = await makeFixture();
  const lease = await acquireLease(fixture.root, fixture.contract.id, { ttlMs: 90_000 });
  await assert.rejects(acquireLease(fixture.root, fixture.contract.id), /Lease conflict/);
  lease.pid = 999_999_999;
  lease.heartbeatAt = new Date(Date.now() - 120_000).toISOString();
  await atomicWriteJson(runtimePaths(fixture.root, fixture.contract.id).lease, lease);
  const audit = await auditLease(fixture.root, fixture.contract.id);
  assert.equal(audit.stale, true);
  await releaseLease(fixture.root, lease);
});

test("human acceptance, takeover and push remain separate transitions", async () => {
  const fixture = await makeFixture();
  let state = createInitialState(fixture.contract.id, fixture.contract);
  state.status = "AWAITING_USER";
  await writeRuntimeState(fixture.root, fixture.contract.id, state);
  await transitionState(fixture.root, state, "AWAITING_CODEX_REVIEW", { userDecision: { action: "ACCEPT" } });
  assert.equal(state.status, "AWAITING_CODEX_REVIEW");
  await transitionState(fixture.root, state, "READY_TO_INTEGRATE", { codexReview: "approved" });
  assert.equal(state.status, "READY_TO_INTEGRATE");
  await transitionState(fixture.root, state, "INTEGRATED");
  assert.equal(state.status, "INTEGRATED");
  assert.notEqual(state.status, "PUSHED");

  const takeover = createInitialState(fixture.contract.id, fixture.contract);
  takeover.status = "USER_OWNED";
  await transitionState(fixture.root, takeover, "READY_TO_INTEGRATE", { userDecision: { action: "ACCEPT" } });
  assert.equal(takeover.status, "READY_TO_INTEGRATE");
  await transitionState(fixture.root, takeover, "INTEGRATED", { integration: { changeId: "change", commitId: "commit" } });
  assert.equal(takeover.status, "INTEGRATED");
  assert.notEqual(takeover.status, "PUSHED");
});

test("scope matcher accepts only explicit paths and directory rules", () => {
  const violations = findScopeViolations(
    ["apps/dashboard/server.mjs", "apps/dashboard/public/app.js", "package.json"],
    ["apps/dashboard/server.mjs", "apps/dashboard/public/**"]
  );
  assert.deepEqual(violations, ["package.json"]);
});

test("raw runtime directory is ignored by Git", async () => {
  const gitignore = await readFile(path.resolve(".gitignore"), "utf8");
  assert.match(gitignore, /orchestration\/runtime\//);
});

test("detached Supervisor survives its launcher process", async () => {
  const fixture = await makeFixture();
  await prepareAndAuthorize(fixture);
  const worker = path.resolve("scripts/agent-supervisor-worker.mjs");
  const launcher = [
    "const {spawn}=require('node:child_process');",
    "const [worker,task,root]=process.argv.slice(1);",
    "const child=spawn(process.execPath,[worker,task,'--executor=fake-success','--root='+root],{detached:true,stdio:'ignore'});",
    "child.unref();"
  ].join("");
  const launched = spawnSync(process.execPath, ["-e", launcher, worker, fixture.contract.id, fixture.root], { encoding: "utf8" });
  assert.equal(launched.status, 0, launched.stderr);
  const state = await waitForState(fixture.root, fixture.contract.id, "AWAITING_USER", 5_000);
  assert.equal(state.status, "AWAITING_USER");
});

test("control CLI requires explicit task-id confirmation", async () => {
  const fixture = await makeFixture();
  const state = createInitialState(fixture.contract.id, fixture.contract);
  state.status = "AWAITING_USER";
  await writeRuntimeState(fixture.root, fixture.contract.id, state);
  const cli = path.resolve("scripts/agent-control.mjs");

  const denied = spawnSync(process.execPath, [cli, "accept", fixture.contract.id, `--root=${fixture.root}`], { encoding: "utf8" });
  assert.equal(denied.status, 2);
  assert.equal((await loadRuntimeState(fixture.root, fixture.contract.id)).status, "AWAITING_USER");

  const accepted = spawnSync(process.execPath, [
    cli,
    "accept",
    fixture.contract.id,
    `--root=${fixture.root}`,
    `--confirm=${fixture.contract.id}`
  ], { encoding: "utf8" });
  assert.equal(accepted.status, 0, accepted.stderr);
  assert.equal((await loadRuntimeState(fixture.root, fixture.contract.id)).status, "AWAITING_CODEX_REVIEW");
});

test("interrupted execution cannot recover without explicit authorization", async () => {
  const fixture = await makeFixture();
  const workspace = createFakeWorkspaceAdapter(fixture.workspacePath);
  const interrupted = await runFake(fixture, { workspace, scenario: "interrupted" });
  assert.equal(interrupted.status, "INTERRUPTED");

  await assert.rejects(runSupervisor({
    root: fixture.root,
    taskId: fixture.contract.id,
    recover: true,
    environment: createFakeEnvironment(true),
    workspace,
    executor: createFakeExecutor("success"),
    verifier: createFakeVerifier([true])
  }), /RESUME or RETRY authorization/);

  interrupted.recoveryAuthorization = {
    action: "RETRY",
    authorizedBy: "Oasis",
    authorizedAt: new Date().toISOString(),
    usedAt: null
  };
  await writeRuntimeState(fixture.root, fixture.contract.id, interrupted);
  const recovered = await runSupervisor({
    root: fixture.root,
    taskId: fixture.contract.id,
    recover: true,
    environment: createFakeEnvironment(true),
    workspace,
    executor: createFakeExecutor("success"),
    verifier: createFakeVerifier([true])
  });
  assert.equal(recovered.status, "AWAITING_USER");
  assert.ok(recovered.recoveryAuthorization.usedAt);
});

test("Jujutsu sparse workspace excludes unapproved repository files", async () => {
  const sandbox = await mkdtemp(path.join(tmpdir(), "agent-jj-workspace-test-"));
  const repo = path.join(sandbox, "repo");
  const workspaceRoot = path.join(sandbox, "workspaces");
  const jj = process.env.JJ_BIN ?? path.resolve(".tools/jj/jj.exe");
  runJj(jj, ["git", "init", "--colocate", repo], sandbox);
  await writeFile(path.join(repo, ".gitignore"), ".agent-contract/\n", "utf8");
  await writeFile(path.join(repo, "AGENTS.md"), "test rules\n", "utf8");
  await writeFile(path.join(repo, "secret.txt"), "must stay outside sparse workspace\n", "utf8");
  runJj(jj, ["describe", "-m", "test base"], repo);
  runJj(jj, ["status"], repo);
  const changeId = runJj(jj, ["--ignore-working-copy", "log", "-r", "@", "--no-graph", "-T", "change_id"], repo);
  const commitId = runJj(jj, ["--ignore-working-copy", "log", "-r", "@", "--no-graph", "-T", "commit_id"], repo);
  const contract = makeContract();
  contract.base = { locked: true, changeId, commitId };
  contract.scope.inputPaths = [".gitignore", "AGENTS.md"];
  contract.scope.allowedPaths = ["work/**"];
  contract.resultPath = "work/result.md";
  contract.approval.contractHash = computeContractHash(contract);

  const previousJj = process.env.JJ_BIN;
  const previousRoot = process.env.AGENT_WORKSPACE_ROOT;
  process.env.JJ_BIN = jj;
  process.env.AGENT_WORKSPACE_ROOT = workspaceRoot;
  try {
    const adapter = createJjWorkspaceAdapter(repo);
    assert.equal((await adapter.checkBase(contract)).ok, true);
    const taskWorkspace = await adapter.create(contract);
    assert.equal(existsSync(path.join(taskWorkspace, "AGENTS.md")), true);
    assert.equal(existsSync(path.join(taskWorkspace, "secret.txt")), false);
    assert.equal(existsSync(path.join(taskWorkspace, ".agent-contract", "contract.json")), true);
    await mkdir(path.join(taskWorkspace, "work"), { recursive: true });
    await writeFile(path.join(taskWorkspace, "work", "result.md"), "ok\n", "utf8");
    assert.deepEqual(await adapter.changedPaths(taskWorkspace), ["work/result.md"]);
  } finally {
    if (previousJj === undefined) delete process.env.JJ_BIN; else process.env.JJ_BIN = previousJj;
    if (previousRoot === undefined) delete process.env.AGENT_WORKSPACE_ROOT; else process.env.AGENT_WORKSPACE_ROOT = previousRoot;
  }
});

async function runFake(fixture, options = {}) {
  await prepareAndAuthorize(fixture, options);
  return runSupervisor({
    root: fixture.root,
    taskId: fixture.contract.id,
    environment: options.environment ?? createFakeEnvironment(true),
    workspace: options.workspace ?? createFakeWorkspaceAdapter(fixture.workspacePath),
    executor: options.executor ?? createFakeExecutor(options.scenario ?? "success"),
    verifier: options.verifier ?? createFakeVerifier([true]),
    heartbeatIntervalMs: 10,
    leaseTtlMs: 100
  });
}

async function prepareAndAuthorize(fixture, options = {}) {
  let state = await loadRuntimeState(fixture.root, fixture.contract.id);
  if (!state) {
    state = await runSupervisor({
      root: fixture.root,
      taskId: fixture.contract.id,
      prepareOnly: true,
      environment: options.environment ?? createFakeEnvironment(true),
      workspace: options.workspace ?? createFakeWorkspaceAdapter(fixture.workspacePath),
      executor: options.executor ?? createFakeExecutor(options.scenario ?? "success"),
      verifier: options.verifier ?? createFakeVerifier([true])
    });
  }
  if (state.status === "READY" && !state.dispatchAuthorization) {
    state.dispatchAuthorization = {
      action: "DISPATCH",
      authorizedBy: "Oasis",
      authorizedAt: new Date().toISOString(),
      usedAt: null
    };
    await writeRuntimeState(fixture.root, fixture.contract.id, state);
  }
}

async function makeFixture(budgetOverrides = {}) {
  const root = await mkdtemp(path.join(tmpdir(), "agent-supervisor-test-"));
  const contract = makeContract(budgetOverrides);
  await mkdir(path.join(root, "orchestration", "tasks"), { recursive: true });
  await writeFile(path.join(root, "orchestration", "tasks", `${contract.id}.json`), `${JSON.stringify(contract, null, 2)}\n`);
  return { root, contract, workspacePath: path.join(root, "fake-workspace") };
}

function makeContract(budgetOverrides = {}) {
  const contract = {
    schemaVersion: 2,
    contractVersion: 2,
    id: "TASK-TEST",
    title: "Fake task",
    lifecycle: "ACTIVE",
    riskLevel: "L1",
    authority: "DELEGATABLE",
    executor: "opencode",
    model: "deepseek/deepseek-v4-pro",
    base: { locked: true, changeId: "base-change", commitId: "base-commit" },
    approval: { status: "APPROVED", approvedBy: "Oasis", approvedAt: "2026-07-16T00:00:00+08:00" },
    budget: {
      maxRuntimeMinutes: 1,
      maxInputTokens: 1000,
      maxOutputTokens: 500,
      maxCost: 1,
      maxCorrectionCycles: 1,
      ...budgetOverrides
    },
    scope: {
      inputPaths: ["AGENTS.md"],
      allowedPaths: ["work/**", "orchestration/results/TASK-TEST.md"]
    },
    verificationCommands: [
      { executable: "node", args: ["--version"], timeoutSeconds: 5 }
    ],
    resultPath: "orchestration/results/TASK-TEST.md"
  };
  contract.approval.contractHash = computeContractHash(contract);
  return contract;
}

async function waitForState(root, taskId, expected, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const state = await loadRuntimeState(root, taskId);
    if (state?.status === expected) return state;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`Timed out waiting for ${expected}`);
}

function runJj(jj, args, cwd) {
  const result = spawnSync(jj, args, { cwd, encoding: "utf8", windowsHide: true });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return result.stdout.trim();
}
