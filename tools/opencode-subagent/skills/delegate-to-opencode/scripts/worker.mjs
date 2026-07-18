import path from "node:path";
import process from "node:process";
import { runSupervisor } from "./supervisor.mjs";
import { createFakeEnvironment, createFakeExecutor, createFakeVerifier, createFakeWorkspaceAdapter } from "./fake.mjs";

const taskId = process.argv[2];
const root = process.argv.find((arg) => arg.startsWith("--root="))?.slice("--root=".length);
const executorMode = process.argv.find((arg) => arg.startsWith("--executor="))?.slice("--executor=".length) ?? "opencode";
if (!taskId || !root) throw new Error("worker requires TASK-ID and --root");

const options = { root: path.resolve(root), taskId, recover: process.argv.includes("--recover") };
if (executorMode.startsWith("fake-")) {
  const scenario = executorMode.slice(5);
  Object.assign(options, {
    executor: createFakeExecutor(scenario),
    environment: createFakeEnvironment(true),
    workspace: createFakeWorkspaceAdapter(path.join(root, ".opencode-subagent", "runtime", "fake-workspaces", taskId)),
    verifier: createFakeVerifier([true])
  });
}

try {
  const state = await runSupervisor(options);
  console.log(JSON.stringify({ taskId, status: state.status }));
} catch (error) {
  console.error(error.stack ?? error.message);
  process.exitCode = 1;
}
