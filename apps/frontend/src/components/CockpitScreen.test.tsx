import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import snapshotFixture from '../../../../contracts/gp05/v1/example.snapshot.json'
import { CockpitScreen } from './CockpitScreen'
import type { CockpitSnapshotV1 } from '../contracts/gp05-v1'

const authoritativeSnapshot = snapshotFixture as CockpitSnapshotV1

describe('CockpitScreen endpoint rendering', () => {
  afterEach(cleanup)

  it('renders Overview previews without any command buttons or inputs', () => {
    render(<CockpitScreen endpoint="overview" snapshot={authoritativeSnapshot} connection="connected" />)

    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getAllByText(/主仪表|HUD|中控|副驾/).length).toBeGreaterThanOrEqual(4)
  })

  it('keeps Center interactive on its own route', () => {
    render(<CockpitScreen endpoint="center" snapshot={authoritativeSnapshot} connection="connected" />)

    expect(screen.getByRole('button', { name: '规划路线' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '目的地' })).toBeInTheDocument()
  })

  it('keeps Passenger interactive on its own route', () => {
    render(<CockpitScreen endpoint="passenger" snapshot={authoritativeSnapshot} connection="connected" />)

    expect(screen.getByRole('button', { name: /播放媒体|暂停媒体/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '发送旅程建议' })).toBeInTheDocument()
  })
})