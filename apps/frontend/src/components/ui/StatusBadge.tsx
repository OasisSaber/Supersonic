import type { ReactNode } from 'react'
import { classNames } from '../../lib/classNames'

type StatusTone = 'neutral' | 'accent' | 'success' | 'warning' | 'critical'

interface StatusBadgeProps {
  children: ReactNode
  icon?: ReactNode
  tone?: StatusTone
}

export function StatusBadge({ children, icon, tone = 'neutral' }: StatusBadgeProps) {
  return (
    <span className={classNames('sp-status-badge', `sp-status-badge--${tone}`)}>
      {icon ? <span className="sp-status-badge__icon" aria-hidden="true">{icon}</span> : null}
      <span>{children}</span>
    </span>
  )
}
