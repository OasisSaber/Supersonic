import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import snapshotFixture from '../../../../../contracts/gp05/v1/example.snapshot.json'
import type { CockpitSnapshotV1 } from '../../contracts/gp05-v1'
import { ScreenShell } from './ScreenShell'

const snapshot = snapshotFixture as CockpitSnapshotV1

describe('ScreenShell service-state messages', () => {
  afterEach(cleanup)

  it('shows initial connection progress without claiming a retained snapshot', () => {
    render(
      <ScreenShell connection="connecting" endpoint="center" snapshot={null}>
        <div>content</div>
      </ScreenShell>,
    )

    expect(screen.getByText(/正在连接：等待第一份权威快照/)).toBeInTheDocument()
    expect(screen.queryByText(/保留最后一次权威快照/)).not.toBeInTheDocument()
  })

  it('distinguishes a transport interruption from a data-domain outage', () => {
    render(
      <ScreenShell connection="offline" endpoint="center" snapshot={snapshot}>
        <div>content</div>
      </ScreenShell>,
    )

    expect(screen.getByText(/连接中断：保留最后一次权威快照/)).toBeInTheDocument()
  })

  it('renders the authoritative system offline mode while transport stays connected', () => {
    render(
      <ScreenShell
        connection="connected"
        endpoint="center"
        snapshot={{ ...snapshot, systemMode: 'offline' }}
      >
        <div>content</div>
      </ScreenShell>,
    )

    expect(screen.getByText(/服务离线：部分数据域不可用/)).toBeInTheDocument()
  })

  it('renders stale and recovery as separate states', () => {
    const { rerender } = render(
      <ScreenShell
        connection="connected"
        endpoint="center"
        snapshot={{ ...snapshot, systemMode: 'stale' }}
      >
        <div>content</div>
      </ScreenShell>,
    )

    expect(screen.getByText(/数据滞后：当前值来自最近一次/)).toBeInTheDocument()

    rerender(
      <ScreenShell
        connection="connected"
        endpoint="center"
        snapshot={{ ...snapshot, systemMode: 'recovery' }}
      >
        <div>content</div>
      </ScreenShell>,
    )

    expect(screen.getByText(/状态恢复中：等待全部端点收敛/)).toBeInTheDocument()
  })
})
