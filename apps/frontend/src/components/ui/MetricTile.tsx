import type { ReactNode } from 'react'

interface MetricTileProps {
  icon: ReactNode
  label: string
  value: ReactNode
  detail?: ReactNode
}

export function MetricTile({ detail, icon, label, value }: MetricTileProps) {
  return (
    <article className="sp-metric">
      <div className="sp-metric__icon" aria-hidden="true">{icon}</div>
      <div className="sp-metric__copy">
        <span>{label}</span>
        <strong className="sp-tabular">{value}</strong>
        {detail ? <small>{detail}</small> : null}
      </div>
    </article>
  )
}
