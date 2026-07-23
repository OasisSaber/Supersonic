import {
  AlertTriangle,
  Battery,
  ChevronRight,
  Eye,
  Gauge,
  MapPin,
  Navigation,
  PauseCircle,
  Radio,
  ShieldAlert,
  WifiOff,
} from 'lucide-react'
import { useState } from 'react'
import type { CockpitSnapshotV1, EndpointId, RiskEventV1 } from '../contracts/gp05-v1'
import { useCockpitCommand } from '../lib/useCockpitCommand'
import type { ConnectionState } from '../stores/cockpit'

interface Props {
  endpoint: EndpointId
  snapshot: CockpitSnapshotV1 | null
  connection: ConnectionState
}

const endpointNames: Record<EndpointId, string> = {
  cluster: '主仪表', hud: 'HUD', center: '中控', passenger: '副驾', overview: '四屏总览', control: '控制台',
}

export function CockpitScreen({ endpoint, snapshot, connection }: Props) {
  const activeRisk = snapshot?.risks.find((risk) => risk.lifecycle !== 'resolved')
  const offline = connection === 'offline' || snapshot?.systemMode === 'offline'
  const degraded = snapshot?.systemMode === 'stale' || snapshot?.systemMode === 'recovery'

  return (
    <section className={`cockpit-screen endpoint-${endpoint} ${activeRisk ? `risk-${activeRisk.severity}` : ''}`}>
      <ScreenHeader endpoint={endpoint} snapshot={snapshot} connection={connection} />
      {(offline || degraded) && <ServiceNotice offline={offline} />}
      {endpoint === 'overview' ? (
        <Overview snapshot={snapshot} activeRisk={activeRisk} connection={connection} />
      ) : (
        <EndpointCanvas endpoint={endpoint} snapshot={snapshot} activeRisk={activeRisk} />
      )}
    </section>
  )
}

function ScreenHeader({ endpoint, snapshot, connection }: Pick<Props, 'endpoint' | 'snapshot' | 'connection'>) {
  const connected = connection === 'connected'
  return <header className="screen-header">
    <div><p className="eyebrow">GP21 · {snapshot?.activeFlow.replace('_', ' ') ?? 'authoritative snapshot'}</p><h1>{endpointNames[endpoint]}</h1></div>
    <span className={`connection-pill ${connected ? 'is-connected' : ''}`}>{connected ? <Radio size={15} /> : <WifiOff size={15} />}{connected ? `REV ${snapshot?.revision ?? '—'}` : '离线降级'}</span>
  </header>
}

function EndpointCanvas({ endpoint, snapshot, activeRisk }: Pick<Props, 'endpoint' | 'snapshot'> & { activeRisk?: RiskEventV1 }) {
  if (endpoint === 'cluster') return <Cluster snapshot={snapshot} activeRisk={activeRisk} />
  if (endpoint === 'hud') return <Hud snapshot={snapshot} activeRisk={activeRisk} />
  if (endpoint === 'passenger') return <Passenger snapshot={snapshot} activeRisk={activeRisk} />
  return <Center snapshot={snapshot} activeRisk={activeRisk} />
}

