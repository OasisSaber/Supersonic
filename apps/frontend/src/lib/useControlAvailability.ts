import { useEffect, useState } from 'react'

export type ControlAvailability = 'checking' | 'enabled' | 'disabled' | 'unavailable'

const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export function useControlAvailability(): ControlAvailability {
  const [availability, setAvailability] = useState<ControlAvailability>('checking')

  useEffect(() => {
    const controller = new AbortController()
    void fetch(`${apiBase}/api/v1/control/status`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(response.statusText)))
      .then((payload: unknown) => {
        if (isControlStatus(payload)) {
          setAvailability(payload.controlEnabled ? 'enabled' : 'disabled')
        } else {
          setAvailability('unavailable')
        }
      })
      .catch((cause: unknown) => {
        if (!(cause instanceof DOMException && cause.name === 'AbortError')) {
          setAvailability('unavailable')
        }
      })
    return () => controller.abort()
  }, [])

  return availability
}

function isControlStatus(value: unknown): value is { controlEnabled: boolean } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'controlEnabled' in value &&
    typeof value.controlEnabled === 'boolean'
  )
}
