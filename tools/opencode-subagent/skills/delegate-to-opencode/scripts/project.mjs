import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export const DATA_DIR = ".opencode-subagent";

export function findProjectRoot(start = process.cwd(), { initialized = true } = {}) {
  let current = path.resolve(start);
  while (true) {
    if (initialized && existsSync(path.join(current, DATA_DIR, "config.json"))) return current;
    if (!initialized && (existsSync(path.join(current, ".jj")) || existsSync(path.join(current, ".git")))) return current;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  throw new Error(initialized
    ? `No initialized OpenCode subagent project found above ${start}; run init first`
    : `No Git or Jujutsu repository found above ${start}`);
}

export async function loadProjectConfig(root) {
  const file = path.join(root, DATA_DIR, "config.json");
  const config = JSON.parse(await readFile(file, "utf8"));
  if (config.schemaVersion !== 1) throw new Error(`Unsupported project config schema: ${config.schemaVersion}`);
  if (!config.userIdentity || !config.model || !config.provider) throw new Error("Project config requires userIdentity, provider, and model");
  if (!Array.isArray(config.verificationExecutables)
      || config.verificationExecutables.some((name) => typeof name !== "string" || !/^[A-Za-z0-9._+-]+$/.test(name))) {
    throw new Error("Project config verificationExecutables must contain simple executable names");
  }
  if (config.verificationBinaries && (typeof config.verificationBinaries !== "object" || Array.isArray(config.verificationBinaries))) {
    throw new Error("Project config verificationBinaries must be an object mapping approved names to trusted paths");
  }
  for (const [name, target] of Object.entries(config.verificationBinaries ?? {})) {
    if (!config.verificationExecutables.includes(name) || typeof target !== "string" || !target.trim()) {
      throw new Error(`Invalid verificationBinaries entry: ${name}`);
    }
  }
  return config;
}

export async function initializeProject(root, options = {}) {
  const data = path.join(root, DATA_DIR);
  if (existsSync(path.join(data, "config.json")) && !options.force) {
    throw new Error(`${DATA_DIR}/config.json already exists; use --force to replace only the generated configuration`);
  }
  const identity = options.identity ?? process.env.USERNAME ?? process.env.USER ?? "local-user";
  const model = options.model ?? "deepseek/deepseek-v4-pro";
  const provider = options.provider ?? model.split("/")[0];
  const config = {
    schemaVersion: 1,
    userIdentity: identity,
    provider,
    model,
    workspaceRoot: null,
    protectedPaths: [],
    verificationExecutables: ["node", "python", "uv", "ruff", "pnpm", "npm", "npx", "cargo", "go", "dotnet", "powershell", "pwsh"],
    verificationBinaries: {},
    binaries: { jj: null, opencode: null }
  };
  await mkdir(path.join(data, "drafts"), { recursive: true });
  await mkdir(path.join(data, "tasks"), { recursive: true });
  await mkdir(path.join(data, "results"), { recursive: true });
  await writeFile(path.join(data, "config.json"), `${JSON.stringify(config, null, 2)}\n`, "utf8");
  await writeFile(path.join(data, ".gitignore"), "runtime/\n", "utf8");
  await writeFile(path.join(data, "contract.example.json"), `${JSON.stringify(contractExample(model), null, 2)}\n`, "utf8");
  return config;
}

function contractExample(model) {
  return {
    schemaVersion: 2,
    contractVersion: 1,
    id: "TASK-0001",
    title: "Replace with a bounded task title",
    lifecycle: "DRAFT",
    riskLevel: "L1",
    authority: "DELEGATABLE",
    executor: "opencode",
    model,
    base: { locked: false, changeId: null, commitId: null },
    approval: { status: "PENDING", approvedBy: null, approvedAt: null, contractHash: null },
    budget: {
      maxRuntimeMinutes: 20,
      maxInputTokens: 100000,
      maxOutputTokens: 20000,
      maxCost: 2,
      maxCorrectionCycles: 1
    },
    scope: {
      inputPaths: ["AGENTS.md"],
      allowedPaths: ["src/**", ".opencode-subagent/results/TASK-0001.md"]
    },
    requirements: ["Describe the required outcome and boundaries."],
    verificationCommands: [
      { executable: "node", args: ["--version"], timeoutSeconds: 10 }
    ],
    resultPath: ".opencode-subagent/results/TASK-0001.md"
  };
}