function Cluster({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  return <div className="cluster-layout">
    <DataTile icon={<Battery />} label="续航" value={`${snapshot?.vehicle.rangeKm ?? '—'} km`} />
    <div className="speed-readout"><span>{snapshot?.vehicle.speedKph ?? '—'}</span><small>km/h · {snapshot?.vehicle.gear ?? '—'}</small></div>
    <div className="cluster-route"><Navigation /><b>{snapshot?.navigation.currentStep?.instruction ?? '等待路线接力'}</b><span>{formatDistance(snapshot?.navigation.currentStep?.distanceMeters)}</span></div>
    {activeRisk && <RiskCard risk={activeRisk} compact />}
  </div>
}

function Hud({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  return <div className="hud-layout">
    {activeRisk ? <RiskCard risk={activeRisk} /> : <><Navigation size={42} /><div><p>下一步</p><b>{snapshot?.navigation.currentStep?.instruction ?? '保持当前车道'}</b></div><strong>{formatDistance(snapshot?.navigation.currentStep?.distanceMeters)}</strong></>}
  </div>
}

function Center({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  const { send, pending, error } = useCockpitCommand('center')
  const [destination, setDestination] = useState('城市艺术中心')
  const routeReady = snapshot?.navigation.status === 'preview'
  return <div className="center-layout"><div className="map-surface"><MapPin /><p>{snapshot?.navigation.destinationName ?? '未设置目的地'}</p><span>{snapshot?.navigation.provider === 'local_fallback' ? '本地路线 · 降级' : '路线已同步至主仪表与 HUD'}</span><div className="command-stack"><input value={destination} onChange={(event) => setDestination(event.target.value)} aria-label="目的地" /><button className="primary-button" disabled={pending || !destination.trim()} onClick={() => void send('select_destination', { destinationName: destination })}>规划路线</button>{routeReady && <button className="secondary-button" disabled={pending} onClick={() => void send('confirm_route', {})}>确认并接力</button>}</div></div><div className="center-side"><DataTile icon={<Gauge />} label="驾驶模式" value={snapshot?.vehicle.driveMode ?? '—'} /><VisionCard risk={activeRisk} />{activeRisk && <><RiskCard risk={activeRisk} /><div className="command-stack">{activeRisk.lifecycle === 'active' && <button className="primary-button" disabled={pending} onClick={() => void send('acknowledge_risk', { eventId: activeRisk.eventId })}>确认告警</button>}{activeRisk.lifecycle === 'acknowledged' && <button className="primary-button" disabled={pending} onClick={() => void send('resolve_risk', { eventId: activeRisk.eventId })}>完成处置并恢复</button>}</div></>}{error && <p className="command-error" role="alert">{error}</p>}</div></div>
}

function Passenger({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  const { send, pending, error } = useCockpitCommand('passenger')
  const [suggestion, setSuggestion] = useState('建议在城市艺术中心短暂停留')
  const suppressed = Boolean(activeRisk && activeRisk.severity === 'critical')
  const playing = snapshot?.passenger.mediaState === 'playing'
  return <div className="passenger-layout"><div className={`media-card ${suppressed ? 'is-suppressed' : ''}`}><PauseCircle size={36} /><p>{suppressed ? '媒体已因驾驶风险抑制' : '媒体与旅程协作'}</p><b>{suppressed ? '请协助驾驶员处置告警' : playing ? '当前播放 · 可由副驾控制' : '媒体已暂停'}</b><div className="command-stack"><button className="secondary-button" disabled={pending || suppressed} onClick={() => void send('set_media_state', { state: playing ? 'paused' : 'playing' })}>{playing ? '暂停媒体' : '播放媒体'}</button><input value={suggestion} onChange={(event) => setSuggestion(event.target.value)} aria-label="旅程建议" /><button className="secondary-button" disabled={pending || !suggestion.trim()} onClick={() => void send('submit_trip_suggestion', { suggestion })}>发送旅程建议</button></div></div><div className="privacy-card"><ShieldAlert /><div><p>隐私模式</p><b>{snapshot?.passenger.privacyEnabled ? '副驾内容不投射至驾驶端' : '副驾内容可共享至中控'}</b></div><button className="secondary-button" disabled={pending} onClick={() => void send('set_cabin_control', { privacyEnabled: !snapshot?.passenger.privacyEnabled })}>{snapshot?.passenger.privacyEnabled ? '关闭隐私' : '开启隐私'}</button></div><VisionCard risk={activeRisk} />{error && <p className="command-error" role="alert">{error}</p>}</div>
}

function Overview({ snapshot, activeRisk, connection }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1; connection: ConnectionState }) {
  return <section className="overview-screens"><div className="overview-primary-row"><ClusterOverviewScreen snapshot={snapshot} activeRisk={activeRisk} /><HudOverviewScreen snapshot={snapshot} activeRisk={activeRisk} /></div><div className="overview-secondary-row"><CenterOverviewScreen snapshot={snapshot} /><PassengerOverviewScreen snapshot={snapshot} activeRisk={activeRisk} /></div><p className="overview-footnote">{connection === 'connected' ? '四屏均消费同一 FastAPI snapshot。' : '等待权威 snapshot；不会用客户端推测值替代。'}</p></section>
}

function OverviewScreenFrame({ endpoint, size, children }: { endpoint: 'cluster' | 'hud' | 'center' | 'passenger'; size: string; children: React.ReactNode }) {
  return <article className={`overview-screen-frame overview-${endpoint}`} aria-label={`${endpointNames[endpoint]}屏幕预览`}><header><h2>{endpointNames[endpoint]}</h2><span>{size}</span></header>{children}</article>
}

function ClusterOverviewScreen({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  return <OverviewScreenFrame endpoint="cluster" size="1920×720"><div className="overview-cluster-canvas"><div className="cluster-corridor"><i /><i /><i /><span /></div>{activeRisk && <div className="overview-alert"><AlertTriangle size={14} />{activeRisk.message}</div>}<div className="cluster-overview-data"><div className="cluster-energy"><span>能量 · 车辆</span><b><Battery size={18} />{snapshot?.vehicle.rangeKm ?? '—'} km</b><small>电量 {snapshot?.vehicle.batteryPercent ?? '—'}%</small></div><div className="cluster-speed"><span>当前车速</span><strong>{snapshot?.vehicle.speedKph ?? '—'}<small>km/h</small></strong><div><b>{snapshot?.vehicle.gear ?? '—'} 挡</b><b>限速 80</b><b>L2 · ACC</b></div></div><div className="cluster-next"><span>下一步导航</span><strong>{formatDistance(snapshot?.navigation.currentStep?.distanceMeters)}</strong><b>{snapshot?.navigation.currentStep?.instruction ?? '等待路线接力'}</b><small>{snapshot?.navigation.destinationName ?? '尚未设置目的地'}</small></div></div></div></OverviewScreenFrame>
}

function HudOverviewScreen({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  return <OverviewScreenFrame endpoint="hud" size="1280×480"><div className="overview-hud-canvas"><div className="hud-status"><span>L2 · ACC</span><span>限速 80</span></div><div className="hud-axis"><strong>{snapshot?.vehicle.speedKph ?? '—'}<small>km/h</small></strong><div><Navigation /><b>{formatDistance(snapshot?.navigation.currentStep?.distanceMeters)}</b><span>{snapshot?.navigation.currentStep?.instruction ?? '保持当前车道'}</span></div><span>保持车道</span></div><div className={`hud-lanes ${activeRisk ? 'is-alert' : ''}`}>{activeRisk ? <><AlertTriangle size={14} />{activeRisk.message}</> : <><i /><i className="is-active" /><i /><span>推荐第 2 车道</span></>}</div></div></OverviewScreenFrame>
}

function CenterOverviewScreen({ snapshot }: { snapshot: CockpitSnapshotV1 | null }) {
  return <OverviewScreenFrame endpoint="center" size="1920×1080"><div className="overview-center-canvas"><div className="overview-map"><svg viewBox="0 0 700 420" preserveAspectRatio="none" aria-hidden="true"><path className="map-blocks" d="M20 20h150v110H20zM20 160h150v90H20zM20 280h150v120H20zM210 20h130v90H210zM210 145h130v110H210zM210 290h130v110H210zM385 20h120v105H385zM535 20h145v105H535zM385 265h295v135H385z" /><path className="map-road" d="M0 205h365M190 0v420M365 205C410 175 420 105 485 85S585 75 650 55" /><path className="map-route" d="M190 345V205H365C410 175 420 105 485 85S585 75 650 55" /></svg><div className="map-turn"><Navigation size={16} /><div><b>{snapshot?.navigation.currentStep?.instruction ?? '保持当前路线'}</b><span>{formatDistance(snapshot?.navigation.currentStep?.distanceMeters)}</span></div></div><div className="map-position"><MapPin size={14} />当前位置 → {snapshot?.navigation.destinationName ?? '未设置目的地'}</div></div><aside><span className="overview-kicker">路线已跨屏同步</span><div><small>目的地</small><h3>{snapshot?.navigation.destinationName ?? '未设置目的地'}</h3></div><div className="route-stats"><span><small>到达</small><b>18:58</b></span><span><small>剩余</small><b>{(snapshot?.navigation.remainingDistanceMeters ?? 0) / 1000} km</b></span><span><small>用时</small><b>{Math.round((snapshot?.navigation.etaSeconds ?? 0) / 60)} min</b></span></div><div className="route-option"><small>推荐路线</small><b>当前道路 · 畅通</b></div><div className="center-comfort"><span>驾驶模式 <b>{snapshot?.vehicle.driveMode ?? '—'}</b></span><span>副驾隐私 <b>{snapshot?.passenger.privacyEnabled ? '开启' : '关闭'}</b></span></div></aside></div></OverviewScreenFrame>
}

function PassengerOverviewScreen({ snapshot, activeRisk }: { snapshot: CockpitSnapshotV1 | null; activeRisk?: RiskEventV1 }) {
  const suppressed = activeRisk?.severity === 'critical'
  return <OverviewScreenFrame endpoint="passenger" size="1920×1080"><div className="overview-passenger-canvas"><div className="passenger-media"><div className={`media-visualizer ${suppressed ? 'is-suppressed' : ''}`}><span /><i /><i /><i />{suppressed && <b>风险接管中 · 媒体已降低音量</b>}</div><div><small>正在播放</small><h3>Silver Arrow</h3><span>Ambient Session</span></div><div className="media-progress"><i /><span>01:42</span><span>03:38</span></div><div className="media-state"><PauseCircle size={24} /><span>{suppressed ? '媒体已抑制' : snapshot?.passenger.mediaState === 'playing' ? '当前播放' : '媒体已暂停'}</span></div></div><aside><div><span className="overview-kicker">旅程协作</span><b>{snapshot?.passenger.tripSuggestions.at(-1) ?? '共同规划下一站'}</b></div><div><ShieldAlert size={20} /><span>隐私模式</span><b>{snapshot?.passenger.privacyEnabled ? '已开启' : '未开启'}</b></div><div><Radio size={20} /><span>座舱连接</span><b>四屏状态已同步</b></div></aside></div></OverviewScreenFrame>
}

function ServiceNotice({ offline }: { offline: boolean }) { return <div className="service-notice"><WifiOff size={16} />{offline ? '服务不可用：仅保留最后一次权威状态，不显示伪造实时数据。' : '同步恢复中：正在使用最新完整 snapshot 校验各屏状态。'}</div> }
function DataTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div className="data-tile">{icon}<span>{label}</span><b>{value}</b></div> }
function VisionCard({ risk }: { risk?: RiskEventV1 }) { return <div className="vision-card"><Eye /><div><p>VehicleVision</p><b>{risk ? `${risk.source} · ${(risk.confidence * 100).toFixed(0)}%` : '健康 · 无活动风险'}</b><small>{risk?.lifecycle ?? 'idle'}</small></div></div> }
function RiskCard({ risk, compact = false }: { risk: RiskEventV1; compact?: boolean }) { return <div className={`risk-card ${compact ? 'is-compact' : ''}`}><AlertTriangle /><div><p>{risk.lifecycle === 'acknowledged' ? '已确认，等待处置' : '关键驾驶告警'}</p><b>{risk.message}</b><small>{risk.source} · {Math.round(risk.confidence * 100)}% · {risk.lifecycle}</small></div><ChevronRight /></div> }
function formatDistance(meters?: number) { return meters ? meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m` : '—' }
