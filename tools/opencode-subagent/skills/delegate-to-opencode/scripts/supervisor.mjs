import { existsSync } from "node:fs";
import { mkdir, readFile, rm } from "node:fs/promises";
import path from "node:path";
import {
  acquireLease,
  appendEvent,
  createInitialState,
  estimateInputTokens,
  findScopeViolations,
  heartbeatLease,
  loadRuntimeState,
  readJson,
  releaseLease,
  runtimePaths,
  transitionState,
  validateActiveContract,
  writeRuntimeState
} from "./core.mjs";
import {
  checkEnvironment,
  createJjWorkspaceAdapter,
  createOpenCodeExecutor,
  runVerification
} from "./adapters.mjs";
import { loadProjectConfig } from "./project.mjs";

export async function runSupervisor(options) {
  const root = options.root;
  const taskId = options.taskId;
  const config = await loadProjectConfig(root);
  const contractPath = path.join(root, ".opencode-subagent", "tasks", `${taskId}.json`);
  const contract = validateActiveContract(await readJson(contractPath), taskId, config);
  const environment = options.environment ?? { check: () => checkEnvironment(root, contract) };
  const workspace = options.workspace ?? createJjWorkspaceAdapter(root, config);
  const executor = options.executor ?? createOpenCodeExecutor(root);
  const verifier = options.verifier ?? { run: () => runVerification(root, contract, state.workspacePath) };
  const paths = runtimePaths(root, taskId);

  let state = await loadRuntimeState(root, taskId);
  if (!state) {
    state = createInitialState(taskId, contract);
    await writeRuntimeState(root, taskId, state);
    await appendEvent(root, taskId, { type: "runtime-created", contractHash: state.contractHash });
  }
  if (state.contractHash !== contract.approval.contractHash) {
    throw new Error("Runtime state belongs to a different contract version");
  }
  if (options.prepareOnly === true) return state;
  const recover = options.recover === true;
  if (state.status !== "READY" && !(recover && state.status === "INTERRUPTED")) {
    throw new Error(`Task cannot start from ${state.status}`);
  }
  if (recover) {
    const authorization = state.recoveryAuthorization;
    if (!authorization || authorization.authorizedBy !== config.userIdentity || authorization.usedAt
        || !["RESUME", "RETRY"].includes(authorization.action)) {
      throw new Error("Interrupted task requires an unused user RESUME or RETRY authorization");
    }
    authorization.usedAt = new Date().toISOString();
    state.owner = "supervisor";
    await writeRuntimeState(root, taskId, state);
  } else {
    const authorization = state.dispatchAuthorization;
    if (!authorization || authorization.action !== "DISPATCH" || authorization.authorizedBy !== config.userIdentity || authorization.usedAt) {
      throw new Error("READY task requires an unused user DISPATCH authorization");
    }
    authorization.usedAt = new Date().toISOString();
    state.owner = "supervisor";
    await writeRuntimeState(root, taskId, state);
  }

  const lease = await acquireLease(root, taskId, { ttlMs: options.leaseTtlMs ?? 90_000 });
  let heartbeatTimer;
  let heartbeatInFlight = Promise.resolve();
  let budgetTimer;
  let stopRequested = null;
  let budgetReason = null;
  let cumulativeUsage = normalizeUsage(state.usage);
  const abortController = new AbortController();
  const singleApproval = contract.approval.mode === "SINGLE_APPROVAL";

  const pause = async (status, details = {}) => {
    await transitionState(root, state, status, details);
    if (singleApproval) {
      await transitionState(root, state, "AWAITING_CODEX_REVIEW", {
        owner: "codex",
        reviewOutcome: status,
        reviewReason: details.reason ?? details.budgetReason ?? details.interruptedReason ?? null,
        nextActions: ["CODEX_REVIEW"]
      });
    }
    return state;
  };

  try {
    const environmentResult = await environment.check(contract);
    state.environment = environmentResult;
    if (!environmentResult.ok) {
      return pause("ENVIRONMENT_DRIFT", { issues: environmentResult.issues, reason: "environment drift" });
    }

    const base = await workspace.checkBase(contract);
    state.baseAudit = base;
    if (!base.ok) {
      return pause("STALE_BASE", { expected: base.expected, actual: base.actual, reason: "stale base" });
    }

    state.workspacePath = await workspace.create(contract, { recover });
    const estimatedInputTokens = await estimateInputTokens(state.workspacePath, contract.scope.inputPaths);
    state.estimatedInputTokens = estimatedInputTokens;
    if (estimatedInputTokens > contract.budget.maxInputTokens) {
      return pause("BUDGET_REVIEW", {
        reason: `estimated input ${estimatedInputTokens} exceeds ${contract.budget.maxInputTokens}`
      });
    }

    await transitionState(root, state, "RUNNING", {
      leaseId: lease.leaseId,
      supervisorPid: process.pid,
      startedAt: new Date().toISOString(),
      interruptedReason: null
    });

    heartbeatTimer = setInterval(() => {
      heartbeatInFlight = heartbeatInFlight.then(async () => {
        try {
          await heartbeatLease(root, lease);
          state.heartbeatAt = lease.heartbeatAt;
          await writeRuntimeState(root, taskId, state);
          const control = await readControl(paths.control);
          if (control && !stopRequested) {
            stopRequested = control;
            abortController.abort();
          }
        } catch (error) {
          await appendEvent(root, taskId, { type: "heartbeat-error", message: error.message });
        }
      });
    }, options.heartbeatIntervalMs ?? 5_000);

    budgetTimer = setTimeout(() => {
      budgetReason = `runtime exceeded ${contract.budget.maxRuntimeMinutes} minutes`;
      abortController.abort();
    }, contract.budget.maxRuntimeMinutes * 60_000);

    const execute = async ({ sessionId, correction, verification = null }) => {
      const priorUsage = { ...cumulativeUsage };
      let reportedByCallback = false;
      const onUsage = (usage) => {
        reportedByCallback = true;
        cumulativeUsage = addUsage(priorUsage, normalizeUsage(usage));
        state.usage = cumulativeUsage;
        budgetReason = findBudgetReason(cumulativeUsage, contract.budget)
          ?? findBudgetHeadroomReason(cumulativeUsage, contract.budget, estimatedInputTokens)
          ?? budgetReason;
        if (budgetReason) abortController.abort();
      };
      const result = await executor.execute({
        contract,
        workspacePath: state.workspacePath,
        sessionId,
        correction,
        verification,
        signal: abortController.signal,
        onUsage
      });
      const usageReported = result.usageReported ?? (reportedByCallback || hasUsage(result.usage));
      if (usageReported) {
        cumulativeUsage = addUsage(priorUsage, normalizeUsage(result.usage));
        state.usage = cumulativeUsage;
        budgetReason = findBudgetReason(cumulativeUsage, contract.budget)
          ?? findBudgetHeadroomReason(cumulativeUsage, contract.budget, estimatedInputTokens)
          ?? budgetReason;
      }
      return { ...result, usageReported };
    };

    let execution = await execute({
      sessionId: recover && state.recoveryAuthorization.action === "RESUME" ? state.sessionId : null,
      correction: false
    });
    state.sessionId = execution.sessionId;
    state.permission = execution.permission;

    if (stopRequested) {
      const target = stopRequested.action === "CANCEL" ? "INTERRUPTED" : "INTERRUPTED";
      return pause(target, { interruptedReason: `user requested ${stopRequested.action}` });
    }
    if (budgetReason) {
      return pause("BUDGET_EXHAUSTED", { budgetReason });
    }
    if (!execution.usageReported) {
      return pause("BUDGET_EXHAUSTED", {
        budgetReason: "executor usage telemetry missing; refusing unmetered continuation"
      });
    }
    if (execution.exitCode !== 0) {
      return pause("INTERRUPTED", { interruptedReason: `executor exit code ${execution.exitCode}` });
    }

    let changedPaths = await workspace.changedPaths(state.workspacePath);
    let violations = findScopeViolations(changedPaths, contract.scope.allowedPaths);
    if (violations.length) {
      return pause("PERMISSION_BLOCKED", { changedPaths, violations, reason: "scope violation" });
    }

    await transitionState(root, state, "VERIFYING", { changedPaths });
    let verification = await verifier.run(contract, state.workspacePath);
    state.verification = verification;

    if (!verification.ok && contract.budget.maxCorrectionCycles > 0) {
      await transitionState(root, state, "CORRECTING", {
        correctionCycles: 1,
        verification
      });
      execution = await execute({
        sessionId: state.sessionId,
        correction: true,
        verification
      });
      state.sessionId = execution.sessionId ?? state.sessionId;
      if (budgetReason) {
        return pause("BUDGET_EXHAUSTED", { budgetReason });
      }
      if (!execution.usageReported) {
        return pause("BUDGET_EXHAUSTED", {
          budgetReason: "executor usage telemetry missing during correction; refusing unmetered continuation"
        });
      }
      if (execution.exitCode !== 0) {
        return pause("INTERRUPTED", { interruptedReason: `correction exit code ${execution.exitCode}` });
      }
      changedPaths = await workspace.changedPaths(state.workspacePath);
      violations = findScopeViolations(changedPaths, contract.scope.allowedPaths);
      if (violations.length) {
        return pause("PERMISSION_BLOCKED", { changedPaths, violations, reason: "scope violation after correction" });
      }
      await transitionState(root, state, "VERIFYING", { changedPaths });
      verification = await verifier.run(contract, state.workspacePath);
      state.verification = verification;
    }

    if (!verification.ok) {
      return pause("VERIFICATION_FAILED", { verification, reason: "deterministic verification failed" });
    }

    const resultPath = path.join(state.workspacePath, contract.resultPath);
    if (!existsSync(resultPath)) {
      return pause("VERIFICATION_FAILED", { reason: `missing result receipt: ${contract.resultPath}` });
    }

    await transitionState(root, state, singleApproval ? "AWAITING_CODEX_REVIEW" : "AWAITING_USER", {
      completedAt: new Date().toISOString(),
      changedPaths,
      verification,
      owner: singleApproval ? "codex" : state.owner,
      reviewOutcome: "EXECUTOR_SUCCEEDED",
      nextActions: singleApproval ? ["CODEX_REVIEW"] : ["ACCEPT", "RETURN", "TAKEOVER", "CANCEL"]
    });
    return state;
  } catch (error) {
    if (["READY", "RUNNING", "VERIFYING", "CORRECTING"].includes(state.status)) {
      await pause("INTERRUPTED", { interruptedReason: error.message });
    }
    await appendEvent(root, taskId, { type: "supervisor-error", message: error.message, stack: error.stack });
    throw error;
  } finally {
    clearInterval(heartbeatTimer);
    clearTimeout(budgetTimer);
    await heartbeatInFlight;
    await rm(paths.control, { force: true });
    await releaseLease(root, lease);
  }
}

