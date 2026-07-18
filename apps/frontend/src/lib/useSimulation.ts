import { useEffect } from 'react'
import { useSimulationStore } from '../stores/simulation'
import type { SimulationFrame } from '../types'

export function useSimulation() {
  const setFrame = useSimulationStore((state) => state.setFrame)
  const setConnected = useSimulationStore((state) => state.setConnected)

  useEffect(() => {
    const url = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8000/ws/simulation'
    let socket: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    let closedByEffect = false

    const connect = () => {
      socket = new WebSocket(url)
      socket.onopen = () => setConnected(true)
      socket.onmessage = (event) => setFrame(JSON.parse(event.data) as SimulationFrame)
      socket.onerror = () => socket?.close()
      socket.onclose = () => {
        setConnected(false)
        if (!closedByEffect) retry = setTimeout(connect, 1800)
      }
    }

    connect()
    return () => {
      closedByEffect = true
      if (retry) clearTimeout(retry)
      socket?.close()
    }
  }, [setConnected, setFrame])
}

