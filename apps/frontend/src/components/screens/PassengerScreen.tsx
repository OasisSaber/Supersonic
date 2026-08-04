import { EyeOff, Pause, Play, Send, ShieldCheck, Sparkles } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import type { CockpitSnapshotV1, RiskEventV1 } from '../../contracts/gp05-v1'
import { isMediaSafetySuppressed } from '../../lib/riskSelection'
import { useCockpitCommand } from '../../lib/useCockpitCommand'
import { ActionButton } from '../ui/ActionButton'
import { RiskBanner } from '../ui/RiskBanner'

interface PassengerScreenProps {
  activeRisk?: RiskEventV1
  snapshot: CockpitSnapshotV1 | null
}

export function PassengerScreen({ activeRisk, snapshot }: PassengerScreenProps) {
  const { error, pendingCommand, send } = useCockpitCommand('passenger')
  const [suggestion, setSuggestion] = useState('建议在城市艺术中心短暂停留')
  const suppressed = isMediaSafetySuppressed(snapshot?.risks ?? [])
  const playing = snapshot?.passenger.mediaState === 'playing'
  const privacyEnabled = snapshot?.passenger.privacyEnabled ?? true

  return (
    <div className="sp-passenger-layout">
      <section className={suppressed ? 'sp-media-stage is-suppressed' : 'sp-media-stage'}>
        <div className="sp-media-stage__art" aria-hidden="true">
          <div className="sp-media-stage__orb" />
          <Sparkles size={40} strokeWidth={1.25} />
        </div>
        <div className="sp-media-stage__copy">
          <p className="sp-eyebrow">Passenger media</p>
          <h2>{suppressed ? '媒体已安全抑制' : playing ? '旅程媒体播放中' : '旅程媒体已暂停'}</h2>
          <p>
            {suppressed
              ? '驾驶风险处置期间，副驾娱乐控制暂时不可用。'
              : '娱乐与旅程协作不影响驾驶关键状态。'}
          </p>
          <ActionButton
            disabled={suppressed}
            icon={playing ? <Pause size={18} strokeWidth={2} /> : <Play size={18} strokeWidth={2} />}
            pending={pendingCommand === 'set_media_state'}
            onClick={() => void send('set_media_state', { state: playing ? 'paused' : 'playing' })}
            variant="secondary"
          >
            {playing ? '暂停媒体' : '播放媒体'}
          </ActionButton>
        </div>
      </section>

      <aside className="sp-passenger-rail">
        <section className="sp-control-card">
          <div className="sp-control-card__heading">
            <div className="sp-control-card__icon" aria-hidden="true">
              {privacyEnabled ? <EyeOff size={22} strokeWidth={1.5} /> : <ShieldCheck size={22} strokeWidth={1.5} />}
            </div>
            <div>
              <span>隐私模式</span>
              <strong>{privacyEnabled ? '副驾内容不投射至驾驶端' : '允许共享必要旅程内容'}</strong>
            </div>
          </div>
          <ActionButton
            pending={pendingCommand === 'set_cabin_control'}
            onClick={() => void send('set_cabin_control', { privacyEnabled: !privacyEnabled })}
            variant="ghost"
          >
            {privacyEnabled ? '关闭隐私' : '开启隐私'}
          </ActionButton>
        </section>

        <form
          className="sp-control-card sp-suggestion-form"
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault()
            void send('submit_trip_suggestion', { suggestion })
          }}
        >
          <label htmlFor="trip-suggestion">旅程建议</label>
          <textarea
            id="trip-suggestion"
            maxLength={200}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setSuggestion(event.target.value)}
            rows={4}
            value={suggestion}
          />
          <div className="sp-suggestion-form__footer">
            <small className="sp-tabular">{suggestion.length}/200</small>
            <ActionButton
              disabled={!suggestion.trim()}
              icon={<Send size={17} strokeWidth={2} />}
              pending={pendingCommand === 'submit_trip_suggestion'}
              type="submit"
              variant="primary"
            >
              发送旅程建议
            </ActionButton>
          </div>
        </form>

        {activeRisk ? <RiskBanner compact risk={activeRisk} /> : null}
        {error ? <p className="sp-inline-error" role="alert">{error}</p> : null}
      </aside>
    </div>
  )
}
