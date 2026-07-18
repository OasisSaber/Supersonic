import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { appendEvent, atomicWriteJson, loadRuntimeState, runtimePaths, transitionState, writeRuntimeState } from "./agent/core.mjs";

const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [actionInput, taskId, ...flags] = process.argv.slice(2);
const action = actionInput?.toUpperCase();
const root = flags.find((flag) => flag.startsWith("--root="))?.slice("--root=".length) ?? defaultRoot;

if (!action || !taskId) usage();
if (!flags.includes(`--confirm=${taskId}`)) {
  console.error(`Confirmation required. Re-run with --confirm=${taskId}`);
  process.exit(2);
}

const state = await loadRuntimeState(root, taskId);
if (!state) throw new Error(`No runtime state for ${taskId}`);

if (action === "DISPATCH") {
  if (state.status !== "READY") throw new Error(`DISPATCH requires READY, got ${state.status}`);
  state.dispatchAuthorization = {
    action: "DISPATCH",
    authorizedBy: "Oasis",
    authorizedAt: new Date().toISOString(),
    usedAt: null
  };
  await writeRuntimeState(root, taskId, state);
  await appendEvent(root, taskId, { type: "dispatch-authorized", authorizedBy: "Oasis" });
  console.log(`DISPATCH authorized for ${taskId}. Start with: pnpm agent:start ${taskId}`);
  process.exit(0);
}

if (action === "RESUME" || action === "RETRY") {
  if (state.status !== "INTERRUPTED") throw new Error(`${action} requires INTERRUPTED, got ${state.status}`);
  if (action === "RESUME" && !state.sessionId) throw new Error("RESUME requires a recorded OpenCode sessionId; use RETRY instead");
  state.recoveryAuthorization = {
    action,
    authorizedBy: "Oasis",
    authorizedAt: new Date().toISOString(),
    usedAt: null
  };
  await writeRuntimeState(root, taskId, state);
  await appendEvent(root, taskId, { type: "recovery-authorized", action, authorizedBy: "Oasis" });
  console.log(`${action} authorized for ${taskId}. Start with: pnpm agent:start ${taskId} --recover`);
  process.exit(0);
}

if (action === "STOP") {
  await atomicWriteJson(runtimePaths(root, taskId).control, {
    schemaVersion: 1,
    taskId,
    action: "STOP",
    requestedBy: "Oasis",
    requestedAt: new Date().toISOString()
  });
  await appendEvent(root, taskId, { type: "user-control", action: "STOP", requestedBy: "Oasis" });
  console.log(`STOP requested for ${taskId}; Supervisor will preserve the workspace and mark it INTERRUPTED.`);
  process.exit(0);
}

const targets = {
  ACCEPT: state.status === "USER_OWNED" ? "READY_TO_INTEGRATE" : "AWAITING_CODEX_REVIEW",
  REVIEW: "READY_TO_INTEGRATE",
  INTEGRATED: "INTEGRATED",
  PUSHED: "PUSHED",
  RETURN: "RETURNED",
  TAKEOVER: "USER_OWNED",
  CANCEL: "CANCELLED"
};
const target = targets[action];
if (!target) usage();

if (action === "INTEGRATED" && (!flagValue("--change=") || !flagValue("--commit="))) {
  throw new Error("INTEGRATED requires --change=<id> and --commit=<id>");
}
if (action === "PUSHED" && !flagValue("--remote=")) {
  throw new Error("PUSHED requires --remote=<name/ref>");
}

await transitionState(root, state, target, {
  userDecision: {
    action,
    decidedBy: "Oasis",
    decidedAt: new Date().toISOString()
  },
  owner: action === "TAKEOVER" ? "Oasis" : state.owner,
  ...(action === "REVIEW" ? { codexReview: { status: "approved", reviewedAt: new Date().toISOString() } } : {}),
  ...(action === "INTEGRATED" ? { integration: { changeId: flagValue("--change="), commitId: flagValue("--commit="), integratedAt: new Date().toISOString() } } : {}),
  ...(action === "PUSHED" ? { push: { remote: flagValue("--remote="), pushedAt: new Date().toISOString() } } : {}),
  ...(action === "TAKEOVER" ? {
    takeoverReceipt: {
      workspacePath: state.workspacePath ?? null,
      changedPaths: state.changedPaths ?? [],
      verification: state.verification ?? null,
      recordedAt: new Date().toISOString()
    }
  } : {})
});
console.log(`${taskId}: ${action} -> ${target}`);
if (action === "TAKEOVER") console.log(JSON.stringify(state.takeoverReceipt, null, 2));

function usage() {
  console.error("Usage: node scripts/agent-control.mjs <dispatch|accept|review|integrated|pushed|return|takeover|cancel|stop|resume|retry> TASK-ID --confirm=TASK-ID");
  process.exit(2);
}

function flagValue(prefix) {
  return flags.find((flag) => flag.startsWith(prefix))?.slice(prefix.length) ?? null;
}
