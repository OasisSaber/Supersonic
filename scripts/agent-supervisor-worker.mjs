import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { runSupervisor } from "./agent/supervisor.mjs";
import { createFakeEnvironment, createFakeExecutor, createFakeVerifier, createFakeWorkspaceAdapter } from "./agent/fake.mjs";

const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const taskId = process.argv[2];
const mode = process.argv.find((arg) => arg.startsWith("--executor="))?.split("=")[1] ?? "opencode";
const root = process.argv.find((arg) => arg.startsWith("--root="))?.slice("--root=".length) ?? defaultRoot;
const recover = process.argv.includes("--recover");
const prepareOnly = process.argv.includes("--prepare-only");

if (!taskId) throw new Error("Missing task id");

const options = { root, taskId, recover, prepareOnly };
if (mode.startsWith("fake-")) {
  const scenario = mode.slice(5);
  const workspacePath = path.join(root, "orchestration", "runtime", "fake-workspaces", taskId);
  Object.assign(options, {
    executor: createFakeExecutor(scenario),
    environment: createFakeEnvironment(true),
    workspace: createFakeWorkspaceAdapter(workspacePath),
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
