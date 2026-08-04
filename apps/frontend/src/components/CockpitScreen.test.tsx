import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import snapshotFixture from '../../../../contracts/gp05/v1/example.snapshot.json'
import type { CockpitSnapshotV1 } from '../contracts/gp05-v1'
import { CockpitScreen } from './CockpitScreen'

const authoritativeSnapshot = snapshotFixture as CockpitSnapshotV1

describe('CockpitScreen endpoint rendering', () => {
  afterEach(cleanup)

  it('identifies the approved Supersonic GP22 design system', () => {
    render(
      <CockpitScreen
        endpoint="cluster"
        snapshot={authoritativeSnapshot}
        connection="connected"
      />,
    )

    expect(screen.getByText('Supersonic · GP22')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '主仪表' })).toBeInTheDocument()
  })

  it('renders Overview previews without command buttons or form fields', () => {
    render(
      <CockpitScreen
        endpoint="overview"
        snapshot={authoritativeSnapshot}
        connection="connected"
      />,
    )

    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getAllByText(/主仪表|HUD|中控|副驾/).length).toBeGreaterThanOrEqual(4)
    expect(screen.getByText(/Overview 不加载任何命令 Hook/)).toBeInTheDocument()
  })

  it('keeps Center interactive on its own route', () => {
    render(
      <CockpitScreen
        endpoint="center"
        snapshot={authoritativeSnapshot}
        connection="connected"
      />,
    )

    expect(screen.getByRole('button', { name: '规划路线' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '目的地' })).toBeInTheDocument()
    expect(screen.getByText(/不冒充实时地图/)).toBeInTheDocument()
  })

  it('keeps Passenger interactive on its own route', () => {
    render(
      <CockpitScreen
        endpoint="passenger"
        snapshot={authoritativeSnapshot}
        connection="connected"
      />,
    )

    expect(screen.getByRole('button', { name: /播放媒体|暂停媒体/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '发送旅程建议' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '旅程建议' })).toHaveAttribute('maxLength', '200')
  })
})
