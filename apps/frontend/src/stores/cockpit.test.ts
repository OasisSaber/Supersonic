import { beforeEach, describe, expect, it } from 'vitest'
import type { CockpitSnapshotV1 } from '../contracts/gp05-v1'
import { shouldAcceptSnapshot, useCockpitStore } from './cockpit'

const snapshot = (revision: number, sessionId = 'test-session'): CockpitSnapshotV1 => ({
  sessionId, revision, timestamp: '2026-07-18T00:00:00Z', theme: 'night', systemMode: 'normal', activeFlow: 'navigation_handoff',
  dataHealth: {}, vehicle: { speedKph: 40, gear: 'D', batteryPercent: 80, rangeKm: 420, driveMode: 'comfort', seatbeltFastened: true },
  navigation: { provider: 'none', serviceStatus: 'unavailable', status: 'idle', destinationName: null, remainingDistanceMeters: 0, etaSeconds: 0, currentStep: null, steps: [], polyline: [], updatedAt: '2026-07-18T00:00:00Z' },
  risks: [], passenger: { mediaState: 'paused', privacyEnabled: true, tripSuggestions: [] }, endpointConnectivity: {}, capabilities: [],
})

describe('cockpit snapshot store', () => {
  beforeEach(() => useCockpitStore.setState({ snapshot: null, connection: 'connecting', lastError: null, endpoint: 'overview' }))

  it('does not let an old snapshot overwrite the latest authoritative revision', () => {
    useCockpitStore.getState().receiveSnapshot(snapshot(8))
    useCockpitStore.getState().receiveSnapshot(snapshot(7))
    expect(useCockpitStore.getState().snapshot?.revision).toBe(8)
  })

  it('accepts a lower revision from a different session', () => {
    useCockpitStore.getState().receiveSnapshot(snapshot(8))
    useCockpitStore.getState().receiveSnapshot(snapshot(3, 'new-session'))
    expect(useCockpitStore.getState().snapshot?.sessionId).toBe('new-session')
    expect(useCockpitStore.getState().snapshot?.revision).toBe(3)
  })

  it('treats duplicate revisions in the same session as idempotent', () => {
    useCockpitStore.getState().receiveSnapshot(snapshot(5))
    useCockpitStore.getState().receiveSnapshot(snapshot(5))
    expect(useCockpitStore.getState().snapshot?.revision).toBe(5)
  })
})

describe('shouldAcceptSnapshot', () => {
  it('rejects only same-session stale revisions and accepts all valid transitions', () => {
    const current = snapshot(8)
    expect(shouldAcceptSnapshot(current, snapshot(7))).toBe(false)
    expect(shouldAcceptSnapshot(current, snapshot(8))).toBe(true)
    expect(shouldAcceptSnapshot(current, snapshot(9))).toBe(true)
    expect(shouldAcceptSnapshot(current, snapshot(1, 'other-session'))).toBe(true)
    expect(shouldAcceptSnapshot(null, snapshot(0))).toBe(true)
  })
})
