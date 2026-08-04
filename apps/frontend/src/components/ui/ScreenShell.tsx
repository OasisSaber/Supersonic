import {
  CloudOff,
  Radio,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  WifiOff,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { CockpitSnapshotV1, EndpointId, SystemMode } from '../../contracts/gp05-v1'
import { classNames } from '../../lib/classNames'
import {
  ENDPOINT_LABELS,
  formatTimestamp,
  snapshotSummary,
  systemModeTone,
  SYSTEM_MODE_LABELS,
} from '../../lib/cockpitPresentation'
import type { ConnectionState } from '../../stores/cockpit'
import { DataHealthStrip } from './DataHealthStrip'
import { StatusBadge } from './StatusBadge'

interface ScreenShellProps {
  children: ReactNode
  connection: ConnectionState
  endpoint: EndpointId
  snapshot: CockpitSnapshotV1 | null
}

export function ScreenShell({ children, connection, endpoint, snapshot }: ScreenShellProps) {
  const connected = connection === 'connected'
  const notice = serviceNotice(connection, snapshot?.systemMode)

  return (
    <section className={classNames('sp-screen-shell', `sp-endpoint-${endpoint}`)}>
      <header className="sp-screen-header">
        <div className="sp-screen-header__brand">
          <div className="sp-brand-mark" aria-hidden="true">S</div>
          <div>
            <p className="sp-eyebrow">Supersonic · GP22</p>
            <h1>{ENDPOINT_LABELS[endpoint]}</h1>
            <p className="sp-screen-header__summary">{snapshotSummary(snapshot)}</p>
          </div>
        </div>

        <div className="sp-screen-header__status">
          <StatusBadge
            icon={connected ? <Radio size={15} strokeWidth={1.5} /> : <WifiOff size={15} strokeWidth={1.5} />}
            tone={connected ? 'success' : 'warning'}
          >
            {connected ? `REV ${snapshot?.revision ?? '—'}` : '连接中断'}
          </StatusBadge>
          <StatusBadge
            icon={<ShieldCheck size={15} strokeWidth={1.5} />}
            tone={systemModeTone(snapshot?.systemMode)}
          >
            {snapshot ? SYSTEM_MODE_LABELS[snapshot.systemMode] : '等待状态'}
          </StatusBadge>
          <time className="sp-screen-header__time" dateTime={snapshot?.timestamp}>
            {formatTimestamp(snapshot?.timestamp)}
          </time>
        </div>
      </header>

      <DataHealthStrip snapshot={snapshot} />

      {notice ? (
        <div className={classNames('sp-service-notice', `is-${notice.tone}`)} role="status">
          <notice.Icon size={17} strokeWidth={2} aria-hidden="true" />
          <span>{notice.message}</span>
        </div>
      ) : null}

      <div className="sp-screen-content">{children}</div>
    </section>
  )
}

function serviceNotice(connection: ConnectionState, mode?: SystemMode) {
  if (connection !== 'connected') {
    return {
      Icon: WifiOff,
      tone: 'offline',
      message: '连接中断：保留最后一次权威快照，不生成伪实时数据。',
    } as const
  }
  if (mode === 'offline') {
    return {
      Icon: CloudOff,
      tone: 'offline',
      message: '服务离线：部分数据域不可用，驾驶关键内容保持明确降级。',
    } as const
  }
  if (mode === 'stale') {
    return {
      Icon: RotateCcw,
      tone: 'stale',
      message: '数据滞后：当前值来自最近一次通过合同校验的权威快照。',
    } as const
  }
  if (mode === 'recovery') {
    return {
      Icon: RefreshCcw,
      tone: 'recovery',
      message: '状态恢复中：等待全部端点收敛到同一 session 与 revision。',
    } as const
  }
  return null
}
