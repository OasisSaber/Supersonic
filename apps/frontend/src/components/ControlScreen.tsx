import { RotateCcw, Settings2 } from 'lucide-react'
import type { CockpitSnapshotV1, EndpointId, SystemMode } from '../contracts/gp05-v1'
import { ENDPOINTS } from '../contracts/gp05-v1'
import { useCockpitCommand } from '../lib/useCockpitCommand'
import { useControlAvailability } from '../lib/useControlAvailability'

interface Props {
  snapshot: CockpitSnapshotV1 | null
}

const endpointNames: Record<EndpointId, string> = {
  cluster: '主仪表',
  hud: 'HUD',
  center: '中控',
  passenger: '副驾',
  overview: '四屏总览',
  control: '控制台',
}

export function ControlScreen({ snapshot }: Props) {
  const availability = useControlAvailability()
  const { send, pending, error } = useCockpitCommand('control')
  const commandsDisabled = availability !== 'enabled' || pending || snapshot === null

  return <div className="control-layout">
    <section className="control-summary" aria-label="权威运行状态">
      <div><span>Session ID</span><b>{snapshot?.sessionId ?? '等待权威 snapshot'}</b></div>
      <div><span>Revision</span><b>{snapshot?.revision ?? '—'}</b></div>
      <div><span>System mode</span><b>{snapshot?.systemMode ?? '—'}</b></div>
      <div><span>Theme</span><b>{snapshot?.theme ?? '—'}</b></div>
    </section>

    <section className="control-panel" aria-label="Control 命令">
      <div className={`control-availability is-${availability}`} role="status">
        <Settings2 size={18} />{availabilityMessage(availability)}
      </div>
      <ControlGroup label="主题">
        {(['day', 'night'] as const).map((theme) => <button key={theme} className="secondary-button" disabled={commandsDisabled || snapshot?.theme === theme} onClick={() => void send('set_theme', { theme })}>{theme === 'day' ? '日间主题' : '夜间主题'}</button>)}
      </ControlGroup>
      <ControlGroup label="系统模式">
        {(['normal', 'warning', 'takeover'] as const).map((mode) => <button key={mode} className="secondary-button" disabled={commandsDisabled || snapshot?.systemMode === mode} onClick={() => void send('set_system_mode', { mode })}>{systemModeName(mode)}</button>)}
      </ControlGroup>
      <button className="primary-button" disabled={commandsDisabled} onClick={() => void send('reset_session', {})}><RotateCcw size={17} />重置权威会话</button>
      {error && <p className="command-error" role="alert">{error}</p>}
    </section>

    <section className="endpoint-status-panel" aria-label="端点连接状态">
      <h2>端点连接</h2>
      <ul>{ENDPOINTS.map((endpoint) => {
        const status = snapshot?.endpointConnectivity[endpoint]?.status ?? 'offline'
        return <li key={endpoint}><span>{endpointNames[endpoint]}</span><b className={`status-${status}`}>{status}</b></li>
      })}</ul>
    </section>
  </div>
}

function ControlGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return <fieldset><legend>{label}</legend><div className="control-actions">{children}</div></fieldset>
}

function availabilityMessage(availability: ReturnType<typeof useControlAvailability>) {
  if (availability === 'checking') return '正在核验本地 Control 配置'
  if (availability === 'enabled') return '本地 Control 命令已启用'
  if (availability === 'disabled') return 'Control 命令未启用；请在本地配置 CONTROL_ENABLED=true'
  return '无法核验 Control 配置；命令保持禁用'
}

function systemModeName(mode: SystemMode) {
  const names: Partial<Record<SystemMode, string>> = {
    normal: '正常模式',
    warning: '告警模式',
    takeover: '接管演示',
  }
  return names[mode] ?? mode
}
