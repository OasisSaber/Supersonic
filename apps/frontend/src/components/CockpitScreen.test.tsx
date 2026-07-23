import { render, screen } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { CockpitScreen } from './CockpitScreen'

const { useCockpitCommand } = vi.hoisted(() => ({ useCockpitCommand: vi.fn() }))

vi.mock('../lib/useCockpitCommand', () => ({
  useCockpitCommand,
}))

beforeEach(() => {
  useCockpitCommand.mockReset()
  useCockpitCommand.mockReturnValue({ send: vi.fn(), pending: false, error: null })
})

const snapshot = {
  sessionId: 'session-1',
  revision: 1,
  timestamp: '2026-07-23T00:00:00.000Z',
  theme: 'day' as const,
  systemMode: 'normal' as const,
  activeFlow: 'navigation_handoff' as const,
  dataHealth: {},
  vehicle: { speedKph: 80, gear: 'D', batteryPercent: 80, rangeKm: 420, driveMode: '舒适', seatbeltFastened: true },
  navigation: { provider: 'local_fallback' as const, serviceStatus: 'degraded' as const, status: 'preview' as const, destinationName: '城市艺术中心', remainingDistanceMeters: 1200, etaSeconds: 300, currentStep: null, steps: [], polyline: [], updatedAt: '2026-07-23T00:00:00.000Z' },
  risks: [],
  passenger: { mediaState: 'playing' as const, privacyEnabled: false, tripSuggestions: [] },
  endpointConnectivity: {},
  capabilities: [],
}

test('renders four read-only previews without command hooks or controls', () => {
  render(<CockpitScreen endpoint="overview" snapshot={snapshot} connection="connected" />)

  expect(screen.getByLabelText('主仪表屏幕预览')).toHaveTextContent('1920×720')
  expect(screen.getByLabelText('HUD屏幕预览')).toHaveTextContent('1280×480')
  expect(screen.getByLabelText('中控屏幕预览')).toHaveTextContent('1920×1080')
  expect(screen.getByLabelText('副驾屏幕预览')).toHaveTextContent('1920×1080')
  expect(screen.queryByText('只读预览')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('目的地')).not.toBeInTheDocument()
  expect(screen.queryByText('规划路线')).not.toBeInTheDocument()
  expect(screen.queryByText('确认并接力')).not.toBeInTheDocument()
  expect(screen.queryByText(/播放媒体|暂停媒体/)).not.toBeInTheDocument()
  expect(screen.queryByLabelText('旅程建议')).not.toBeInTheDocument()
  expect(screen.queryByText('发送旅程建议')).not.toBeInTheDocument()
  expect(screen.queryByText(/开启隐私|关闭隐私/)).not.toBeInTheDocument()
  expect(useCockpitCommand).not.toHaveBeenCalled()
})

test('keeps center and passenger command controls on their own routes', () => {
  const { rerender } = render(<CockpitScreen endpoint="center" snapshot={snapshot} connection="connected" />)

  expect(screen.getByLabelText('目的地')).toBeInTheDocument()
  expect(screen.getByText('规划路线')).toBeInTheDocument()
  expect(useCockpitCommand).toHaveBeenLastCalledWith('center')

  rerender(<CockpitScreen endpoint="passenger" snapshot={snapshot} connection="connected" />)

  expect(screen.getByText('暂停媒体')).toBeInTheDocument()
  expect(screen.getByLabelText('旅程建议')).toBeInTheDocument()
  expect(screen.getByText('发送旅程建议')).toBeInTheDocument()
  expect(screen.getByText('开启隐私')).toBeInTheDocument()
  expect(useCockpitCommand).toHaveBeenLastCalledWith('passenger')
})
