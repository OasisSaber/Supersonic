import { AlertTriangle, CheckCircle2, ChevronRight } from 'lucide-react'
import type { RiskEventV1 } from '../../contracts/gp05-v1'
import { riskSourceLabel } from '../../lib/cockpitPresentation'
import { classNames } from '../../lib/classNames'

interface RiskBannerProps {
  compact?: boolean
  risk: RiskEventV1
}

export function RiskBanner({ compact = false, risk }: RiskBannerProps) {
  const acknowledged = risk.lifecycle === 'acknowledged'
  return (
    <article
      className={classNames(
        'sp-risk-banner',
        `sp-risk-banner--${risk.severity}`,
        compact && 'sp-risk-banner--compact',
      )}
      role={risk.severity === 'critical' ? 'alert' : 'status'}
    >
      <div className="sp-risk-banner__icon" aria-hidden="true">
        {acknowledged ? (
          <CheckCircle2 size={22} strokeWidth={2} />
        ) : (
          <AlertTriangle size={22} strokeWidth={2} />
        )}
      </div>
      <div className="sp-risk-banner__copy">
        <span>{acknowledged ? '风险已确认 · 等待处置' : '驾驶关键告警'}</span>
        <strong>{risk.message}</strong>
        <small className="sp-tabular">
          {riskSourceLabel(risk.source)} · {Math.round(risk.confidence * 100)}% · {risk.lifecycle}
        </small>
      </div>
      <ChevronRight className="sp-risk-banner__chevron" size={20} aria-hidden="true" />
    </article>
  )
}
