import { spawn } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { auditLease, loadRuntimeState, runtimePaths, transitionState } from "./agent/core.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [command, taskId, ...flags] = process.argv.slice(2);

if (!command || !taskId) usage();

if (command === "prepare") {
  const worker = path.join(root, "scripts", "agent-supervisor-worker.mjs");
  const child = spawn(process.execPath, [worker, taskId, "--prepare-only"], { cwd: root, stdio: "inherit", windowsHide: true });
  process.exitCode = await new Promise((resolve) => child.on("close", resolve));
} else if (command === "start") {
  const executor = flags.find((flag) => flag.startsWith("--executor=")) ?? "--executor=opencode";
  const recover = flags.includes("--recover") ? ["--recover"] : [];
  const foreground = flags.includes("--foreground");
  const worker = path.join(root, "scripts", "agent-supervisor-worker.mjs");
  if (foreground) {
    const child = spawn(process.execPath, [worker, taskId, executor, ...recover], { cwd: root, stdio: "inherit", windowsHide: true });
    process.exitCode = await new Promise((resolve) => child.on("close", resolve));
  } else {
    const paths = runtimePaths(root, taskId);
    await mkdir(path.dirname(paths.supervisorLog), { recursive: true });
    const out = openSync(paths.supervisorLog, "a");
    const child = spawn(process.execPath, [worker, taskId, executor, ...recover], {
      cwd: root,
      detached: true,
      windowsHide: true,
      stdio: ["ignore", out, out]
    });
    child.unref();
    closeSync(out);
    console.log(`Supervisor started for ${taskId} (PID ${child.pid}).`);
    console.log(`Use: pnpm agent:status ${taskId}`);
  }
} else if (command === "status") {
  const state = await loadRuntimeState(root, taskId);
  const lease = await auditLease(root, taskId);
  console.log(JSON.stringify({ state, lease }, null, 2));
} else if (command === "audit") {
  const state = await loadRuntimeState(root, taskId);
  if (!state) throw new Error(`No runtime state for ${taskId}`);
  const lease = await auditLease(root, taskId);
  if ((state.status === "RUNNING" || state.status === "CORRECTING" || state.status === "VERIFYING") && lease.stale) {
    await transitionState(root, state, "INTERRUPTED", {
      interruptedReason: lease.exists ? "stale heartbeat or dead supervisor PID" : "missing supervisor lease"
    });
  }
  console.log(JSON.stringify({ state, lease }, null, 2));
} else {
  usage();
}

function usage() {
  console.error("Usage: node scripts/agent-supervisor.mjs <prepare|start|status|audit> TASK-ID [--foreground] [--executor=opencode|fake-success] [--recover]");
  process.exit(2);
}
