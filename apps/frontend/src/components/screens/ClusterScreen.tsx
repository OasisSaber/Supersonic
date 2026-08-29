import { BatteryCharging, Gauge, Navigation2, Route } from 'lucide-react'
import type { CockpitSnapshotV1, RiskEventV1 } from '../../contracts/gp05-v1'
import { formatDistance, formatEta, navigationSourceLabel } from '../../lib/cockpitPresentation'
import { EmptyState } from '../ui/EmptyState'
import { MetricTile } from '../ui/MetricTile'
import { RiskBanner } from '../ui/RiskBanner'

interface ClusterScreenProps {
  activeRisk?: RiskEventV1
  snapshot: CockpitSnapshotV1 | null
}

export function ClusterScreen({ activeRisk, snapshot }: ClusterScreenProps) {
  const step = snapshot?.navigation.currentStep

  return (
    <div className="sp-cluster-layout">
      <div className="sp-cluster-layout__metrics">
        <MetricTile
          icon={<BatteryCharging size={22} strokeWidth={1.5} />}
          label="剩余续航"
          value={`${snapshot?.vehicle.rangeKm ?? '—'} km`}
          detail={`${snapshot?.vehicle.batteryPercent ?? '—'}% 电量`}
        />
        <MetricTile
          icon={<Gauge size={22} strokeWidth={1.5} />}
          label="驾驶模式"
          value={snapshot?.vehicle.driveMode ?? '—'}
          detail={
            snapshot === null
              ? '等待权威状态'
              : snapshot.vehicle.seatbeltFastened ? '安全带已系' : '安全带未系'
          }
        />
      </div>

      <section className="sp-speed-dial" aria-label="当前车速">
        <span className="sp-speed-dial__gear">{snapshot?.vehicle.gear ?? '—'}</span>
        <strong className="sp-tabular">{snapshot?.vehicle.speedKph ?? '—'}</strong>
        <small>km/h</small>
        <div className="sp-speed-dial__track" aria-hidden="true"><span /></div>
      </section>

      <div className="sp-cluster-layout__route">
        {snapshot === null ? (
          <EmptyState
            icon={<Route size={24} strokeWidth={1.5} />}
            title="路线数据暂不可用"
            description="正在等待第一份权威快照，不显示推测的路线状态。"
          />
        ) : step ? (
          <article className="sp-route-card">
            <div className="sp-route-card__icon" aria-hidden="true">
              <Navigation2 size={28} strokeWidth={1.5} />
            </div>
            <span>下一步 · {navigationSourceLabel(snapshot)}</span>
            <strong>{step.instruction}</strong>
            <p>{step.roadName}</p>
            <div className="sp-route-card__metrics">
              <b className="sp-tabular">{formatDistance(step.distanceMeters)}</b>
              <small>{formatEta(snapshot?.navigation.etaSeconds)} 到达</small>
            </div>
          </article>
        ) : (
          <EmptyState
            icon={<Route size={24} strokeWidth={1.5} />}
            title="等待路线接力"
            description="在中控规划并确认路线后，此处显示下一步驾驶行动。"
          />
        )}
        {activeRisk ? <RiskBanner compact risk={activeRisk} /> : null}
      </div>
    </div>
  )
}
