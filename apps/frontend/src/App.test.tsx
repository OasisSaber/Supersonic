import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import snapshotFixture from '../../../contracts/gp05/v1/example.snapshot.json'
import App from './App'
import type { CockpitSnapshotV1 } from './contracts/gp05-v1'
import mainSource from './main.tsx?raw'
import { useCockpitStore } from './stores/cockpit'

vi.mock('./lib/useCockpitSnapshot', () => ({
  useCockpitSnapshot: vi.fn(),
}))

const authoritativeSnapshot = snapshotFixture as CockpitSnapshotV1
const themeSourceFiles = import.meta.glob(
  ['./**/*.{css,ts,tsx}', '!./App.test.tsx'],
  { eager: true, import: 'default', query: '?raw' },
) as Record<string, string>

describe('authoritative cockpit theme', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/cluster')
    useCockpitStore.setState({
      endpoint: 'overview',
      snapshot: null,
      connection: 'connecting',
      lastError: null,
    })
  })

  afterEach(() => {
    cleanup()
    useCockpitStore.setState({
      endpoint: 'overview',
      snapshot: null,
      connection: 'connecting',
      lastError: null,
    })
  })

  it('loads the design tokens exactly once before the consuming stylesheet', () => {
    const tokenImport = "import './design/gp05-tokens.css'"
    const stylesImport = "import './styles.css'"
    const tokenReferences = Object.values(themeSourceFiles)
      .flatMap((source) => source.match(/gp05-tokens\.css/g) ?? [])

    expect(tokenReferences).toHaveLength(1)
    expect(mainSource).toContain(tokenImport)
    expect(mainSource.indexOf(tokenImport)).toBeLessThan(mainSource.indexOf(stylesImport))
  })

  it('uses Night before the first valid authoritative snapshot', () => {
    render(<App />)

    expect(screen.getByRole('main')).toHaveAttribute('data-theme', 'night')
  })

  it('renders the theme from the latest authoritative snapshot', () => {
    render(<App />)

    act(() => {
      useCockpitStore.setState({
        snapshot: { ...authoritativeSnapshot, theme: 'day' },
      })
    })

    expect(screen.getByRole('main')).toHaveAttribute('data-theme', 'day')

    act(() => {
      useCockpitStore.setState({
        snapshot: { ...authoritativeSnapshot, revision: 43, theme: 'night' },
      })
    })

    expect(screen.getByRole('main')).toHaveAttribute('data-theme', 'night')
  })
})