async function readControl(file) {
  try {
    return JSON.parse(await readFile(file, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function normalizeUsage(usage) {
  return {
    inputTokens: Number(usage?.inputTokens ?? 0),
    outputTokens: Number(usage?.outputTokens ?? 0),
    cost: Number(usage?.cost ?? 0)
  };
}

function addUsage(left, right) {
  return {
    inputTokens: left.inputTokens + right.inputTokens,
    outputTokens: left.outputTokens + right.outputTokens,
    cost: left.cost + right.cost
  };
}

function hasUsage(usage) {
  const normalized = normalizeUsage(usage);
  return normalized.inputTokens > 0 || normalized.outputTokens > 0 || normalized.cost > 0;
}

export function findBudgetReason(usage, budget) {
  if (usage.inputTokens > budget.maxInputTokens) return "input token budget exhausted";
  if (usage.outputTokens > budget.maxOutputTokens) return "output token budget exhausted";
  if (usage.cost > budget.maxCost) return "cost budget exhausted";
  return null;
}

export function findBudgetHeadroomReason(usage, budget, estimatedInputTokens) {
  const reserve = Math.min(
    Math.max(0, Number(estimatedInputTokens ?? 0)),
    Math.max(2_000, Math.floor(budget.maxInputTokens * 0.25))
  );
  if (reserve > 0 && usage.inputTokens + reserve > budget.maxInputTokens) {
    return `input headroom reached before next model turn (${usage.inputTokens} used, ${reserve} reserved)`;
  }
  return null;
}
