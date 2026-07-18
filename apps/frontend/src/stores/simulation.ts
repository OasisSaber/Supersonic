import { create } from 'zustand'
import type { RiskEvent, SimulationFrame } from '../types'

interface SimulationState {
  frame: SimulationFrame | null
  timeline: RiskEvent[]
  connected: boolean
  setFrame: (frame: SimulationFrame) => void
  setConnected: (connected: boolean) => void
}

export const useSimulationStore = create<SimulationState>((set) => ({
  frame: null,
  timeline: [],
  connected: false,
  setFrame: (frame) =>
    set((state) => ({
      frame,
      timeline:
        frame.risk.level === 'low'
          ? state.timeline
          : [
              frame.risk,
              ...state.timeline.filter(
                (item) =>
                  item.event !== frame.risk.event || item.timestamp !== frame.risk.timestamp,
              ),
            ].slice(0, 6),
    })),
  setConnected: (connected) => set({ connected }),
}))
