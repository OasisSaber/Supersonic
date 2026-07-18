import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import {
  assertVerificationCommandsResolvable,
  buildOpenCodePrompt,
  checkVerificationCommands,
  resolveVerificationExecutable,
  runVerification
} from "../skills/delegate-to-opencode/scripts/adapters.mjs";
import { findBudgetHeadroomReason } from "../skills/delegate-to-opencode/scripts/supervisor.mjs";

test("execution and correction prompts preserve the immutable contract and include the real task", () => {
  const contract = makeContract();
  for (const correction of [false, true]) {
    const prompt = buildOpenCodePrompt(contract, correction, {
      ok: false,
      results: [{ executable: "node", exitCode: 1, stderr: "assertion failed" }]
    });
    assert.match(prompt, /Treat \.agent-contract\/contract\.json.*read-only/i);
    assert.match(prompt, /Never edit, delete, rename, or rewrite \.agent-contract\/\*\*/i);
    assert.match(prompt, /Create scripts\/install\.ps1/);
    assert.match(prompt, /scripts\/\*\*/);
    assert.match(prompt, /\.opencode-subagent\/results\/PROMPT-TEST\.md/);
    assert.match(prompt, /Independent verification commands/);
  }
});

test("trusted verification binary overrides use the same resolver as runtime", async () => {
  const fixture = await makeFixture({
    verificationExecutables: ["powershell"],
    verificationBinaries: { powershell: process.execPath }
  });
  const command = { executable: "powershell", args: ["--version"], timeoutSeconds: 10 };
  assert.equal(resolveVerificationExecutable(fixture.root, "powershell", fixture.config), process.execPath);
  assert.deepEqual(assertVerificationCommandsResolvable(fixture.root, fixture.config, [command]), { powershell: process.execPath });
  const result = await runVerification(fixture.root, { id: "VERIFY-OVERRIDE", verificationCommands: [command] }, fixture.workspace);
  assert.equal(result.ok, true);
  assert.equal(result.results[0].resolvedExecutable, process.execPath);
});

test("unresolved approved verifier is rejected early and returns a structured runtime failure", async () => {
  const name = "definitely-missing-verifier-5f9c";
  const fixture = await makeFixture({ verificationExecutables: [name], verificationBinaries: {} });
  const command = { executable: name, args: ["--version"], timeoutSeconds: 10 };
  const preflight = checkVerificationCommands(fixture.root, fixture.config, [command]);
  assert.equal(preflight.ok, false);
  assert.match(preflight.issues[0], /Unable to resolve approved verification executable/);
  assert.throws(
    () => assertVerificationCommandsResolvable(fixture.root, fixture.config, [command]),
    /Unable to resolve approved verification executable/
  );
  const result = await runVerification(fixture.root, { id: "VERIFY-MISSING", verificationCommands: [command] }, fixture.workspace);
  assert.equal(result.ok, false);
  assert.equal(result.results[0].exitCode, null);
  assert.equal(result.results[0].resolvedExecutable, null);
  assert.match(result.results[0].stderr, /Verification executable unavailable/);
});

test("verification policy drift is structured instead of crashing the supervisor", async () => {
  const fixture = await makeFixture({ verificationExecutables: ["node"], verificationBinaries: {} });
  const command = { executable: "powershell", args: ["-NoProfile", "-Command", "exit 0"], timeoutSeconds: 10 };
  const result = await runVerification(fixture.root, { id: "VERIFY-POLICY-DRIFT", verificationCommands: [command] }, fixture.workspace);
  assert.equal(result.ok, false);
  assert.equal(result.results[0].exitCode, null);
  assert.match(result.results[0].stderr, /Verification executable is not approved/);
});

test("PowerShell resolves and executes on Windows", { skip: process.platform !== "win32" }, async () => {
  const fixture = await makeFixture({ verificationExecutables: ["powershell"], verificationBinaries: {} });
  const resolved = resolveVerificationExecutable(fixture.root, "powershell", fixture.config);
  assert.match(resolved, /powershell(?:\.exe)?$/i);
  const command = { executable: "powershell", args: ["-NoProfile", "-NonInteractive", "-Command", "exit 0"], timeoutSeconds: 10 };
  const result = await runVerification(fixture.root, { id: "VERIFY-POWERSHELL", verificationCommands: [command] }, fixture.workspace);
  assert.equal(result.ok, true, result.results[0]?.stderr);
});

test("PATH-resolved package-manager shims execute without shell-string verification commands", async () => {
  const fixture = await makeFixture({ verificationExecutables: ["pnpm"], verificationBinaries: {} });
  const command = { executable: "pnpm", args: ["--version"], timeoutSeconds: 10 };
  const result = await runVerification(fixture.root, { id: "VERIFY-PNPM", verificationCommands: [command] }, fixture.workspace);
  assert.equal(result.ok, true, result.results[0]?.stderr);
  assert.ok(path.isAbsolute(result.results[0].resolvedExecutable));
});

test("input headroom stops before another model turn can overshoot the contract", () => {
  const budget = { maxInputTokens: 35_000 };
  assert.equal(findBudgetHeadroomReason({ inputTokens: 20_000 }, budget, 8_000), null);
  assert.match(findBudgetHeadroomReason({ inputTokens: 29_000 }, budget, 8_000), /headroom reached/);
});

test("headroom reserve is bounded by the estimated task input", () => {
  const budget = { maxInputTokens: 35_000 };
  assert.equal(findBudgetHeadroomReason({ inputTokens: 32_500 }, budget, 2_000), null);
  assert.match(findBudgetHeadroomReason({ inputTokens: 33_500 }, budget, 2_000), /2000 reserved/);
});

function makeContract() {
  return {
    id: "PROMPT-TEST",
    title: "Implement deployment",
    requirements: ["Create scripts/install.ps1", "Keep the immutable contract unchanged"],
    scope: { allowedPaths: ["scripts/**", ".opencode-subagent/results/PROMPT-TEST.md"] },
    resultPath: ".opencode-subagent/results/PROMPT-TEST.md",
    verificationCommands: [{ executable: "node", args: ["--version"], timeoutSeconds: 10 }]
  };
}

async function makeFixture(overrides) {
  const root = await mkdtemp(path.join(tmpdir(), "opencode-subagent-regression-"));
  const workspace = path.join(root, "workspace");
  const config = {
    schemaVersion: 1,
    userIdentity: "Test User",
    provider: "openai",
    model: "openai/test-model",
    protectedPaths: [],
    binaries: { jj: null, opencode: null },
    ...overrides
  };
  await mkdir(path.join(root, ".opencode-subagent", "runtime", "logs"), { recursive: true });
  await mkdir(workspace, { recursive: true });
  await writeFile(path.join(root, ".opencode-subagent", "config.json"), `${JSON.stringify(config, null, 2)}\n`, "utf8");
  return { root, workspace, config };
}
