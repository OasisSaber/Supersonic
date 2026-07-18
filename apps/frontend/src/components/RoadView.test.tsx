import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RoadView } from './RoadView'

describe('RoadView', () => {
  it('provides a local video import control while keeping the Mock fallback', () => {
    render(<RoadView frame={null} />)

    expect(screen.getByLabelText('导入本地行车视频')).toHaveAttribute('accept', 'video/*')
    expect(screen.getByText(/本地行车视频 · Mock/)).toBeInTheDocument()
  })
})
