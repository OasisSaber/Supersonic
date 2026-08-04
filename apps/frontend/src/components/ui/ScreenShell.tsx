import { Radio, RefreshCcw, ShieldCheck, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'
import type { CockpitSnapshotV1, EndpointId } from '../../contracts/gp05-v1'
import {
  ENDPOINT_LABELS,
  formatTimestamp,
  snapshotSummary,
  systemModeTone,
} from '../../lib/cockpitPresentation'
import type { ConnectionState } from '../../stores/cockpit'
import { classNames } from '../../lib/classNames'
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
  const needsNotice = !connected || snapshot?.systemMode === 'stale' || snapshot?.systemMode === 'recovery'

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
            {connected ? `REV ${snapshot?.revision ?? '—'}` : '离线降级'}
          </StatusBadge>
          <StatusBadge
            icon={<ShieldCheck size={15} strokeWidth={1.5} />}
            tone={systemModeTone(snapshot?.systemMode)}
          >
            {snapshot?.systemMode ?? 'loading'}
          </StatusBadge>
          <time className="sp-screen-header__time" dateTime={snapshot?.timestamp}>
            {formatTimestamp(snapshot?.timestamp)}
          </time>
        </div>
      </header>

      <DataHealthStrip snapshot={snapshot} />

      {needsNotice ? (
        <div className="sp-service-notice" role="status">
          {connected ? (
            <RefreshCcw size={17} strokeWidth={2} aria-hidden="true" />
          ) : (
            <WifiOff size={17} strokeWidth={2} aria-hidden="true" />
          )}
          <span>
            {connected
              ? '状态恢复中：界面只呈现最近一次通过合同校验的权威快照。'
              : '服务不可用：保留最后权威状态，不生成伪实时数据。'}
          </span>
        </div>
      ) : null}

      <div className="sp-screen-content">{children}</div>
    </section>
  )
}
