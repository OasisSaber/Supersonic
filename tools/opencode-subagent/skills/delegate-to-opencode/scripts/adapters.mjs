import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { createWriteStream, existsSync } from "node:fs";
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { once } from "node:events";
import { homedir } from "node:os";
import path from "node:path";
import process from "node:process";
import { atomicWriteJson, normalizePath, runtimePaths, validateCommand } from "./core.mjs";
import { loadProjectConfig } from "./project.mjs";

export function resolveJj(root, config = {}) {
  if (process.env.JJ_BIN) return process.env.JJ_BIN;
  if (config.binaries?.jj) return path.resolve(root, config.binaries.jj);
  const local = path.join(root, ".tools", "jj", process.platform === "win32" ? "jj.exe" : "jj");
  return existsSync(local) ? local : "jj";
}

export function resolveOpenCode(root, config = {}) {
  if (process.env.OPENCODE_BIN) return process.env.OPENCODE_BIN;
  if (config.binaries?.opencode) return path.resolve(root, config.binaries.opencode);
  if (process.platform === "win32") {
    const npmRoot = path.join(process.env.APPDATA ?? path.join(homedir(), "AppData", "Roaming"), "npm");
    const native = path.join(npmRoot, "node_modules", "opencode-ai", "bin", "opencode.exe");
    if (existsSync(native)) return native;
    const npmShim = path.join(npmRoot, "opencode.cmd");
    if (existsSync(npmShim)) return npmShim;
    return "opencode";
  }
  return "opencode";
}

