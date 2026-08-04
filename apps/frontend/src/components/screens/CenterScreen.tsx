import { Check, Eye, MapPin, Navigation2, Route, ShieldAlert } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import type { CockpitSnapshotV1, RiskEventV1 } from '../../contracts/gp05-v1'
import { useCockpitCommand } from '../../lib/useCockpitCommand'
import {
  formatDistance,
  formatEta,
  navigationSourceLabel,
  riskSourceLabel,
} from '../../lib/cockpitPresentation'
import { ActionButton } from '../ui/ActionButton'
import { EmptyState } from '../ui/EmptyState'
import { MetricTile } from '../ui/MetricTile'
import { RiskBanner } from '../ui/RiskBanner'

interface CenterScreenProps {
  activeRisk?: RiskEventV1
  snapshot: CockpitSnapshotV1 | null
}

export function CenterScreen({ activeRisk, snapshot }: CenterScreenProps) {
  const { error, pendingCommand, send } = useCockpitCommand('center')
  const [destination, setDestination] = useState('城市艺术中心')
  const routeReady = snapshot?.navigation.status === 'preview'

  return (
    <div className="sp-center-layout">
      <section className="sp-map-panel" aria-label="路线规划">
        <div className="sp-map-panel__visual" aria-hidden="true">
          <div className="sp-map-grid" />
          <div className="sp-route-line"><span /><span /><span /></div>
          <MapPin className="sp-map-pin" size={30} strokeWidth={2} />
        </div>

        <div className="sp-map-panel__content">
          <p className="sp-eyebrow">Navigation handoff</p>
          <h2>{snapshot?.navigation.destinationName ?? '规划下一段行程'}</h2>
          <p>{navigationSourceLabel(snapshot)}</p>

          {snapshot?.navigation.destinationName ? (
            <div className="sp-inline-metrics" aria-label="路线摘要">
              <span><b className="sp-tabular">{formatDistance(snapshot.navigation.remainingDistanceMeters)}</b> 剩余</span>
              <span><b className="sp-tabular">{formatEta(snapshot.navigation.etaSeconds)}</b> 预计</span>
              <span><b>{snapshot.navigation.status}</b> 状态</span>
            </div>
          ) : null}

          <form
            className="sp-command-form"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault()
              void send('select_destination', { destinationName: destination })
            }}
          >
            <label htmlFor="destination">目的地</label>
            <div className="sp-field-row">
              <input
                id="destination"
                aria-describedby="destination-help"
                maxLength={160}
                onChange={(event: ChangeEvent<HTMLInputElement>) => setDestination(event.target.value)}
                value={destination}
              />
              <ActionButton
                disabled={!destination.trim()}
                icon={<Route size={18} strokeWidth={2} />}
                pending={pendingCommand === 'select_destination'}
                type="submit"
                variant="primary"
              >
                规划路线
              </ActionButton>
            </div>
            <small id="destination-help">使用本地确定性路线验证跨屏接力，不冒充实时地图。</small>
          </form>

          {routeReady ? (
            <ActionButton
              className="sp-map-panel__confirm"
              icon={<Navigation2 size={18} strokeWidth={2} />}
              pending={pendingCommand === 'confirm_route'}
              onClick={() => void send('confirm_route', {})}
              variant="secondary"
            >
              确认并接力至主仪表与 HUD
            </ActionButton>
          ) : null}
        </div>
      </section>

      <aside className="sp-center-rail">
        <MetricTile
          icon={<Eye size={22} strokeWidth={1.5} />}
          label="VehicleVision"
          value={activeRisk ? riskSourceLabel(activeRisk.source) : '无活动风险'}
          detail={activeRisk ? `${Math.round(activeRisk.confidence * 100)}% · ${activeRisk.lifecycle}` : '当前来源：离线'}
        />

        {activeRisk ? (
          <section className="sp-risk-workflow" aria-label="风险处置">
            <RiskBanner risk={activeRisk} />
            <div className="sp-risk-workflow__steps" aria-hidden="true">
              <span className="is-complete"><Check size={14} />检测</span>
              <span className={activeRisk.lifecycle !== 'active' ? 'is-complete' : ''}>确认</span>
              <span className={activeRisk.lifecycle === 'resolved' ? 'is-complete' : ''}>恢复</span>
            </div>
            {activeRisk.lifecycle === 'active' ? (
              <ActionButton
                icon={<ShieldAlert size={18} strokeWidth={2} />}
                pending={pendingCommand === 'acknowledge_risk'}
                onClick={() => void send('acknowledge_risk', { eventId: activeRisk.eventId })}
                variant="danger"
              >
                确认告警
              </ActionButton>
            ) : null}
            {activeRisk.lifecycle === 'acknowledged' ? (
              <ActionButton
                icon={<Check size={18} strokeWidth={2} />}
                pending={pendingCommand === 'resolve_risk'}
                onClick={() => void send('resolve_risk', { eventId: activeRisk.eventId })}
                variant="primary"
              >
                完成处置并恢复
              </ActionButton>
            ) : null}
          </section>
        ) : (
          <EmptyState
            icon={<ShieldAlert size={24} strokeWidth={1.5} />}
            title="风险处置待命"
            description="Control 触发模拟接管后，此处呈现完整确认与恢复流程。"
          />
        )}

        {error ? <p className="sp-inline-error" role="alert">{error}</p> : null}
      </aside>
    </div>
  )
}
