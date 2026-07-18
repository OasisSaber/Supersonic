import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { RiskBanner } from './RiskBanner'

test('renders high risk composite event', () => {
  render(
    <RiskBanner
      risk={{
        event: 'pedestrian_and_distraction',
        level: 'high',
        timestamp: 125.6,
        message: '前方检测到行人且驾驶员注意力偏移',
        evidence: ['前方行人', '驾驶员注意力偏移'],
      }}
    />,
  )
  expect(screen.getByText('前方检测到行人且驾驶员注意力偏移')).toBeInTheDocument()
  expect(screen.getByText('high')).toBeInTheDocument()
})
