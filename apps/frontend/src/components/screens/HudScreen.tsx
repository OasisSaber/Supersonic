import { Navigation2, ShieldCheck } from 'lucide-react'
import type { CockpitSnapshotV1, RiskEventV1 } from '../../contracts/gp05-v1'
import { formatDistance } from '../../lib/cockpitPresentation'
import { RiskBanner } from '../ui/RiskBanner'

interface HudScreenProps {
  activeRisk?: RiskEventV1
  snapshot: CockpitSnapshotV1 | null
}

export function HudScreen({ activeRisk, snapshot }: HudScreenProps) {
  if (activeRisk) {
    return (
      <div className="sp-hud-layout sp-hud-layout--risk">
        <RiskBanner risk={activeRisk} />
        <p className="sp-hud-assist">保持视线前方，按中控提示完成处置。</p>
      </div>
    )
  }

  const step = snapshot?.navigation.currentStep
  return (
    <div className="sp-hud-layout">
      <div className="sp-hud-direction" aria-hidden="true">
        {step ? <Navigation2 size={48} strokeWidth={1.5} /> : <ShieldCheck size={48} strokeWidth={1.5} />}
      </div>
      <div className="sp-hud-copy">
        <span>{step ? '下一步驾驶行动' : '驾驶状态'}</span>
        <strong>{step?.instruction ?? '保持当前车道'}</strong>
        <p>{step?.roadName ?? '当前无活动风险'}</p>
      </div>
      <b className="sp-hud-distance sp-tabular">{formatDistance(step?.distanceMeters)}</b>
    </div>
  )
}
