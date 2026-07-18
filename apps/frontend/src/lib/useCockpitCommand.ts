import { useCallback, useState } from 'react'
import {
  CONTRACT_VERSION,
  isMessageEnvelopeV1,
  type CommandName,
  type EndpointId,
  type JsonValue,
} from '../contracts/gp05-v1'
import { useCockpitStore } from '../stores/cockpit'

const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export function useCockpitCommand(endpoint: EndpointId) {
  const receiveSnapshot = useCockpitStore((state) => state.receiveSnapshot)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const send = useCallback(async (name: CommandName, parameters: Record<string, JsonValue>) => {
    setPending(true)
    setError(null)
    try {
      const now = new Date().toISOString()
      const response = await fetch(`${apiBase}/api/v1/commands`, {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          protocolVersion: CONTRACT_VERSION, messageId: crypto.randomUUID(), correlationId: crypto.randomUUID(), timestamp: now,
          source: { kind: 'endpoint', id: endpoint }, target: null, kind: 'command', payload: { name, endpoint, parameters },
        }),
      })
      const payload: unknown = await response.json()
      if (!response.ok) throw new Error(isError(payload) ? payload.error.message : '命令未被服务端接受')
      if (!isMessageEnvelopeV1(payload) || payload.kind !== 'snapshot') throw new Error('服务端未返回有效 snapshot')
      receiveSnapshot(payload.payload)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '命令失败')
    } finally {
      setPending(false)
    }
  }, [endpoint, receiveSnapshot])

  return { send, pending, error }
}

function isError(value: unknown): value is { error: { message: string } } {
  return typeof value === 'object' && value !== null && 'error' in value &&
    typeof value.error === 'object' && value.error !== null && 'message' in value.error &&
    typeof value.error.message === 'string'
}
