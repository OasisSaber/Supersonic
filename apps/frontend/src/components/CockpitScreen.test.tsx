import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import snapshotFixture from '../../../../contracts/gp05/v1/example.snapshot.json'
import type { CockpitSnapshotV1 } from '../contracts/gp05-v1'
import { CockpitScreen } from './CockpitScreen'
import { CenterScreen } from './screens/CenterScreen'

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

  it('does not invent vehicle or route facts before Cluster receives a snapshot', () => {
    render(<CockpitScreen endpoint="cluster" snapshot={null} connection="connecting" />)

    expect(screen.queryByText('安全带未系')).not.toBeInTheDocument()
    expect(screen.getAllByText(/等待权威/).length).toBeGreaterThan(0)
  })

  it('does not invent lane, navigation, or risk facts before HUD receives a snapshot', () => {
    render(<CockpitScreen endpoint="hud" snapshot={null} connection="connecting" />)

    expect(screen.queryByText('保持当前车道')).not.toBeInTheDocument()
    expect(screen.queryByText('当前无活动风险')).not.toBeInTheDocument()
    expect(screen.getByText('HUD 数据暂不可用')).toBeInTheDocument()
  })

  it('disables Center mutations before the first authoritative snapshot', () => {
    render(<CockpitScreen endpoint="center" snapshot={null} connection="connecting" />)

    expect(screen.getByText('路线状态暂不可用')).toBeInTheDocument()
    expect(screen.queryByText('无活动风险')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '目的地' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '规划路线' })).toBeDisabled()
  })

  it('keeps Center risk mutations disabled without a snapshot even if a risk prop is present', () => {
    render(<CenterScreen activeRisk={authoritativeSnapshot.risks[0]} snapshot={null} />)

    expect(screen.getByRole('button', { name: '确认告警' })).toBeDisabled()
  })

  it('does not invent Passenger state and disables mutations before a snapshot', () => {
    render(<CockpitScreen endpoint="passenger" snapshot={null} connection="connecting" />)

    expect(screen.queryByText('旅程媒体已暂停')).not.toBeInTheDocument()
    expect(screen.queryByText('副驾内容不投射至驾驶端')).not.toBeInTheDocument()
    expect(screen.getByText('媒体状态暂不可用')).toBeInTheDocument()
    expect(screen.getByText('隐私状态暂不可用')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '媒体控制不可用' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '隐私控制不可用' })).toBeDisabled()
    expect(screen.getByRole('textbox', { name: '旅程建议' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '发送旅程建议' })).toBeDisabled()
  })

  it('does not invent Overview driving, navigation, or media facts before a snapshot', () => {
    render(<CockpitScreen endpoint="overview" snapshot={null} connection="connecting" />)

    expect(screen.queryByText('保持当前车道')).not.toBeInTheDocument()
    expect(screen.queryByText('idle')).not.toBeInTheDocument()
    expect(screen.queryByText('paused')).not.toBeInTheDocument()
    expect(screen.queryByText('允许共享旅程内容')).not.toBeInTheDocument()
    expect(screen.getAllByText('等待权威快照')).toHaveLength(4)
  })
})
