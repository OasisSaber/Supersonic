import { useEffect } from 'react'
import {
  isMessageEnvelopeV1,
  isCockpitSnapshotV1,
  type EndpointId,
} from '../contracts/gp05-v1'
import { useCockpitStore } from '../stores/cockpit'

const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

function websocketUrl(endpoint: EndpointId) {
  const url = new URL(apiBase)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/ws/v1/cockpit'
  url.searchParams.set('endpoint', endpoint)
  return url.toString()
}

export function useCockpitSnapshot(endpoint: EndpointId) {
  const setEndpoint = useCockpitStore((state) => state.setEndpoint)
  const receiveSnapshot = useCockpitStore((state) => state.receiveSnapshot)
  const setConnection = useCockpitStore((state) => state.setConnection)

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined

    setEndpoint(endpoint)
    setConnection('connecting')
    void fetch(`${apiBase}/api/v1/snapshot`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.statusText)))
      .then((payload: unknown) => {
        if (!disposed && isCockpitSnapshotV1(payload)) receiveSnapshot(payload)
      })
      .catch(() => undefined)

    const connect = () => {
      if (disposed) return
      socket = new WebSocket(websocketUrl(endpoint))
      socket.onopen = () => setConnection('connected')
      socket.onmessage = (event) => {
        const payload: unknown = JSON.parse(event.data)
        if (isMessageEnvelopeV1(payload) && payload.kind === 'snapshot') {
          receiveSnapshot(payload.payload)
        }
      }
      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        if (disposed) return
        setConnection('offline', '未连接到 FastAPI snapshot 服务')
        retry = setTimeout(connect, 1800)
      }
    }

    connect()
    return () => {
      disposed = true
      if (retry) clearTimeout(retry)
      socket?.close()
    }
  }, [endpoint, receiveSnapshot, setConnection, setEndpoint])
}
