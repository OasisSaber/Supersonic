import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { createWriteStream, existsSync } from "node:fs";
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { once } from "node:events";
import { homedir } from "node:os";
import path from "node:path";
import process from "node:process";
import { atomicWriteJson, normalizePath, runtimePaths, validateCommand } from "./core.mjs";

export function resolveJj(root) {
  return process.env.JJ_BIN ?? path.join(root, ".tools", "jj", "jj.exe");
}

export function resolveOpenCode() {
  if (process.env.OPENCODE_BIN) return process.env.OPENCODE_BIN;
  if (process.platform === "win32") {
    const npmRoot = path.join(process.env.APPDATA ?? path.join(homedir(), "AppData", "Roaming"), "npm");
    const native = path.join(npmRoot, "node_modules", "opencode-ai", "bin", "opencode.exe");
    if (existsSync(native)) return native;
    return path.join(npmRoot, "opencode.cmd");
  }
  return "opencode";
}

export function runSync(executable, args, options = {}) {
  const result = spawnSync(executable, args, {
    cwd: options.cwd,
    encoding: "utf8",
    windowsHide: true,
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
  const lock = JSON.parse(await readFile(path.join(root, "orchestration", "environment-lock.json"), "utf8"));
  const issues = [];
  if (process.version !== lock.node) issues.push(`node ${process.version} != ${lock.node}`);
  if (process.platform !== lock.platform || process.arch !== lock.arch) {
    issues.push(`platform ${process.platform}/${process.arch} != ${lock.platform}/${lock.arch}`);
  }

  const config = await readFile(path.join(root, "opencode.json"));
  const configHash = createHash("sha256").update(config).digest("hex");
  if (configHash !== lock.opencodeConfigSha256) issues.push("opencode.json hash changed");

  const jj = resolveJj(root);
  if (!existsSync(jj)) issues.push("Jujutsu binary missing");
  else {
    const version = runSync(jj, ["--version"], { cwd: root }).match(/\d+\.\d+\.\d+/)?.[0];
    if (version !== lock.jujutsu) issues.push(`jj ${version ?? "unknown"} != ${lock.jujutsu}`);
  }

  const opencode = resolveOpenCode();
  if (!existsSync(opencode) && path.isAbsolute(opencode)) issues.push("OpenCode CLI missing");
  else {
    const version = runOpenCodeSync(opencode, ["--version"], root).trim();
    if (version !== lock.opencodeCli) issues.push(`opencode ${version} != ${lock.opencodeCli}`);
    const models = runOpenCodeSync(opencode, ["models", lock.provider], root);
    if (!models.includes(contract.model)) issues.push(`model unavailable: ${contract.model}`);
  }

  return { ok: issues.length === 0, issues, lock, configHash };
}

function runOpenCodeSync(bin, args, cwd) {
  if (process.platform === "win32" && bin.toLowerCase().endsWith(".cmd")) {
    const command = quoteWindowsCommand(bin, args);
    return runSync(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", command], { cwd });
  }
  return runSync(bin, args, { cwd });
}

export function createJjWorkspaceAdapter(root) {
  const jj = resolveJj(root);
  return {
    async checkBase(contract) {
      const actual = runSync(jj, ["--ignore-working-copy", "log", "-r", contract.base.changeId, "--no-graph", "-T", "commit_id"], { cwd: root });
      return { ok: actual === contract.base.commitId, actual, expected: contract.base.commitId };
    },

    async create(contract, { recover = false } = {}) {
      const workspaceRoot = process.env.AGENT_WORKSPACE_ROOT
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
      await writeFile(injectedContract, `${JSON.stringify(contract, null, 2)}\n`, "utf8");
      return destination;
    },

    async changedPaths(workspacePath) {
      const output = runSync(jj, ["diff", "--name-only"], { cwd: workspacePath });
      return output.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map(normalizePath);
    }
  };
}

function toSparsePattern(rule) {
  const normalized = normalizePath(rule);
  return normalized.endsWith("/**") ? normalized.slice(0, -3) : normalized;
}

export async function createTaskPermissionConfig(root, contract) {
  const file = runtimePaths(root, contract.id).permissionConfig;
  const config = {
    $schema: "https://opencode.ai/config.json",
    model: contract.model,
    enabled_providers: ["deepseek"],
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
      const opencode = resolveOpenCode();
      const paths = runtimePaths(root, contract.id);
      await mkdir(path.dirname(paths.rawLog), { recursive: true });
      const permission = await createTaskPermissionConfig(root, contract);
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
  if (correction) {
    const details = JSON.stringify(verification ?? { ok: false, results: [] }, null, 2).slice(0, 6000);
    return [
      "The independent verifier failed. Fix only the reported deterministic failures within the unchanged task contract.",
      "Do not expand scope. Verification details:",
      details
    ].join("\n");
  }
  return [
    `Execute the approved immutable contract for ${contract.id}.`,
    "Read .agent-contract/contract.json and the checked-out AGENTS.md files.",
    "Edit only scope.allowedPaths. Do not run shell, Git, Jujutsu, web tools, or subagents.",
    "Write the required result receipt and stop. If blocked, explain without guessing."
  ].join(" ");
}

function spawnOpenCode(bin, args, cwd, env) {
  if (process.platform === "win32" && bin.toLowerCase().endsWith(".cmd")) {
    const command = quoteWindowsCommand(bin, args);
    return spawn(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", command], {
      cwd, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"]
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
  return [quote(bin), ...args.map(quote)].join(" ");
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
  const results = [];
  const allowed = new Map([
    ["node", process.execPath],
    ["python", process.env.PYTHON_BIN ?? "python"],
    ["uv", process.env.UV_BIN ?? "uv"],
    ["ruff", process.env.RUFF_BIN ?? "ruff"]
  ]);
  for (const command of contract.verificationCommands) {
    validateCommand(command);
    const executable = allowed.get(command.executable);
    const startedAt = Date.now();
    const result = await runProcess(executable, command.args, workspacePath, command.timeoutSeconds * 1000);
    const record = {
      executable: command.executable,
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

async function runProcess(executable, args, cwd, timeoutMs) {
  const child = spawn(executable, args, { cwd, shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    terminateProcessTree(child);
  }, timeoutMs);
  const exitCode = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", resolve);
  });
  clearTimeout(timeout);
  return { exitCode, timedOut, stdout: Buffer.concat(stdout).toString("utf8"), stderr: Buffer.concat(stderr).toString("utf8") };
}
