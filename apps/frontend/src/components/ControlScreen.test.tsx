import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import snapshotFixture from '../../../../contracts/gp05/v1/example.snapshot.json'
import type { CockpitSnapshotV1 } from '../contracts/gp05-v1'
import { useCockpitStore } from '../stores/cockpit'
import { CockpitScreen } from './CockpitScreen'
import { ControlScreen } from './ControlScreen'

const initialSnapshot = snapshotFixture as CockpitSnapshotV1

function Harness() {
  const snapshot = useCockpitStore((state) => state.snapshot)
  return <ControlScreen snapshot={snapshot} />
}

describe('ControlScreen', () => {
  beforeEach(() => {
    useCockpitStore.setState({
      endpoint: 'control',
      snapshot: initialSnapshot,
      connection: 'connected',
      lastError: null,
    })
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('shows an explicit disabled state and disables privileged commands', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ controlEnabled: false }),
    }))

    render(<Harness />)

    expect(await screen.findByText(/Control 命令未启用/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '日间主题' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '重置权威会话' })).toBeDisabled()
    expect(screen.getByText(initialSnapshot.sessionId)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '端点连接' })).toBeInTheDocument()
  })

  it('renders the dedicated Control endpoint instead of the Center fallback', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ controlEnabled: false }),
    }))

    render(<CockpitScreen endpoint="control" snapshot={initialSnapshot} connection="connected" />)

    expect(await screen.findByRole('button', { name: '重置权威会话' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Control 命令' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: '目的地' })).not.toBeInTheDocument()
  })

  it('submits every Control action and renders only authoritative responses', async () => {
    let releaseThemeResponse: () => void = () => {}
    const themeResponseGate = new Promise<void>((resolve) => {
      releaseThemeResponse = resolve
    })
    const fetchMock = vi.fn().mockImplementation(async (input: string | URL, init?: RequestInit) => {
      if (String(input).endsWith('/api/v1/control/status')) {
        return { ok: true, json: async () => ({ controlEnabled: true }) }
      }
      const command = JSON.parse(String(init?.body)).payload
      if (command.name === 'set_theme') await themeResponseGate
      const snapshots = {
        set_theme: { ...initialSnapshot, revision: 43, theme: 'day' as const },
        set_system_mode: {
          ...initialSnapshot,
          revision: 44,
          theme: 'day' as const,
          systemMode: 'normal' as const,
        },
        reset_session: {
          ...initialSnapshot,
          sessionId: 'reset-session',
          revision: 45,
          systemMode: 'normal' as const,
        },
      }
      return {
        ok: true,
        json: async () => ({
          protocolVersion: 'gp05.v1',
          messageId: '5eb3f63d-bebd-4855-98bb-2f706b8aa378',
          correlationId: '5fcff1d6-1d44-4d23-aad2-967ec94b7052',
          timestamp: '2026-07-17T08:36:23Z',
          source: { kind: 'service', id: 'fastapi' },
          target: null,
          kind: 'snapshot',
          payload: snapshots[command.name as keyof typeof snapshots],
        }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<Harness />)
    const dayButton = await screen.findByRole('button', { name: '日间主题' })
    await waitFor(() => expect(dayButton).toBeEnabled())
    fireEvent.click(dayButton)

    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) =>
      String(input).includes('/commands/'),
    )).toHaveLength(1))
    expect(useCockpitStore.getState().snapshot).toBe(initialSnapshot)
    expect(screen.getByText(String(initialSnapshot.revision))).toBeInTheDocument()
    expect(screen.getByText(initialSnapshot.theme)).toBeInTheDocument()

    releaseThemeResponse()
    await waitFor(() => expect(screen.getByText('43')).toBeInTheDocument())
    expect(screen.getByText('day')).toBeInTheDocument()

    const normalButton = screen.getByRole('button', { name: '正常模式' })
    await waitFor(() => expect(normalButton).toBeEnabled())
    fireEvent.click(normalButton)
    await waitFor(() => expect(useCockpitStore.getState().snapshot).toMatchObject({
      revision: 44,
      systemMode: 'normal',
    }))
    expect(screen.getByText('44')).toBeInTheDocument()
    expect(screen.getByText('normal')).toBeInTheDocument()

    const resetButton = screen.getByRole('button', { name: '重置权威会话' })
    await waitFor(() => expect(resetButton).toBeEnabled())
    fireEvent.click(resetButton)
    await waitFor(() => expect(useCockpitStore.getState().snapshot).toMatchObject({
      sessionId: 'reset-session',
      revision: 45,
    }))
    expect(screen.getByText('45')).toBeInTheDocument()
    expect(screen.getByText('reset-session')).toBeInTheDocument()

    const commandCalls = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes('/commands/'),
    )
    expect(commandCalls).toHaveLength(3)
    expect(commandCalls.every(([input]) =>
      String(input).endsWith('/api/v1/commands/control'),
    )).toBe(true)
    expect(commandCalls.map(([, init]) => JSON.parse(String(init?.body)).payload)).toEqual([
      { name: 'set_theme', endpoint: 'control', parameters: { theme: 'day' } },
      { name: 'set_system_mode', endpoint: 'control', parameters: { mode: 'normal' } },
      { name: 'reset_session', endpoint: 'control', parameters: {} },
    ])
  })
})
