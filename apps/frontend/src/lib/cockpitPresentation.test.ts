import { describe, expect, it } from 'vitest'
import {
  formatDistance,
  formatEta,
  freshnessTone,
  riskSourceLabel,
  screenStateClass,
} from './cockpitPresentation'

describe('cockpit presentation helpers', () => {
  it('formats dynamic values without exposing invalid zero data', () => {
    expect(formatDistance(1250)).toBe('1.3 km')
    expect(formatDistance(280)).toBe('280 m')
    expect(formatDistance(0)).toBe('—')
    expect(formatEta(960)).toBe('16 min')
  })

  it('maps status to semantic tone rather than raw colors', () => {
    expect(freshnessTone('fresh')).toBe('success')
    expect(freshnessTone('stale')).toBe('warning')
    expect(freshnessTone('offline')).toBe('neutral')
  })

  it('keeps source labels explicit for mock and real data', () => {
    expect(riskSourceLabel('simulated_event')).toBe('模拟事件')
    expect(riskSourceLabel('live_camera')).toBe('实时摄像头')
  })

  it('uses stable state classes for shell styling', () => {
    expect(screenStateClass(null)).toBe('is-loading')
    expect(screenStateClass({ systemMode: 'takeover' } as never)).toBe('is-takeover')
    expect(screenStateClass({ systemMode: 'recovery' } as never)).toBe('is-degraded')
  })
})
