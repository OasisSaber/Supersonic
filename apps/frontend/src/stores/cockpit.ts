import { create } from 'zustand'
import type { CockpitSnapshotV1, EndpointId } from '../contracts/gp05-v1'

export type ConnectionState = 'connecting' | 'connected' | 'offline'

interface CockpitState {
  endpoint: EndpointId
  snapshot: CockpitSnapshotV1 | null
  connection: ConnectionState
  lastError: string | null
  setEndpoint: (endpoint: EndpointId) => void
  receiveSnapshot: (snapshot: CockpitSnapshotV1) => void
  setConnection: (connection: ConnectionState, error?: string | null) => void
}

export const useCockpitStore = create<CockpitState>((set) => ({
  endpoint: 'overview',
  snapshot: null,
  connection: 'connecting',
  lastError: null,
  setEndpoint: (endpoint) => set({ endpoint }),
  receiveSnapshot: (snapshot) =>
    set((state) =>
      state.snapshot && snapshot.revision < state.snapshot.revision
        ? state
        : { snapshot, lastError: null },
    ),
  setConnection: (connection, lastError = null) => set({ connection, lastError }),
}))
