import { create } from 'zustand'
import type { CockpitSnapshotV1, EndpointId } from '../contracts/gp05-v1'

export type ConnectionState = 'connecting' | 'connected' | 'offline'

export function shouldAcceptSnapshot(
  current: CockpitSnapshotV1 | null,
  incoming: CockpitSnapshotV1,
): boolean {
  if (current === null) return true
  if (incoming.sessionId !== current.sessionId) return true
  return incoming.revision >= current.revision
}

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
      shouldAcceptSnapshot(state.snapshot, snapshot)
        ? { snapshot, lastError: null }
        : state,
    ),
  setConnection: (connection, lastError = null) => set({ connection, lastError }),
}))
