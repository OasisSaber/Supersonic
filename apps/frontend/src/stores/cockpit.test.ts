import { beforeEach, describe, expect, it } from 'vitest'
import type { CockpitSnapshotV1 } from '../contracts/gp05-v1'
import { useCockpitStore } from './cockpit'

const snapshot = (revision: number): CockpitSnapshotV1 => ({
  sessionId: 'test-session', revision, timestamp: '2026-07-18T00:00:00Z', theme: 'night', systemMode: 'normal', activeFlow: 'navigation_handoff',
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
})
