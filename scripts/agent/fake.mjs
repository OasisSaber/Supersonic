import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";

export function createFakeExecutor(scenario = "success") {
  let calls = 0;
  return {
    async execute({ contract, workspacePath, correction, signal, onUsage }) {
      calls += 1;
      const usage = scenario === "budget"
        ? { inputTokens: contract.budget.maxInputTokens + 1, outputTokens: 1, cost: 0 }
        : { inputTokens: 120, outputTokens: 40, cost: 0.001 };
      onUsage?.(usage);

      if (scenario === "timeout") {
        await new Promise((resolve) => signal.addEventListener("abort", resolve, { once: true }));
        return { exitCode: 143, sessionId: "fake-timeout", usage };
      }
      if (scenario === "interrupted") return { exitCode: 1, sessionId: "fake-interrupted", usage };

      const allowedFile = firstWritableFile(contract.scope.allowedPaths, workspacePath);
      await mkdir(path.dirname(allowedFile), { recursive: true });
      await writeFile(allowedFile, correction ? "corrected\n" : "fake implementation\n", "utf8");

      if (scenario === "scope-violation") {
        await writeFile(path.join(workspacePath, "forbidden-by-contract.txt"), "violation\n", "utf8");
      }
      if (scenario !== "missing-result") {
        const receipt = path.join(workspacePath, contract.resultPath);
        await mkdir(path.dirname(receipt), { recursive: true });
        await writeFile(receipt, `# ${contract.id} fake receipt\n\n- scenario: ${scenario}\n- correction: ${correction}\n`, "utf8");
      }
      return { exitCode: 0, sessionId: "fake-session", usage, permission: { summary: "fake" }, calls };
    }
  };
}

export function createFakeWorkspaceAdapter(workspacePath, options = {}) {
  let baseline = new Map();
  return {
    async checkBase(contract) {
      return options.staleBase
        ? { ok: false, expected: contract.base.commitId, actual: "changed-base" }
        : { ok: true, expected: contract.base.commitId, actual: contract.base.commitId };
    },
    async create(_contract, { recover = false } = {}) {
      await mkdir(workspacePath, { recursive: true });
      if (!recover || baseline.size === 0) baseline = await snapshot(workspacePath);
      return workspacePath;
    },
    async changedPaths() {
      const after = await snapshot(workspacePath);
      const names = new Set([...baseline.keys(), ...after.keys()]);
      return [...names].filter((name) => baseline.get(name) !== after.get(name)).sort();
    }
  };
}

export function createFakeVerifier(sequence = [true]) {
  let index = 0;
  return {
    async run() {
      const ok = sequence[Math.min(index, sequence.length - 1)];
      index += 1;
      return { ok, results: [{ executable: "fake", args: [], exitCode: ok ? 0 : 1, timedOut: false }] };
    }
  };
}

export function createFakeEnvironment(ok = true) {
  return { async check() { return { ok, issues: ok ? [] : ["fake environment drift"] }; } };
}

function firstWritableFile(rules, workspacePath) {
  const rule = rules.find((item) => !item.endsWith(".md")) ?? rules[0];
  const relative = rule.endsWith("/**") ? `${rule.slice(0, -3)}/fake-output.txt` : rule;
  return path.join(workspacePath, relative);
}

async function snapshot(root, current = root, result = new Map()) {
  const entries = await readdir(current, { withFileTypes: true }).catch(() => []);
  for (const entry of entries) {
    const absolute = path.join(current, entry.name);
    if (entry.isDirectory()) await snapshot(root, absolute, result);
    else if (entry.isFile()) {
      const relative = path.relative(root, absolute).replaceAll("\\", "/");
      result.set(relative, createHash("sha256").update(await readFile(absolute)).digest("hex"));
    }
  }
  return result;
}