export function runSync(executable, args, options = {}) {
  const result = spawnSync(executable, args, {
    cwd: options.cwd,
    encoding: "utf8",
    windowsHide: true,
    windowsVerbatimArguments: options.windowsVerbatimArguments === true,
    shell: false,
    env: options.env ?? process.env
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${path.basename(executable)} failed (${result.status}): ${(result.stderr || result.stdout).trim()}`);
  }
  return result.stdout.trim();
}

export async function checkEnvironment(root, contract) {
  const config = await loadProjectConfig(root);
  const issues = [];
  const jj = resolveJj(root, config);
  try {
    const version = runSync(jj, ["--version"], { cwd: root }).match(/\d+\.\d+\.\d+/)?.[0];
    if (!version) issues.push("unable to determine Jujutsu version");
  } catch (error) {
    issues.push(`Jujutsu unavailable: ${error.message}`);
  }

  const opencode = resolveOpenCode(root, config);
  try {
    const version = runOpenCodeSync(opencode, ["--version"], root).trim();
    if (!version) issues.push("unable to determine OpenCode version");
    const models = runOpenCodeSync(opencode, ["models", config.provider], root);
    if (!models.includes(contract.model)) issues.push(`model unavailable: ${contract.model}`);
  } catch (error) {
    issues.push(`OpenCode unavailable: ${error.message}`);
  }

  const verification = checkVerificationCommands(root, config, contract.verificationCommands ?? []);
  issues.push(...verification.issues);

  return {
    ok: issues.length === 0,
    issues,
    node: process.version,
    platform: process.platform,
    arch: process.arch,
    verification: verification.resolved
  };
}

function runOpenCodeSync(bin, args, cwd) {
  if (process.platform === "win32" && bin.toLowerCase().endsWith(".cmd")) {
    const command = quoteWindowsCommand(bin, args);
    return runSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", command], { cwd, windowsVerbatimArguments: true });
  }
  return runSync(bin, args, { cwd });
}

export function createJjWorkspaceAdapter(root, config = {}) {
  const jj = resolveJj(root, config);
  const injectedHashes = new Map();
  return {
    async checkBase(contract) {
      const actual = runSync(jj, ["--ignore-working-copy", "log", "-r", contract.base.changeId, "--no-graph", "-T", "commit_id"], { cwd: root });
      return { ok: actual === contract.base.commitId, actual, expected: contract.base.commitId };
    },

    async create(contract, { recover = false } = {}) {
      const workspaceRoot = process.env.AGENT_WORKSPACE_ROOT ?? (config.workspaceRoot && path.resolve(root, config.workspaceRoot))
        ?? path.join(path.dirname(root), `${path.basename(root)}.agent-workspaces`);
      const destination = path.join(workspaceRoot, `${contract.id}-v${contract.contractVersion}`);
      if (existsSync(destination)) {
        if (!recover) throw new Error(`Task workspace already exists: ${destination}`);
        return destination;
      }
      await mkdir(workspaceRoot, { recursive: true });
      const name = `agent-${contract.id.toLowerCase()}-v${contract.contractVersion}`;
      runSync(jj, [
        "workspace", "add", destination,
        "--name", name,
        "-r", contract.base.commitId,
        "-m", `task(${contract.id}): ${contract.title}`,
        "--sparse-patterns", "empty"
      ], { cwd: root });

      const patterns = [...new Set([
        ...contract.scope.inputPaths,
        ...contract.scope.allowedPaths
      ].map(toSparsePattern))];
      const args = ["-R", destination, "sparse", "set", "--clear"];
      for (const pattern of patterns) args.push("--add", pattern);
      runSync(jj, args, { cwd: root });
      const injectedContract = path.join(destination, ".agent-contract", "contract.json");
      await mkdir(path.dirname(injectedContract), { recursive: true });
      const injectedContent = `${JSON.stringify(contract, null, 2)}\n`;
      await writeFile(injectedContract, injectedContent, "utf8");
      injectedHashes.set(destination, createHash("sha256").update(injectedContent).digest("hex"));
      return destination;
    },

    async changedPaths(workspacePath) {
      const injectedContract = path.join(workspacePath, ".agent-contract", "contract.json");
      const expectedHash = injectedHashes.get(workspacePath);
      if (expectedHash) {
        const actualHash = createHash("sha256").update(await readFile(injectedContract)).digest("hex");
        if (actualHash !== expectedHash) throw new Error("Injected immutable contract was modified");
      }
      const output = runSync(jj, ["diff", "--name-only"], { cwd: workspacePath });
      return output.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map(normalizePath)
        .filter((file) => file !== ".agent-contract/contract.json");
    }
  };
}

function toSparsePattern(rule) {
  const normalized = normalizePath(rule);
  return normalized.endsWith("/**") ? normalized.slice(0, -3) : normalized;
}

export async function createTaskPermissionConfig(root, contract, projectConfig = {}) {
  const file = runtimePaths(root, contract.id).permissionConfig;
  const config = {
    $schema: "https://opencode.ai/config.json",
    model: contract.model,
    enabled_providers: [projectConfig.provider ?? contract.model.split("/")[0]],
    share: "disabled",
    snapshot: false,
    autoupdate: false,
    subagent_depth: 0,
    permission: {
      read: "allow",
      edit: "allow",
      glob: "allow",
      grep: "allow",
      list: "allow",
      lsp: "allow",
      external_directory: "deny",
      task: "deny",
      webfetch: "deny",
      websearch: "deny",
      bash: { "*": "deny" }
    }
  };
  await atomicWriteJson(file, config);
  return {
    file,
    sha256: createHash("sha256").update(JSON.stringify(config)).digest("hex"),
    summary: "sparse read set; scoped write audit; no shell, web, external directory, or subagents"
  };
}

export function createOpenCodeExecutor(root) {
  return {
    async execute({ contract, workspacePath, sessionId, correction, verification, signal, onUsage }) {
      const projectConfig = await loadProjectConfig(root);
      const opencode = resolveOpenCode(root, projectConfig);
      const paths = runtimePaths(root, contract.id);
      await mkdir(path.dirname(paths.rawLog), { recursive: true });
      const permission = await createTaskPermissionConfig(root, contract, projectConfig);
      const prompt = buildOpenCodePrompt(contract, correction, verification);
      const args = ["run", "--pure", "--format", "json", "--model", contract.model, "--dir", workspacePath];
      if (sessionId) args.push("--session", sessionId);
      args.push("--title", `${contract.id} ${contract.title}`, prompt);
      const env = { ...process.env, OPENCODE_CONFIG: permission.file };
      const child = spawnOpenCode(opencode, args, workspacePath, env);
      signal?.addEventListener("abort", () => terminateProcessTree(child), { once: true });

      let buffer = "";
      let resolvedSession = sessionId ?? null;
      let usage = { inputTokens: 0, outputTokens: 0, cost: 0 };
      let usageEvents = 0;
      const rawStream = createWriteStream(paths.rawLog, { flags: "a" });
      const errorStream = createWriteStream(paths.supervisorLog, { flags: "a" });
      const processLine = (line) => {
        if (!line.trim()) return;
        try {
          const event = JSON.parse(line);
          resolvedSession ??= findFirst(event, ["sessionID", "sessionId", "session_id"]);
          const delta = extractUsage(event);
          if (delta) {
            usageEvents += 1;
            usage = {
              inputTokens: usage.inputTokens + delta.inputTokens,
              outputTokens: usage.outputTokens + delta.outputTokens,
              cost: usage.cost + delta.cost
            };
            onUsage?.(usage);
          }
        } catch {
          // The raw log is authoritative; malformed lines are ignored by the usage summarizer.
        }
      };
      child.stdout.on("data", (chunk) => {
        rawStream.write(chunk);
        buffer += chunk.toString("utf8");
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() ?? "";
        for (const line of lines) processLine(line);
      });
      child.stderr.on("data", (chunk) => errorStream.write(chunk));
      const exitCode = await new Promise((resolve, reject) => {
        child.on("error", reject);
        child.on("close", resolve);
      });
      if (buffer.trim()) processLine(buffer);
      rawStream.end();
      errorStream.end();
      await Promise.all([once(rawStream, "finish"), once(errorStream, "finish")]);
      return { exitCode, sessionId: resolvedSession, usage, usageReported: usageEvents > 0, permission };
    }
  };
}

export function buildOpenCodePrompt(contract, correction, verification) {
  const task = [
    `Execute the approved immutable task ${contract.id}: ${contract.title}.`,
    "Treat .agent-contract/contract.json and every checked-out AGENTS.md as read-only policy inputs.",
    "Never edit, delete, rename, or rewrite .agent-contract/**, AGENTS.md, the task scope, or the task requirements.",
    `The only writable paths are: ${JSON.stringify(contract.scope.allowedPaths)}.`,
    "Interpret that list as a permission boundary, not as content to modify. Implement the requirements in the permitted project files.",
    `Requirements: ${JSON.stringify(contract.requirements ?? [])}.`,
    `Required result receipt: ${contract.resultPath}.`,
    `Independent verification commands: ${JSON.stringify(contract.verificationCommands ?? [])}.`,
    "Do not run shell, Git, Jujutsu, web tools, or subagents. Do not broaden scope. If blocked, explain without guessing."
  ];
  if (correction) {
    const details = JSON.stringify(verification ?? { ok: false, results: [] }, null, 2).slice(0, 6000);
    task.push(
      "The independent verifier failed. Fix only the reported deterministic failures while preserving the immutable contract and writable-path boundary.",
      `Verification details: ${details}`
    );
  }
  return task.join("\n");
}

function spawnOpenCode(bin, args, cwd, env) {
  if (process.platform === "win32" && bin.toLowerCase().endsWith(".cmd")) {
    const command = quoteWindowsCommand(bin, args);
    return spawn(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", command], {
      cwd, env, windowsHide: true, windowsVerbatimArguments: true, stdio: ["ignore", "pipe", "pipe"]
    });
  }
  return spawn(bin, args, { cwd, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
}

function terminateProcessTree(child) {
  if (!child?.pid) return;
  if (process.platform === "win32") {
    const killer = spawn("taskkill.exe", ["/pid", String(child.pid), "/t", "/f"], {
      windowsHide: true,
      stdio: "ignore"
    });
    killer.on("error", () => child.kill());
    return;
  }
  child.kill("SIGTERM");
}

function quoteWindowsCommand(bin, args) {
  const quote = (value) => `"${String(value).replaceAll('"', '\\"')}"`;
  return `"${[quote(bin), ...args.map(quote)].join(" ")}"`;
}

function findFirst(value, keys) {
  if (!value || typeof value !== "object") return null;
  for (const key of keys) if (typeof value[key] === "string") return value[key];
  for (const child of Object.values(value)) {
    const found = findFirst(child, keys);
    if (found) return found;
  }
  return null;
}

function extractUsage(event) {
  const part = event.part ?? event.properties?.part ?? event.data?.part;
  if (!part || !/step.*finish/i.test(String(event.type ?? part.type ?? ""))) return null;
  const tokens = part.tokens ?? event.tokens;
  if (!tokens) return null;
  return {
    inputTokens: Number(tokens.input ?? tokens.inputTokens ?? 0),
    outputTokens: Number(tokens.output ?? tokens.outputTokens ?? 0),
    cost: Number(part.cost ?? event.cost ?? 0)
  };
}

export async function runVerification(root, contract, workspacePath) {
  const config = await loadProjectConfig(root);
  const results = [];
  for (const command of contract.verificationCommands) {
    const startedAt = Date.now();
    let result;
    let resolvedExecutable = null;
    try {
      validateCommand(command, config);
      resolvedExecutable = resolveVerificationExecutable(root, command.executable, config);
      result = await runProcess(resolvedExecutable, command.args, workspacePath, command.timeoutSeconds * 1000);
    } catch (error) {
      result = {
        exitCode: null,
        timedOut: false,
        stdout: "",
        stderr: `Verification executable unavailable: ${error.message}`,
        spawnError: error.message
      };
    }
    const record = {
      executable: command.executable,
      resolvedExecutable,
      args: command.args,
      exitCode: result.exitCode,
      timedOut: result.timedOut,
      durationMs: Date.now() - startedAt,
      stdout: result.stdout.slice(-4000),
      stderr: result.stderr.slice(-4000)
    };
    results.push(record);
    await appendFile(runtimePaths(root, contract.id).supervisorLog, `${JSON.stringify({ type: "verification", ...record })}\n`);
    if (record.exitCode !== 0 || record.timedOut) break;
  }
  return { ok: results.length === contract.verificationCommands.length && results.every((item) => item.exitCode === 0 && !item.timedOut), results };
}

export function resolveVerificationExecutable(root, name, config = {}) {
  if (typeof name !== "string" || !/^[A-Za-z0-9._+-]+$/.test(name)) {
    throw new Error(`Invalid verification executable name: ${name}`);
  }
  if (!(config.verificationExecutables ?? []).includes(name)) {
    throw new Error(`Verification executable is not approved: ${name}`);
  }
  const override = config.verificationBinaries?.[name];
  if (override) {
    const resolved = path.isAbsolute(override) ? override : path.resolve(root, override);
    if (!existsSync(resolved)) throw new Error(`Configured verification binary does not exist: ${resolved}`);
    return resolved;
  }
  if (name === "node") return process.execPath;
  const envName = `${name.replace(/[^A-Za-z0-9]/g, "_").toUpperCase()}_BIN`;
  if (process.env[envName]) {
    const resolved = path.resolve(process.env[envName]);
    if (!existsSync(resolved)) throw new Error(`${envName} does not exist: ${resolved}`);
    return resolved;
  }
  const locator = process.platform === "win32" ? "where.exe" : "which";
  const lookup = spawnSync(locator, [name], { cwd: root, encoding: "utf8", windowsHide: true, shell: false });
  const resolved = lookup.status === 0
    ? lookup.stdout.split(/\r?\n/).map((line) => line.trim()).find((line) => line && existsSync(line))
    : null;
  if (!resolved) throw new Error(`Unable to resolve approved verification executable '${name}' on PATH`);
  return resolved;
}

export function checkVerificationCommands(root, config, commands = []) {
  const resolved = {};
  const issues = [];
  for (const command of commands) {
    try {
      validateCommand(command, config);
      resolved[command.executable] ??= resolveVerificationExecutable(root, command.executable, config);
    } catch (error) {
      issues.push(`Verification command '${command?.executable ?? "unknown"}' unavailable: ${error.message}`);
    }
  }
  return { ok: issues.length === 0, issues, resolved };
}

export function assertVerificationCommandsResolvable(root, config, commands = []) {
  const result = checkVerificationCommands(root, config, commands);
  if (!result.ok) throw new Error(result.issues.join("; "));
  return result.resolved;
}

async function runProcess(executable, args, cwd, timeoutMs) {
  if (typeof executable !== "string" || !executable.trim()) {
    return { exitCode: null, timedOut: false, stdout: "", stderr: "Verification executable resolved to an empty path", spawnError: "empty executable" };
  }
  let child;
  try {
    child = spawnVerificationProcess(executable, args, cwd);
  } catch (error) {
    return { exitCode: null, timedOut: false, stdout: "", stderr: error.message, spawnError: error.message };
  }
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    terminateProcessTree(child);
  }, timeoutMs);
  let spawnError = null;
  const exitCode = await new Promise((resolve) => {
    child.on("error", (error) => {
      spawnError = error;
      resolve(null);
    });
    child.on("close", resolve);
  });
  clearTimeout(timeout);
  return {
    exitCode,
    timedOut,
    stdout: Buffer.concat(stdout).toString("utf8"),
    stderr: spawnError?.message ?? Buffer.concat(stderr).toString("utf8"),
    spawnError: spawnError?.message ?? null
  };
}

function spawnVerificationProcess(executable, args, cwd) {
  if (process.platform === "win32" && /\.(cmd|bat)$/i.test(executable)) {
    return spawn(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", quoteWindowsVerificationCommand(executable, args)], {
      cwd, shell: false, windowsHide: true, windowsVerbatimArguments: true, stdio: ["ignore", "pipe", "pipe"]
    });
  }
  return spawn(executable, args, { cwd, shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
}

function quoteWindowsVerificationCommand(executable, args) {
  const values = [executable, ...args].map((value) => String(value));
  const unsafe = values.find((value) => /["%\r\n\0]/.test(value));
  if (unsafe !== undefined) {
    throw new Error("Windows .cmd/.bat verification arguments cannot contain quotes, percent expansion, or control characters");
  }
  const quoted = values.map((value) => `"${value}"`).join(" ");
  return `"${quoted}"`;
}
