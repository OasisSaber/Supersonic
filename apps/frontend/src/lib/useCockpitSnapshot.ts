import { useEffect } from 'react'
import {
  isMessageEnvelopeV1,
  isCockpitSnapshotV1,
  type EndpointId,
} from '../contracts/gp05-v1'
import { useCockpitStore } from '../stores/cockpit'

const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
const INITIAL_RECONNECT_DELAY_MS = 500
const MAX_RECONNECT_DELAY_MS = 5000

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
    let reconnectAttempt = 0

    setEndpoint(endpoint)
    setConnection('connecting')
    void fetch(`${apiBase}/api/v1/snapshot`)
      .then((response) => (response.ok ? response.json() : Promise.reject(response.statusText)))
      .then((payload: unknown) => {
        if (!disposed && isCockpitSnapshotV1(payload)) receiveSnapshot(payload)
      })
      .catch(() => undefined)

    const scheduleReconnect = (message: string) => {
      if (disposed) return
      setConnection('offline', message)
      const delay = Math.min(
        INITIAL_RECONNECT_DELAY_MS * 2 ** reconnectAttempt,
        MAX_RECONNECT_DELAY_MS,
      )
      reconnectAttempt += 1
      retry = setTimeout(connect, delay)
    }

    const connect = () => {
      if (disposed) return
      setConnection('connecting')
      let currentSocket: WebSocket
      try {
        currentSocket = new WebSocket(websocketUrl(endpoint))
      } catch {
        scheduleReconnect('无法创建 FastAPI snapshot 连接')
        return
      }
      socket = currentSocket
      let closeMessage = '未连接到 FastAPI snapshot 服务'
      currentSocket.onmessage = (event) => {
        if (disposed || socket !== currentSocket) return
        let payload: unknown
        try {
          if (typeof event.data !== 'string') throw new Error('non-text message')
          payload = JSON.parse(event.data)
        } catch {
          closeMessage = '收到无法解析的 FastAPI snapshot 消息'
          currentSocket.close()
          return
        }
        if (!isMessageEnvelopeV1(payload) || payload.kind !== 'snapshot') {
          closeMessage = '收到不兼容的 FastAPI snapshot 消息'
          currentSocket.close()
          return
        }
        reconnectAttempt = 0
        receiveSnapshot(payload.payload)
        setConnection('connected')
      }
      currentSocket.onerror = () => {
        closeMessage = 'FastAPI snapshot 连接发生错误'
        currentSocket.close()
      }
      currentSocket.onclose = () => {
        if (socket === currentSocket) socket = null
        scheduleReconnect(closeMessage)
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
