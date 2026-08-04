import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
}

export function EmptyState({ description, icon, title }: EmptyStateProps) {
  return (
    <div className="sp-empty-state" role="status">
      <div className="sp-empty-state__icon" aria-hidden="true">{icon}</div>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  )
}
