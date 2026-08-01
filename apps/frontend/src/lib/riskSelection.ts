import type { RiskEventV1, RiskLifecycle, RiskSeverity } from '../contracts/gp05-v1'

const SEVERITY_RANK: Record<RiskSeverity, number> = { info: 0, warning: 1, critical: 2 }

const PRESENTABLE_LIFECYCLES: ReadonlySet<RiskLifecycle> = new Set(['active', 'acknowledged'])

export function isMediaSafetySuppressed(risks: readonly RiskEventV1[]): boolean {
  return risks.some(
    (risk) =>
      risk.severity === 'critical' &&
      (risk.lifecycle === 'active' || risk.lifecycle === 'acknowledged'),
  )
}

export function selectPrimaryRisk(risks: readonly RiskEventV1[]): RiskEventV1 | undefined {
  let primary: RiskEventV1 | undefined
  for (const risk of risks) {
    if (!PRESENTABLE_LIFECYCLES.has(risk.lifecycle)) continue
    if (primary === undefined || isHigherPriority(risk, primary)) primary = risk
  }
  return primary
}

function isHigherPriority(candidate: RiskEventV1, current: RiskEventV1): boolean {
  const severityDiff = SEVERITY_RANK[candidate.severity] - SEVERITY_RANK[current.severity]
  if (severityDiff !== 0) return severityDiff > 0
  const lifecycleDiff = lifecycleRank(candidate.lifecycle) - lifecycleRank(current.lifecycle)
  if (lifecycleDiff !== 0) return lifecycleDiff > 0
  const timeDiff = candidate.occurredAt.localeCompare(current.occurredAt)
  if (timeDiff !== 0) return timeDiff < 0
  return candidate.eventId.localeCompare(current.eventId) < 0
}

function lifecycleRank(lifecycle: RiskLifecycle): number {
  return lifecycle === 'active' ? 1 : 0
}