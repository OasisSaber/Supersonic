import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { computeContractHash, readJson, atomicWriteJson, selectExecutorModel, validateActiveContract } from "./agent/core.mjs";
import { resolveJj, runSync } from "./agent/adapters.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [actionInput, taskId, ...flags] = process.argv.slice(2);
const action = actionInput?.toUpperCase();

if (action !== "APPROVE" || !taskId || !flags.includes(`--confirm=${taskId}`)) usage();

const draftPath = path.join(root, "orchestration", "drafts", `${taskId}.json`);
const taskPath = path.join(root, "orchestration", "tasks", `${taskId}.json`);
const draft = await readJson(draftPath);
if (draft.id !== taskId || draft.lifecycle !== "DRAFT" || draft.approval?.status !== "PENDING") {
  throw new Error("Only a matching PENDING DRAFT can be approved");
}

const jj = resolveJj(root);
const baseRevision = flags.find((flag) => flag.startsWith("--base="))?.slice("--base=".length) ?? "@-";
const changeId = runSync(jj, ["--ignore-working-copy", "log", "-r", baseRevision, "--no-graph", "-T", "change_id"], { cwd: root });
const commitId = runSync(jj, ["--ignore-working-copy", "log", "-r", baseRevision, "--no-graph", "-T", "commit_id"], { cwd: root });

const contract = structuredClone(draft);
contract.lifecycle = "ACTIVE";
contract.base = { locked: true, changeId, commitId };
const modelSelection = selectExecutorModel(contract.complexity);
contract.complexity = modelSelection.complexity;
contract.model = modelSelection.model;
contract.modelPolicy = {
  version: 1,
  selectedBy: "codex-contract-approval",
  defaultApplied: modelSelection.defaultApplied
};
contract.approval = {
  status: "APPROVED",
  approvedBy: "Oasis",
  approvedAt: new Date().toISOString(),
  contractHash: null
};
contract.approval.contractHash = computeContractHash(contract);
validateActiveContract(contract, taskId);
await atomicWriteJson(taskPath, contract);

draft.lifecycle = "PROMOTED";
draft.approval = {
  status: "PROMOTED",
  approvedBy: "Oasis",
  approvedAt: contract.approval.approvedAt,
  contractHash: contract.approval.contractHash
};
draft.promotedTo = `orchestration/tasks/${taskId}.json`;
await atomicWriteJson(draftPath, draft);

console.log(JSON.stringify({
  taskId,
  taskPath,
  complexity: contract.complexity,
  model: contract.model,
  modelPolicy: contract.modelPolicy,
  base: contract.base,
  contractHash: contract.approval.contractHash
}, null, 2));

function usage() {
  console.error("Usage: node scripts/task-contract.mjs approve TASK-ID --confirm=TASK-ID [--base=REVSET]");
  process.exit(2);
}
