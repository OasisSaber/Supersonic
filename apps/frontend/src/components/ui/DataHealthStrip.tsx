import { Activity, Map, RadioTower } from 'lucide-react'
import type { CockpitSnapshotV1, DataFreshness } from '../../contracts/gp05-v1'
import { FRESHNESS_LABELS, freshnessTone } from '../../lib/cockpitPresentation'
import { StatusBadge } from './StatusBadge'

const domains = [
  { key: 'vehicle', label: '车辆', icon: <Activity size={15} strokeWidth={1.5} /> },
  { key: 'navigation', label: '导航', icon: <Map size={15} strokeWidth={1.5} /> },
  { key: 'vision', label: '视觉', icon: <RadioTower size={15} strokeWidth={1.5} /> },
] as const

export function DataHealthStrip({ snapshot }: { snapshot: CockpitSnapshotV1 | null }) {
  return (
    <div className="sp-health-strip" aria-label="数据健康状态">
      {domains.map(({ icon, key, label }) => {
        const status: DataFreshness = snapshot?.dataHealth[key]?.status ?? 'offline'
        return (
          <StatusBadge key={key} icon={icon} tone={freshnessTone(status)}>
            {label} · {FRESHNESS_LABELS[status]}
          </StatusBadge>
        )
      })}
    </div>
  )
}
