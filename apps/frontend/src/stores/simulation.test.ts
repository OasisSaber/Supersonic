import { beforeEach, describe, expect, it } from 'vitest'
import { useSimulationStore } from './simulation'
import type { SimulationFrame } from '../types'

const frame: SimulationFrame = {
  sequence: 3,
  vehicle: {
    speed: 32,
    gear: 'D',
    battery: 81,
    range_km: 432,
    drive_mode: '舒适',
    battery_temperature: 29,
    seatbelt_fastened: true,
  },
  sensor: {
    timestamp: 125.6,
    road: {
      pedestrian_detected: true,
      vehicle_count: 3,
      lane_departure: false,
      front_vehicle_risk: 'medium',
    },
    driver: {
      fatigue_level: 'medium',
      distracted: true,
      eyes_closed_duration: 0.4,
      yawning: false,
    },
    vehicle: {
      speed: 32,
      gear: 'D',
      battery: 81,
      range_km: 432,
      drive_mode: '舒适',
      battery_temperature: 29,
      seatbelt_fastened: true,
    },
  },
  risk: {
    event: 'pedestrian_and_distraction',
    level: 'high',
    timestamp: 125.6,
    message: '前方检测到行人且驾驶员注意力偏移',
    evidence: ['前方行人', '驾驶员注意力偏移'],
  },
}

describe('simulation timeline', () => {
  beforeEach(() => useSimulationStore.setState({ frame: null, timeline: [], connected: false }))

  it('deduplicates the same risk event after reconnect or replay', () => {
    useSimulationStore.getState().setFrame(frame)
    useSimulationStore.getState().setFrame({ ...frame, sequence: 8 })

    expect(useSimulationStore.getState().timeline).toEqual([frame.risk])
  })
})
