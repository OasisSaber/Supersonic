import type { ReactNode } from 'react'
import { BatteryCharging, Gauge, Monitor, Navigation2, Users } from 'lucide-react'
import type { CockpitSnapshotV1, RiskEventV1 } from '../../contracts/gp05-v1'
import {
  ENDPOINT_LABELS,
  FLOW_LABELS,
  formatDistance,
  onlineEndpointCount,
} from '../../lib/cockpitPresentation'
import type { ConnectionState } from '../../stores/cockpit'
import { RiskBanner } from '../ui/RiskBanner'

interface OverviewScreenProps {
  activeRisk?: RiskEventV1
  connection: ConnectionState
  snapshot: CockpitSnapshotV1 | null
}

export function OverviewScreen({ activeRisk, connection, snapshot }: OverviewScreenProps) {
  const step = snapshot?.navigation.currentStep
  const online = onlineEndpointCount(snapshot)

  return (
    <div className="sp-overview-layout">
      <section className="sp-overview-summary" aria-label="多屏权威状态摘要">
        <div>
          <Monitor size={21} strokeWidth={1.5} aria-hidden="true" />
          <span>连接端点</span>
          <strong className="sp-tabular">{snapshot ? `${online}/6` : '—/6'}</strong>
        </div>
        <div>
          <Gauge size={21} strokeWidth={1.5} aria-hidden="true" />
          <span>权威修订</span>
          <strong className="sp-tabular">{snapshot?.revision ?? '—'}</strong>
        </div>
        <div>
          <Users size={21} strokeWidth={1.5} aria-hidden="true" />
          <span>当前流程</span>
          <strong>{snapshot ? FLOW_LABELS[snapshot.activeFlow] : '等待状态'}</strong>
        </div>
      </section>

      <div className="sp-overview-grid">
        <PreviewCard endpoint="cluster">
          {snapshot ? (
            <>
              <div className="sp-preview-speed sp-tabular">{snapshot.vehicle.speedKph}</div>
              <span>km/h · {snapshot.vehicle.gear}</span>
              <div className="sp-preview-inline">
                <BatteryCharging size={18} strokeWidth={1.5} />
                {snapshot.vehicle.rangeKm} km
              </div>
            </>
          ) : <UnavailablePreview />}
        </PreviewCard>

        <PreviewCard endpoint="hud">
          {snapshot ? (
            <>
              <Navigation2 size={30} strokeWidth={1.5} aria-hidden="true" />
              <strong>{activeRisk?.message ?? step?.instruction ?? '保持当前车道'}</strong>
              <span className="sp-tabular">{formatDistance(step?.distanceMeters)}</span>
            </>
          ) : <UnavailablePreview />}
        </PreviewCard>

        <PreviewCard endpoint="center">
          {snapshot ? (
            <>
              <div className="sp-preview-route" aria-hidden="true"><span /><span /><span /></div>
              <strong>{snapshot.navigation.destinationName ?? '未设置目的地'}</strong>
              <span>{snapshot.navigation.status} · read only</span>
            </>
          ) : <UnavailablePreview />}
        </PreviewCard>

        <PreviewCard endpoint="passenger">
          {snapshot ? (
            <>
              <strong>{snapshot.passenger.mediaState}</strong>
              <span>{snapshot.passenger.privacyEnabled ? '隐私模式开启' : '允许共享旅程内容'}</span>
              <div className="sp-preview-inline">建议 {snapshot.passenger.tripSuggestions.length} 条</div>
            </>
          ) : <UnavailablePreview />}
        </PreviewCard>
      </div>

      {activeRisk ? <RiskBanner risk={activeRisk} /> : null}
      <p className="sp-overview-footnote">
        {connection === 'connected'
          ? '所有预览只消费同一 FastAPI 权威快照；Overview 不加载任何命令 Hook。'
          : '等待权威快照；不使用客户端推测值填充驾驶信息。'}
      </p>
    </div>
  )
}

function UnavailablePreview() {
  return (
    <>
      <strong>等待权威快照</strong>
      <span>暂不显示客户端推测值</span>
    </>
  )
}

function PreviewCard({
  children,
  endpoint,
}: {
  children: ReactNode
  endpoint: 'cluster' | 'hud' | 'center' | 'passenger'
}) {
  return (
    <article className={`sp-preview-card sp-preview-card--${endpoint}`}>
      <header>
        <span>{ENDPOINT_LABELS[endpoint]}</span>
        <small>只读预览</small>
      </header>
      <div className="sp-preview-card__body">{children}</div>
    </article>
  )
}
