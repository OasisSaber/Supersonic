import type { ReactNode } from 'react'
import {
  AlertTriangle,
  Moon,
  Radio,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Sun,
} from 'lucide-react'
import type { CockpitSnapshotV1, EndpointId, SystemMode } from '../../contracts/gp05-v1'
import { ENDPOINTS } from '../../contracts/gp05-v1'
import { ENDPOINT_LABELS, FRESHNESS_LABELS, SYSTEM_MODE_LABELS } from '../../lib/cockpitPresentation'
import { isMediaSafetySuppressed } from '../../lib/riskSelection'
import { useCockpitCommand } from '../../lib/useCockpitCommand'
import { useControlAvailability } from '../../lib/useControlAvailability'
import { ActionButton } from '../ui/ActionButton'

interface ControlScreenProps {
  snapshot: CockpitSnapshotV1 | null
}

export function ControlScreen({ snapshot }: ControlScreenProps) {
  const availability = useControlAvailability()
  const { error, pending, pendingCommand, send } = useCockpitCommand('control')
  const commandsDisabled = availability !== 'enabled' || pending || snapshot === null
  const takeoverLocked = isMediaSafetySuppressed(snapshot?.risks ?? [])

  return (
    <div className="sp-control-layout">
      <section className="sp-control-summary" aria-label="权威运行状态">
        <SummaryItem label="Session" value={snapshot?.sessionId ?? '等待权威快照'} mono />
        <SummaryItem label="Revision" value={snapshot?.revision ?? '—'} mono />
        <SummaryItem label="System mode" value={snapshot ? SYSTEM_MODE_LABELS[snapshot.systemMode] : '—'} />
        <SummaryItem label="Theme" value={snapshot ? (snapshot.theme === 'day' ? '日间' : '夜间') : '—'} />
      </section>

      <section className="sp-control-panel" aria-label="演示控制命令">
        <div className={`sp-control-availability is-${availability}`} role="status">
          <Settings2 size={20} strokeWidth={1.5} aria-hidden="true" />
          <div>
            <span>Control access</span>
            <strong>{availabilityMessage(availability)}</strong>
          </div>
        </div>

        <ControlGroup label="显示主题" description="主题由服务端确认后同步到全部端点。">
          <ActionButton
            disabled={commandsDisabled || snapshot?.theme === 'day'}
            icon={<Sun size={18} strokeWidth={2} />}
            pending={pendingCommand === 'set_theme' && snapshot?.theme !== 'day'}
            onClick={() => void send('set_theme', { theme: 'day' })}
          >
            日间主题
          </ActionButton>
          <ActionButton
            disabled={commandsDisabled || snapshot?.theme === 'night'}
            icon={<Moon size={18} strokeWidth={2} />}
            pending={pendingCommand === 'set_theme' && snapshot?.theme !== 'night'}
            onClick={() => void send('set_theme', { theme: 'night' })}
          >
            夜间主题
          </ActionButton>
        </ControlGroup>

        <ControlGroup
          label="系统模式"
          description={
            takeoverLocked
              ? '存在未解决关键风险；完成处置前不能退出接管模式。'
              : '用于答辩演示状态切换；不绕过后端风险不变量。'
          }
        >
          {(['normal', 'warning', 'takeover'] as const).map((mode) => (
            <ActionButton
              key={mode}
              disabled={
                commandsDisabled ||
                snapshot?.systemMode === mode ||
                (takeoverLocked && mode !== 'takeover')
              }
              icon={modeIcon(mode)}
              pending={pendingCommand === 'set_system_mode' && snapshot?.systemMode !== mode}
              onClick={() => void send('set_system_mode', { mode })}
              variant={mode === 'takeover' ? 'danger' : 'secondary'}
            >
              {SYSTEM_MODE_LABELS[mode]}
            </ActionButton>
          ))}
        </ControlGroup>

        <div className="sp-control-panel__danger-zone">
          <div>
            <span>会话重置</span>
            <p>创建新 session，并让所有已连接端点收敛到同一初始快照。</p>
          </div>
          <ActionButton
            disabled={commandsDisabled}
            icon={<RotateCcw size={18} strokeWidth={2} />}
            pending={pendingCommand === 'reset_session'}
            onClick={() => void send('reset_session', {})}
            variant="danger"
          >
            重置权威会话
          </ActionButton>
        </div>

        {error ? <p className="sp-inline-error" role="alert">{error}</p> : null}
      </section>

      <section className="sp-endpoint-panel" aria-label="端点连接状态">
        <header>
          <div>
            <span>Endpoint status</span>
            <h2>端点连接</h2>
          </div>
          <Radio size={21} strokeWidth={1.5} aria-hidden="true" />
        </header>
        <ul>
          {ENDPOINTS.map((endpoint) => (
            <EndpointRow
              endpoint={endpoint}
              key={endpoint}
              status={snapshot?.endpointConnectivity[endpoint]?.status ?? 'offline'}
            />
          ))}
        </ul>
      </section>
    </div>
  )
}

function SummaryItem({ label, mono = false, value }: { label: string; mono?: boolean; value: ReactNode }) {
  return (
    <div>
      <span>{label}</span>
      <strong className={mono ? 'sp-mono sp-tabular' : undefined}>{value}</strong>
    </div>
  )
}

function ControlGroup({
  children,
  description,
  label,
}: {
  children: ReactNode
  description: string
  label: string
}) {
  return (
    <fieldset className="sp-control-group">
      <legend>{label}</legend>
      <p>{description}</p>
      <div>{children}</div>
    </fieldset>
  )
}

function EndpointRow({
  endpoint,
  status,
}: {
  endpoint: EndpointId
  status: 'fresh' | 'stale' | 'offline'
}) {
  return (
    <li>
      <span>{ENDPOINT_LABELS[endpoint]}</span>
      <b className={`sp-endpoint-status is-${status}`}>{FRESHNESS_LABELS[status]}</b>
    </li>
  )
}

function modeIcon(mode: SystemMode) {
  if (mode === 'takeover') return <AlertTriangle size={18} strokeWidth={2} />
  return <ShieldCheck size={18} strokeWidth={2} />
}

function availabilityMessage(availability: ReturnType<typeof useControlAvailability>) {
  if (availability === 'checking') return '正在核验本地配置'
  if (availability === 'enabled') return '本地控制命令已启用'
  if (availability === 'disabled') return 'CONTROL_ENABLED 未启用，命令保持禁用'
  return '无法核验配置，命令保持禁用'
}
