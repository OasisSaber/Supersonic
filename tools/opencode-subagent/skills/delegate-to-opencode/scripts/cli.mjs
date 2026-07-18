#!/usr/bin/env node
import { spawn } from "node:child_process";
import { closeSync, existsSync, openSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import {
  appendEvent,
  atomicWriteJson,
  auditLease,
  computeContractHash,
  loadRuntimeState,
  readJson,
  runtimePaths,
  transitionState,
  validateActiveContract,
  writeRuntimeState
} from "./core.mjs";
import { assertVerificationCommandsResolvable, checkEnvironment, resolveJj, runSync } from "./adapters.mjs";
import { findProjectRoot, initializeProject, loadProjectConfig } from "./project.mjs";
import { runSupervisor } from "./supervisor.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const [commandInput, subject, ...rest] = process.argv.slice(2);
const command = commandInput?.toLowerCase();
const allFlags = [subject, ...rest].filter(Boolean);
const rootFlag = allFlags.find((flag) => flag.startsWith("--root="));
const start = rootFlag?.slice("--root=".length) ?? process.cwd();

try {
  if (command === "init") await initCommand(start, allFlags);
  else {
    const root = findProjectRoot(start);
    const config = await loadProjectConfig(root);
    if (command === "doctor") await doctorCommand(root, config, flagSubject(subject));
    else if (command === "new") await newCommand(root, config, subject, rest);
    else if (command === "approve") await approveCommand(root, config, subject, rest);
    else if (command === "review") await reviewCommand(root, config, subject, rest);
    else if (command === "integrate") await integrateCommand(root, config, subject, rest);
    else if (command === "prepare") print(await runSupervisor({ root, taskId: subject, prepareOnly: true }));
    else if (command === "start") await startCommand(root, subject, rest);
    else if (command === "status") await statusCommand(root, subject);
    else if (command === "audit") await auditCommand(root, subject);
    else if (["dispatch", "accept", "return", "takeover", "cancel", "stop", "resume", "retry"].includes(command)) {
      await controlCommand(root, config, command.toUpperCase(), subject, rest);
    } else usage();
  }
} catch (error) {
  console.error(error.stack ?? error.message);
  process.exitCode = 1;
}

async function initCommand(startAt, flags) {
  const root = findProjectRoot(startAt, { initialized: false });
  const config = await initializeProject(root, {
    identity: valueFlag(flags, "identity"),
    model: valueFlag(flags, "model"),
    provider: valueFlag(flags, "provider"),
    force: flags.includes("--force")
  });
  print({ root, config, next: "Run doctor, then create a bounded draft with new TASK-ID." });
}

async function doctorCommand(root, config, taskId) {
  let contract = { model: config.model, verificationCommands: [] };
  if (taskId) {
    assertTaskId(taskId);
    const taskPath = path.join(root, ".opencode-subagent", "tasks", `${taskId}.json`);
    const draftPath = path.join(root, ".opencode-subagent", "drafts", `${taskId}.json`);
    contract = await readJson(existsSync(taskPath) ? taskPath : draftPath);
  }
  const environment = await checkEnvironment(root, contract);
  print({ root, config, environment });
  if (!environment.ok) process.exitCode = 1;
}

async function newCommand(root, config, taskId, flags) {
  assertTaskId(taskId);
  const target = path.join(root, ".opencode-subagent", "drafts", `${taskId}.json`);
  if (existsSync(target)) throw new Error(`Draft already exists: ${target}`);
  const example = await readJson(path.join(root, ".opencode-subagent", "contract.example.json"));
  example.id = taskId;
  example.title = valueFlag(flags, "title") ?? example.title;
  example.model = config.model;
  example.scope.allowedPaths = example.scope.allowedPaths.map((value) => value.replaceAll("TASK-0001", taskId));
  example.resultPath = example.resultPath.replaceAll("TASK-0001", taskId);
  await atomicWriteJson(target, example);
  print({ draft: target, next: "Edit requirements, scope, budgets, and deterministic verification before approval." });
}

async function approveCommand(root, config, taskId, flags) {
  assertConfirmed(taskId, flags);
  const singleApproval = flags.includes("--run");
  if (singleApproval && !flags.includes("--ack-external-data-sharing")) {
    throw new Error("Single-approval execution requires --ack-external-data-sharing in the user's APPROVE decision");
  }
  const draftPath = path.join(root, ".opencode-subagent", "drafts", `${taskId}.json`);
  const taskPath = path.join(root, ".opencode-subagent", "tasks", `${taskId}.json`);
  if (existsSync(taskPath)) throw new Error(`Immutable task already exists: ${taskPath}`);
  const draft = await readJson(draftPath);
  if (draft.id !== taskId || draft.lifecycle !== "DRAFT" || draft.approval?.status !== "PENDING") {
    throw new Error("Only a matching PENDING DRAFT can be approved");
  }
  const jj = resolveJj(root, config);
  const revision = valueFlag(flags, "base") ?? "@-";
  const changeId = runSync(jj, ["--ignore-working-copy", "log", "-r", revision, "--no-graph", "-T", "change_id"], { cwd: root });
  const commitId = runSync(jj, ["--ignore-working-copy", "log", "-r", revision, "--no-graph", "-T", "commit_id"], { cwd: root });
  const contract = structuredClone(draft);
  contract.lifecycle = "ACTIVE";
  contract.base = { locked: true, changeId, commitId };
  contract.approval = {
    status: "APPROVED",
    approvedBy: config.userIdentity,
    approvedAt: new Date().toISOString(),
    mode: singleApproval ? "SINGLE_APPROVAL" : "MANUAL_GATES",
    grants: singleApproval
      ? ["EXTERNAL_DATA_SHARING", "DISPATCH_ONCE", "CODEX_REVIEW", "CODEX_TAKEOVER", "LOCAL_INTEGRATION"]
      : [],
    pushAuthorized: false,
    contractHash: null
  };
  contract.approval.contractHash = computeContractHash(contract);
  validateActiveContract(contract, taskId, config);
  const verificationExecutables = assertVerificationCommandsResolvable(root, config, contract.verificationCommands);
  await atomicWriteJson(taskPath, contract);
  draft.lifecycle = "PROMOTED";
  draft.approval = { ...contract.approval, status: "PROMOTED" };
  draft.promotedTo = `.opencode-subagent/tasks/${taskId}.json`;
  await atomicWriteJson(draftPath, draft);
  print({ taskId, taskPath, base: contract.base, contractHash: contract.approval.contractHash, verificationExecutables,
    approvalMode: contract.approval.mode, grants: contract.approval.grants, pushAuthorized: false });
  if (singleApproval) {
    const state = await runSupervisor({ root, taskId, prepareOnly: true });
    state.dispatchAuthorization = authorization("DISPATCH", config.userIdentity, "SINGLE_APPROVAL");
    await writeRuntimeState(root, taskId, state);
    await appendEvent(root, taskId, {
      type: "single-approval-authorized",
      authorizedBy: config.userIdentity,
      grants: contract.approval.grants,
      pushAuthorized: false
    });
    await startCommand(root, taskId, flags);
  }
}

async function reviewCommand(root, config, taskId, flags) {
  assertConfirmed(taskId, flags);
  if (valueFlag(flags, "verdict") !== "pass") throw new Error("Codex review requires --verdict=pass");
  const state = await loadRuntimeState(root, taskId);
  if (!state) throw new Error(`No runtime state for ${taskId}`);
  if (state.status !== "AWAITING_CODEX_REVIEW") throw new Error(`Review requires AWAITING_CODEX_REVIEW, got ${state.status}`);
  if (state.approvalMode !== "SINGLE_APPROVAL" || !state.grants?.includes("CODEX_REVIEW")) {
    throw new Error("Task does not carry a single-approval Codex review grant");
  }
  await transitionState(root, state, "READY_TO_INTEGRATE", {
    owner: "codex",
    codexReview: {
      verdict: "PASS",
      reviewedBy: "Codex",
      approvalOwner: config.userIdentity,
      reviewedAt: new Date().toISOString(),
      note: valueFlag(flags, "note") ?? null
    },
    nextActions: ["LOCAL_INTEGRATION"]
  });
  print({ taskId, status: state.status, codexReview: state.codexReview });
}

async function integrateCommand(root, config, taskId, flags) {
  assertConfirmed(taskId, flags);
  const state = await loadRuntimeState(root, taskId);
  if (!state) throw new Error(`No runtime state for ${taskId}`);
  if (state.status !== "READY_TO_INTEGRATE") throw new Error(`Integration requires READY_TO_INTEGRATE, got ${state.status}`);
  if (state.approvalMode !== "SINGLE_APPROVAL" || !state.grants?.includes("LOCAL_INTEGRATION")) {
    throw new Error("Task does not carry a single-approval local integration grant");
  }
  const revision = valueFlag(flags, "revision");
  if (!revision) throw new Error("Integration receipt requires --revision=<integrated-jj-revision>");
  const jj = resolveJj(root, config);
  const changeId = runSync(jj, ["--ignore-working-copy", "log", "-r", revision, "--no-graph", "-T", "change_id"], { cwd: root });
  const commitId = runSync(jj, ["--ignore-working-copy", "log", "-r", revision, "--no-graph", "-T", "commit_id"], { cwd: root });
  await transitionState(root, state, "INTEGRATED", {
    owner: "codex",
    integrationReceipt: {
      revision,
      changeId,
      commitId,
      recordedBy: "Codex",
      approvalOwner: config.userIdentity,
      recordedAt: new Date().toISOString()
    },
    nextActions: ["PUSH_REQUIRES_EXPLICIT_AUTHORIZATION"]
  });
  print({ taskId, status: state.status, integrationReceipt: state.integrationReceipt, pushAuthorized: state.pushAuthorized });
}

async function startCommand(root, taskId, flags) {
  assertTaskId(taskId);
  const foreground = flags.includes("--foreground");
  const worker = path.join(scriptDir, "worker.mjs");
  const args = [worker, taskId, `--root=${root}`];
  if (flags.includes("--recover")) args.push("--recover");
  const fake = valueFlag(flags, "executor");
  if (fake) args.push(`--executor=${fake}`);
  if (foreground) {
    const child = spawn(process.execPath, args, { cwd: root, stdio: "inherit", windowsHide: true });
    process.exitCode = await new Promise((resolve) => child.on("close", resolve));
    return;
  }
  const paths = runtimePaths(root, taskId);
  await mkdir(path.dirname(paths.supervisorLog), { recursive: true });
  const out = openSync(paths.supervisorLog, "a");
  const child = spawn(process.execPath, args, { cwd: root, detached: true, windowsHide: true, stdio: ["ignore", out, out] });
  child.unref();
  closeSync(out);
  print({ taskId, supervisorPid: child.pid, statusCommand: `node ${path.join(scriptDir, "cli.mjs")} status ${taskId} --root=${root}` });
}

async function statusCommand(root, taskId) {
  assertTaskId(taskId);
  print({ state: await loadRuntimeState(root, taskId), lease: await auditLease(root, taskId) });
}

async function auditCommand(root, taskId) {
  const state = await loadRuntimeState(root, taskId);
  if (!state) throw new Error(`No runtime state for ${taskId}`);
  const lease = await auditLease(root, taskId);
  if (["RUNNING", "CORRECTING", "VERIFYING"].includes(state.status) && lease.stale) {
    await transitionState(root, state, "INTERRUPTED", {
      interruptedReason: lease.exists ? "stale heartbeat or dead supervisor PID" : "missing supervisor lease"
    });
  }
  print({ state, lease });
}

async function controlCommand(root, config, action, taskId, flags) {
  assertConfirmed(taskId, flags);
  const state = await loadRuntimeState(root, taskId);
  if (!state) throw new Error(`No runtime state for ${taskId}`);
  if (action === "DISPATCH") {
    if (state.status !== "READY") throw new Error(`DISPATCH requires READY, got ${state.status}`);
    state.dispatchAuthorization = authorization("DISPATCH", config.userIdentity);
    await writeRuntimeState(root, taskId, state);
    await appendEvent(root, taskId, { type: "dispatch-authorized", authorizedBy: config.userIdentity });
    return print({ taskId, status: state.status, authorized: "DISPATCH" });
  }
  if (["RESUME", "RETRY"].includes(action)) {
    if (state.status !== "INTERRUPTED") throw new Error(`${action} requires INTERRUPTED, got ${state.status}`);
    if (action === "RESUME" && !state.sessionId) throw new Error("RESUME requires a recorded OpenCode sessionId; use RETRY instead");
    state.recoveryAuthorization = authorization(action, config.userIdentity);
    await writeRuntimeState(root, taskId, state);
    await appendEvent(root, taskId, { type: "recovery-authorized", action, authorizedBy: config.userIdentity });
    return print({ taskId, authorized: action });
  }
  if (action === "STOP") {
    await atomicWriteJson(runtimePaths(root, taskId).control, {
      schemaVersion: 1, taskId, action: "STOP", requestedBy: config.userIdentity, requestedAt: new Date().toISOString()
    });
    await appendEvent(root, taskId, { type: "user-control", action: "STOP", requestedBy: config.userIdentity });
    return print({ taskId, requested: "STOP" });
  }
  const targets = { ACCEPT: "AWAITING_CODEX_REVIEW", RETURN: "RETURNED", TAKEOVER: "USER_OWNED", CANCEL: "CANCELLED" };
  const target = targets[action];
  if (!target) usage();
  await transitionState(root, state, target, {
    userDecision: { action, decidedBy: config.userIdentity, decidedAt: new Date().toISOString() },
    owner: action === "TAKEOVER" ? config.userIdentity : state.owner,
    ...(action === "TAKEOVER" ? { takeoverReceipt: {
      workspacePath: state.workspacePath ?? null,
      changedPaths: state.changedPaths ?? [],
      verification: state.verification ?? null,
      recordedAt: new Date().toISOString()
    } } : {})
  });
  print({ taskId, action, status: target, takeoverReceipt: state.takeoverReceipt });
}

function authorization(action, identity, source = "EXPLICIT_GATE") {
  return { action, authorizedBy: identity, authorizedAt: new Date().toISOString(), usedAt: null, source };
}

function assertConfirmed(taskId, flags) {
  assertTaskId(taskId);
  if (!flags.includes(`--confirm=${taskId}`)) throw new Error(`Confirmation required: --confirm=${taskId}`);
}

function assertTaskId(taskId) {
  if (!/^[A-Z][A-Z0-9_-]{2,63}$/.test(taskId ?? "")) throw new Error("Task id must be 3-64 uppercase letters, digits, underscores, or hyphens");
}

function valueFlag(flags, name) {
  return flags.find((flag) => flag.startsWith(`--${name}=`))?.slice(name.length + 3);
}

function flagSubject(value) {
  return value?.startsWith("--") ? null : value;
}

function print(value) {
  console.log(JSON.stringify(value, null, 2));
}

function usage() {
  console.error("Usage: cli.mjs <init|doctor|new|approve|prepare|dispatch|start|status|audit|review|integrate|accept|return|takeover|cancel|stop|resume|retry> [TASK-ID] [flags]");
  process.exit(2);
}
