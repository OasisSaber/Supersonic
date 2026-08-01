import { describe, expect, it } from 'vitest'
import type { RiskEventV1, RiskLifecycle, RiskSeverity } from '../contracts/gp05-v1'
import { isMediaSafetySuppressed, selectPrimaryRisk } from './riskSelection'

const risk = (
  eventId: string,
  severity: RiskSeverity,
  lifecycle: RiskLifecycle,
  occurredAt = '2026-07-18T00:00:00Z',
): RiskEventV1 => ({
  eventId,
  sessionId: 'test-session',
  riskType: 'driver_fatigue',
  lifecycle,
  severity,
  source: 'simulated_event',
  confidence: 1,
  occurredAt,
  updatedAt: occurredAt,
  message: eventId,
  evidence: [],
  metadata: {},
})

describe('selectPrimaryRisk', () => {
  it('picks the highest severity presentable risk', () => {
    const risks = [risk('warning-1', 'warning', 'active'), risk('critical-1', 'critical', 'active')]
    expect(selectPrimaryRisk(risks)?.eventId).toBe('critical-1')
  })

  it('prefers active over acknowledged when severity is equal', () => {
    const risks = [risk('ack-1', 'critical', 'acknowledged'), risk('act-1', 'critical', 'active')]
    expect(selectPrimaryRisk(risks)?.eventId).toBe('act-1')
  })

  it('severity wins over lifecycle: critical acknowledged beats warning active', () => {
    const risks = [risk('warn-1', 'warning', 'active'), risk('crit-1', 'critical', 'acknowledged')]
    expect(selectPrimaryRisk(risks)?.eventId).toBe('crit-1')
  })

  it('is deterministic regardless of array order', () => {
    const a = risk('a-1', 'warning', 'active', '2026-07-18T00:00:01Z')
    const b = risk('b-1', 'critical', 'active', '2026-07-18T00:00:02Z')
    expect(selectPrimaryRisk([a, b])?.eventId).toBe(selectPrimaryRisk([b, a])?.eventId)
  })

  it('breaks ties by earliest occurredAt then lexicographic eventId', () => {
    const older = risk('older', 'warning', 'active', '2026-07-18T00:00:01Z')
    const newer = risk('newer', 'warning', 'active', '2026-07-18T00:00:02Z')
    expect(selectPrimaryRisk([newer, older])?.eventId).toBe('older')

    const sameTimeA = risk('b-id', 'warning', 'active', '2026-07-18T00:00:00Z')
    const sameTimeB = risk('a-id', 'warning', 'active', '2026-07-18T00:00:00Z')
    expect(selectPrimaryRisk([sameTimeA, sameTimeB])?.eventId).toBe('a-id')
  })

  it('returns null when only resolved or candidate risks exist', () => {
    expect(selectPrimaryRisk([risk('r1', 'critical', 'resolved'), risk('c1', 'warning', 'candidate')])).toBeUndefined()
    expect(selectPrimaryRisk([])).toBeUndefined()
  })

  it('handles multiple simultaneous risks of the same severity deterministically', () => {
    const risks = [
      risk('m1', 'warning', 'active', '2026-07-18T00:00:03Z'),
      risk('m2', 'warning', 'active', '2026-07-18T00:00:01Z'),
      risk('m3', 'warning', 'active', '2026-07-18T00:00:02Z'),
    ]
    expect(selectPrimaryRisk(risks)?.eventId).toBe('m2')
  })
})

describe('isMediaSafetySuppressed', () => {
  it('matches the backend policy: any active or acknowledged critical risk suppresses media', () => {
    expect(isMediaSafetySuppressed([risk('a', 'critical', 'active')])).toBe(true)
    expect(isMediaSafetySuppressed([risk('a', 'critical', 'acknowledged')])).toBe(true)
    expect(isMediaSafetySuppressed([risk('a', 'warning', 'active')])).toBe(false)
    expect(isMediaSafetySuppressed([risk('a', 'critical', 'resolved')])).toBe(false)
    expect(isMediaSafetySuppressed([risk('a', 'critical', 'candidate')])).toBe(false)
    expect(isMediaSafetySuppressed([])).toBe(false)
  })

  it('suppresses when a critical risk exists even if a tie-break picks a different primary', () => {
    const risks = [
      risk('later-critical', 'critical', 'active', '2026-07-18T00:00:02Z'),
      risk('earlier-critical', 'critical', 'active', '2026-07-18T00:00:01Z'),
    ]
    expect(selectPrimaryRisk(risks)?.eventId).toBe('earlier-critical')
    expect(isMediaSafetySuppressed(risks)).toBe(true)
  })
})