import {
  Activity,
  CheckCircle2,
  Clock3,
  Map,
  RadioTower,
  WifiOff,
} from 'lucide-react'
import type { CockpitSnapshotV1, DataFreshness } from '../../contracts/gp05-v1'
import { FRESHNESS_LABELS, freshnessTone } from '../../lib/cockpitPresentation'
import { StatusBadge } from './StatusBadge'

const domains = [
  { key: 'vehicle', label: '车辆', icon: Activity },
  { key: 'navigation', label: '导航', icon: Map },
  { key: 'vision', label: '视觉', icon: RadioTower },
] as const

export function DataHealthStrip({ snapshot }: { snapshot: CockpitSnapshotV1 | null }) {
  return (
    <div className="sp-health-strip" aria-label="数据健康状态">
      {domains.map(({ icon: DomainIcon, key, label }) => {
        if (!snapshot) {
          return (
            <StatusBadge key={key} tone="neutral">
              <span className="sp-health-strip__domain" aria-hidden="true">
                <DomainIcon size={15} strokeWidth={1.5} />
                <Clock3 size={14} strokeWidth={2} />
              </span>
              {label} · 等待
            </StatusBadge>
          )
        }
        const status: DataFreshness = snapshot.dataHealth[key]?.status ?? 'offline'
        const StateIcon = freshnessIcon(status)
        return (
          <StatusBadge key={key} tone={freshnessTone(status)}>
            <span className="sp-health-strip__domain" aria-hidden="true">
              <DomainIcon size={15} strokeWidth={1.5} />
              <StateIcon size={14} strokeWidth={2} />
            </span>
            {label} · {FRESHNESS_LABELS[status]}
          </StatusBadge>
        )
      })}
    </div>
  )
}

function freshnessIcon(status: DataFreshness) {
  if (status === 'fresh') return CheckCircle2
  if (status === 'stale') return Clock3
  return WifiOff
}
