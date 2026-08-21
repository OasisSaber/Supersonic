import { afterEach, describe, expect, it, vi } from 'vitest'
import { platformApi } from './platformApi'

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const identity = {
  userId: 'user-current',
  displayName: 'Current Admin',
  role: 'admin',
  platformSessionId: 'session-current',
  expiresAt: '2026-08-22T12:00:00Z',
}

describe('platformApi boundary', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('always includes credentials and never writes login secrets to browser storage', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(identity))
    const localStorageSpy = vi.spyOn(Storage.prototype, 'setItem')
    const sessionStorageSpy = vi.spyOn(Storage.prototype, 'setItem')

    await expect(platformApi.login('alice', 'correct horse battery staple')).resolves.toEqual(identity)

    expect(fetchSpy).toHaveBeenCalledOnce()
    expect(fetchSpy.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({ username: 'alice', password: 'correct horse battery staple' }),
    })
    expect(localStorageSpy).not.toHaveBeenCalled()
    expect(sessionStorageSpy).not.toHaveBeenCalled()
  })

  it('runtime-rejects malformed success payloads before they enter React state', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse({ ...identity, role: 'root', token: 'must-not-enter-state' }),
    )

    await expect(platformApi.me()).rejects.toMatchObject({
      status: 502,
      code: 'invalid_response',
    })
  })

  it('validates nested audit data and preserves stable server errors', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    fetchSpy.mockResolvedValueOnce(jsonResponse({ events: [{ id: 3 }], nextCursor: null }))
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ error: { code: 'session_invalid', message: 'Invalid session.' } }, 401),
    )

    await expect(platformApi.audit()).rejects.toMatchObject({ code: 'invalid_response' })
    await expect(platformApi.users()).rejects.toMatchObject({
      status: 401,
      code: 'session_invalid',
      message: 'Invalid session.',
    })
  })
})
