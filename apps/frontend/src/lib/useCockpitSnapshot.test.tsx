import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import snapshotFixture from '../../../../contracts/gp05/v1/example.snapshot.json'
import { useCockpitStore } from '../stores/cockpit'
import { useCockpitSnapshot } from './useCockpitSnapshot'

const snapshotEnvelope = {
  protocolVersion: 'gp05.v1',
  messageId: '5eb3f63d-bebd-4855-98bb-2f706b8aa378',
  correlationId: '5fcff1d6-1d44-4d23-aad2-967ec94b7052',
  timestamp: '2026-07-17T08:36:23Z',
  source: { kind: 'service', id: 'fastapi' },
  target: null,
  kind: 'snapshot',
  payload: snapshotFixture,
}

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this)
  }

  message(payload: unknown) {
    this.onmessage?.({ data: payload } as MessageEvent)
  }

  close() {
    const handler = this.onclose
    this.onclose = null
    handler?.()
  }
}

describe('useCockpitSnapshot', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    useCockpitStore.setState({
      endpoint: 'overview',
      snapshot: null,
      connection: 'offline',
      lastError: null,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('marks connected only after the first valid authoritative snapshot', () => {
    const { unmount } = renderHook(() => useCockpitSnapshot('cluster'))

    expect(useCockpitStore.getState().connection).toBe('connecting')
    expect(FakeWebSocket.instances).toHaveLength(1)

    act(() => FakeWebSocket.instances[0].message(JSON.stringify(snapshotEnvelope)))

    expect(useCockpitStore.getState().connection).toBe('connected')
    expect(useCockpitStore.getState().snapshot?.revision).toBe(snapshotFixture.revision)
    unmount()
  })

  it('contains malformed JSON, retries deterministically, and recovers without reload', async () => {
    const { unmount } = renderHook(() => useCockpitSnapshot('hud'))

    expect(() => act(() => FakeWebSocket.instances[0].message('{not-json'))).not.toThrow()
    expect(useCockpitStore.getState().connection).toBe('offline')
    expect(useCockpitStore.getState().snapshot).toBeNull()

    await act(() => vi.advanceTimersByTimeAsync(499))
    expect(FakeWebSocket.instances).toHaveLength(1)
    await act(() => vi.advanceTimersByTimeAsync(1))
    expect(FakeWebSocket.instances).toHaveLength(2)
    expect(useCockpitStore.getState().connection).toBe('connecting')

    act(() => FakeWebSocket.instances[1].message(JSON.stringify(snapshotEnvelope)))
    expect(useCockpitStore.getState().connection).toBe('connected')
    expect(useCockpitStore.getState().snapshot?.sessionId).toBe(snapshotFixture.sessionId)
    unmount()
  })

  it.each([
    ['wrong protocol', { ...snapshotEnvelope, protocolVersion: 'gp04.v1' }],
    ['invalid snapshot', { ...snapshotEnvelope, payload: { ...snapshotFixture, revision: -1 } }],
    ['missing critical field', { ...snapshotEnvelope, payload: { ...snapshotFixture, vehicle: undefined } }],
  ])('rejects %s before it enters the Store', (_name, message) => {
    const { unmount } = renderHook(() => useCockpitSnapshot('center'))

    act(() => FakeWebSocket.instances[0].message(JSON.stringify(message)))

    expect(useCockpitStore.getState().snapshot).toBeNull()
    expect(useCockpitStore.getState().connection).toBe('offline')
    expect(useCockpitStore.getState().lastError).toContain('不兼容')
    unmount()
  })
})
