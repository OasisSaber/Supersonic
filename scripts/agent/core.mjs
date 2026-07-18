import { createHash, randomUUID } from "node:crypto";
import { appendFile, mkdir, open, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

export const TERMINAL_OR_PAUSED = new Set([
  "AWAITING_USER",
  "INTERRUPTED",
  "STALE_BASE",
  "ENVIRONMENT_DRIFT",
  "BUDGET_REVIEW",
  "BUDGET_EXHAUSTED",
  "PERMISSION_BLOCKED",
  "VERIFICATION_FAILED",
  "AWAITING_CODEX_REVIEW",
  "RETURNED",
  "USER_OWNED",
  "CANCELLED",
  "READY_TO_INTEGRATE",
  "INTEGRATED",
  "PUSHED"
]);

export const TRANSITIONS = Object.freeze({
  READY: new Set(["RUNNING", "INTERRUPTED", "STALE_BASE", "ENVIRONMENT_DRIFT", "BUDGET_REVIEW", "PERMISSION_BLOCKED"]),
  RUNNING: new Set(["VERIFYING", "INTERRUPTED", "BUDGET_EXHAUSTED", "PERMISSION_BLOCKED"]),
  VERIFYING: new Set(["CORRECTING", "AWAITING_USER", "VERIFICATION_FAILED", "PERMISSION_BLOCKED", "INTERRUPTED"]),
  CORRECTING: new Set(["VERIFYING", "INTERRUPTED", "BUDGET_EXHAUSTED", "PERMISSION_BLOCKED"]),
  AWAITING_USER: new Set(["AWAITING_CODEX_REVIEW", "RETURNED", "USER_OWNED", "CANCELLED"]),
  INTERRUPTED: new Set(["RUNNING", "STALE_BASE", "ENVIRONMENT_DRIFT", "BUDGET_REVIEW", "BUDGET_EXHAUSTED", "PERMISSION_BLOCKED", "USER_OWNED", "CANCELLED"]),
  VERIFICATION_FAILED: new Set(["RETURNED", "USER_OWNED", "CANCELLED"]),
  BUDGET_EXHAUSTED: new Set(["USER_OWNED", "CANCELLED"]),
  BUDGET_REVIEW: new Set(["CANCELLED"]),
  STALE_BASE: new Set(["CANCELLED"]),
  ENVIRONMENT_DRIFT: new Set(["CANCELLED"]),
  PERMISSION_BLOCKED: new Set(["USER_OWNED", "CANCELLED"]),
  AWAITING_CODEX_REVIEW: new Set(["READY_TO_INTEGRATE", "RETURNED"]),
  READY_TO_INTEGRATE: new Set(["INTEGRATED", "RETURNED"]),
  INTEGRATED: new Set(["PUSHED"]),
  RETURNED: new Set([]),
  USER_OWNED: new Set(["READY_TO_INTEGRATE", "CANCELLED"]),
  CANCELLED: new Set([]),
  PUSHED: new Set([])
});

const CODEX_ONLY_PATHS = Object.freeze([
  "AGENTS.md",
  "opencode.json",
  "package.json",
  "pnpm-lock.yaml",
  "pnpm-workspace.yaml",
  ".github/**",
  "docs/adr/**",
  "docs/ai-collaboration/**",
  "orchestration/tasks/**",
  "orchestration/drafts/**",
  "scripts/agent/**",
  "scripts/agent-control.mjs",
  "scripts/agent-supervisor.mjs",
  "scripts/agent-supervisor-worker.mjs"
]);

export const OPENCODE_MODEL_POLICY = Object.freeze({
  version: 1,
  defaultComplexity: "LOW",
  flashModel: "deepseek/deepseek-v4-flash",
  proModel: "deepseek/deepseek-v4-pro"
});

export function selectExecutorModel(complexity) {
  const normalized = typeof complexity === "string" ? complexity.toUpperCase() : OPENCODE_MODEL_POLICY.defaultComplexity;
  if (!["LOW", "MEDIUM", "HIGH"].includes(normalized)) {
    throw new Error(`Unsupported task complexity: ${complexity}`);
  }
  return {
    complexity: normalized,
    model: normalized === "HIGH" ? OPENCODE_MODEL_POLICY.proModel : OPENCODE_MODEL_POLICY.flashModel,
    defaultApplied: complexity === undefined || complexity === null || complexity === ""
  };
}

export function assertTransition(from, to) {
  if (!TRANSITIONS[from]?.has(to)) {
    throw new Error(`Invalid task transition: ${from} -> ${to}`);
  }
}

export function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function computeContractHash(contract) {
  const copy = structuredClone(contract);
  if (copy.approval) delete copy.approval.contractHash;
  return createHash("sha256").update(stableStringify(copy)).digest("hex");
}

export function validateActiveContract(contract, taskId) {
  if (contract.schemaVersion !== 2) throw new Error("Active task contract must use schemaVersion 2");
  if (contract.id !== taskId) throw new Error("Task id does not match contract filename");
  if (contract.lifecycle !== "ACTIVE") throw new Error(`Task contract is not active: ${contract.lifecycle}`);
  if (contract.authority !== "DELEGATABLE" || contract.executor !== "opencode") {
    throw new Error("Task is not authorized for OpenCode");
  }
  if (contract.approval?.status !== "APPROVED" || contract.approval?.approvedBy !== "Oasis"
      || !contract.approval?.approvedAt || Number.isNaN(Date.parse(contract.approval.approvedAt))
      || !contract.approval?.contractHash) {
    throw new Error("Task contract has not been approved and sealed");
  }
  if (["L2", "L3", "CRITICAL"].includes(contract.riskLevel)) {
    throw new Error(`Risk level ${contract.riskLevel} is reserved for Codex`);
  }
  if (contract.modelPolicy?.version === OPENCODE_MODEL_POLICY.version) {
    const selection = selectExecutorModel(contract.complexity);
    if (contract.model !== selection.model) {
      throw new Error(`Task model does not match ${selection.complexity} complexity policy`);
    }
    if (contract.modelPolicy.selectedBy !== "codex-contract-approval") {
      throw new Error("Task model policy was not selected by Codex contract approval");
    }
  }
  const actualHash = computeContractHash(contract);
  if (actualHash !== contract.approval.contractHash) throw new Error("Task contract hash mismatch");
  if (!contract.base?.changeId || !contract.base?.commitId || !contract.base?.locked) {
    throw new Error("Task contract does not pin a locked Jujutsu base");
  }
  if (!Array.isArray(contract.scope?.inputPaths) || !Array.isArray(contract.scope?.allowedPaths)) {
    throw new Error("Task contract is missing inputPaths or allowedPaths");
  }
  const protectedPaths = contract.scope.allowedPaths.filter((allowed) =>
    CODEX_ONLY_PATHS.some((reserved) => rulesOverlap(allowed, reserved))
  );
  if (protectedPaths.length) {
    throw new Error(`OpenCode scope includes Codex-only paths: ${protectedPaths.join(", ")}`);
  }
  for (const key of ["maxRuntimeMinutes", "maxInputTokens", "maxOutputTokens", "maxCost", "maxCorrectionCycles"]) {
    if (typeof contract.budget?.[key] !== "number" || contract.budget[key] < 0) {
      throw new Error(`Task budget is missing numeric ${key}`);
    }
  }
  if (!Array.isArray(contract.verificationCommands) || contract.verificationCommands.length === 0) {
    throw new Error("Task contract requires structured verification commands");
  }
  for (const command of contract.verificationCommands) validateCommand(command);
  return contract;
}

function rulesOverlap(left, right) {
  const leftPath = normalizePath(left);
  const rightPath = normalizePath(right);
  const leftPrefix = leftPath.endsWith("/**") ? leftPath.slice(0, -3) : null;
  const rightPrefix = rightPath.endsWith("/**") ? rightPath.slice(0, -3) : null;
  if (!leftPrefix && !rightPrefix) return leftPath === rightPath;
  if (leftPrefix && rightPrefix) return leftPrefix.startsWith(rightPrefix) || rightPrefix.startsWith(leftPrefix);
  if (leftPrefix) return rightPath === leftPrefix || rightPath.startsWith(`${leftPrefix}/`);
  return leftPath === rightPrefix || leftPath.startsWith(`${rightPrefix}/`);
}

export function validateCommand(command) {
  if (!command || typeof command.executable !== "string" || !Array.isArray(command.args)) {
    throw new Error("Verification command must contain executable and args");
  }
  if (!Number.isInteger(command.timeoutSeconds) || command.timeoutSeconds <= 0) {
    throw new Error("Verification command requires a positive timeoutSeconds");
  }
  const allowedExecutables = new Set(["node", "python", "uv", "ruff"]);
  if (!allowedExecutables.has(command.executable)) {
    throw new Error(`Verification executable is not approved: ${command.executable}`);
  }
  if (command.args.some((arg) => typeof arg !== "string" || /[\r\n\0]/.test(arg))) {
    throw new Error("Verification arguments must be newline-free strings");
  }
}

export async function readJson(file) {
  return JSON.parse(await readFile(file, "utf8"));
}

export async function atomicWriteJson(file, value) {
  await mkdir(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await rename(temp, file);
}

export function runtimePaths(root, taskId) {
  const base = path.join(root, "orchestration", "runtime");
  return {
    base,
    state: path.join(base, "tasks", `${taskId}.json`),
    lease: path.join(base, "leases", `${taskId}.json`),
    events: path.join(base, "events", `${taskId}.jsonl`),
    rawLog: path.join(base, "logs", `${taskId}.jsonl`),
    supervisorLog: path.join(base, "logs", `${taskId}.supervisor.log`),
    permissionConfig: path.join(base, "permissions", `${taskId}.json`),
    control: path.join(base, "control", `${taskId}.json`)
  };
}

export async function loadRuntimeState(root, taskId) {
  try {
    return await readJson(runtimePaths(root, taskId).state);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

export async function writeRuntimeState(root, taskId, state) {
  state.updatedAt = new Date().toISOString();
  await atomicWriteJson(runtimePaths(root, taskId).state, state);
  return state;
}

export async function transitionState(root, state, to, details = {}) {
  assertTransition(state.status, to);
  const from = state.status;
  Object.assign(state, details, { status: to });
  await writeRuntimeState(root, state.taskId, state);
  await appendEvent(root, state.taskId, { type: "transition", from, to, details });
  return state;
}

export async function appendEvent(root, taskId, event) {
  const file = runtimePaths(root, taskId).events;
  await mkdir(path.dirname(file), { recursive: true });
  await appendFile(file, `${JSON.stringify({ at: new Date().toISOString(), taskId, ...event })}\n`, "utf8");
}

export async function acquireLease(root, taskId, { owner = "supervisor", ttlMs = 90_000 } = {}) {
  const paths = runtimePaths(root, taskId);
  await mkdir(path.dirname(paths.lease), { recursive: true });
  const lease = {
    schemaVersion: 1,
    taskId,
    leaseId: randomUUID(),
    owner,
    pid: process.pid,
    acquiredAt: new Date().toISOString(),
    heartbeatAt: new Date().toISOString(),
    ttlMs
  };
  let handle;
  try {
    handle = await open(paths.lease, "wx");
    await handle.writeFile(`${JSON.stringify(lease, null, 2)}\n`, "utf8");
  } catch (error) {
    if (error.code === "EEXIST") {
      const audit = await auditLease(root, taskId);
      const suffix = audit.stale ? "stale lease requires explicit recovery" : "another supervisor owns the task";
      throw new Error(`Lease conflict for ${taskId}: ${suffix}`);
    }
    throw error;
  } finally {
    await handle?.close();
  }
  return lease;
}

export async function heartbeatLease(root, lease) {
  const paths = runtimePaths(root, lease.taskId);
  const current = await readJson(paths.lease);
  if (current.leaseId !== lease.leaseId) throw new Error("Lease ownership changed");
  lease.heartbeatAt = new Date().toISOString();
  lease.pid = process.pid;
  await atomicWriteJson(paths.lease, lease);
  return lease;
}

export async function releaseLease(root, lease) {
  const file = runtimePaths(root, lease.taskId).lease;
  try {
    const current = await readJson(file);
    if (current.leaseId === lease.leaseId) await rm(file, { force: true });
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

export async function auditLease(root, taskId, now = Date.now()) {
  try {
    const lease = await readJson(runtimePaths(root, taskId).lease);
    const ageMs = now - Date.parse(lease.heartbeatAt);
    const alive = isProcessAlive(lease.pid);
    return { exists: true, lease, ageMs, alive, stale: ageMs > lease.ttlMs || !alive };
  } catch (error) {
    if (error.code === "ENOENT") return { exists: false, stale: true, alive: false, ageMs: Infinity };
    throw error;
  }
}

export function isProcessAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export function normalizePath(value) {
  return value.replaceAll("\\", "/").replace(/^\.\//, "");
}

export function matchesRule(file, rule) {
  const normalizedFile = normalizePath(file);
  const normalizedRule = normalizePath(rule);
  if (normalizedRule.endsWith("/**")) return normalizedFile.startsWith(normalizedRule.slice(0, -3));
  return normalizedFile === normalizedRule;
}

export function findScopeViolations(files, allowedPaths) {
  return files.map(normalizePath).filter((file) => !allowedPaths.some((rule) => matchesRule(file, rule))).sort();
}

export async function estimateInputTokens(workspaceRoot, inputPaths) {
  let bytes = 0;
  for (const rule of inputPaths) {
    const relative = normalizePath(rule).replace(/\/\*\*$/, "");
    const absolute = path.join(workspaceRoot, relative);
    bytes += await sizeRecursive(absolute);
  }
  return Math.ceil(bytes / 4);
}

async function sizeRecursive(target) {
  try {
    const info = await stat(target);
    if (info.isFile()) return info.size;
    if (!info.isDirectory()) return 0;
    const { readdir } = await import("node:fs/promises");
    const entries = await readdir(target, { withFileTypes: true });
    let total = 0;
    for (const entry of entries) total += await sizeRecursive(path.join(target, entry.name));
    return total;
  } catch (error) {
    if (error.code === "ENOENT") return 0;
    throw error;
  }
}

export function createInitialState(taskId, contract) {
  return {
    schemaVersion: 1,
    taskId,
    contractVersion: contract.contractVersion,
    contractHash: contract.approval.contractHash,
    status: "READY",
    owner: "Oasis",
    dispatchAuthorization: null,
    usage: { inputTokens: 0, outputTokens: 0, cost: 0 },
    correctionCycles: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
}
