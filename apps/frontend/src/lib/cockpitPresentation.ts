import type {
  CockpitSnapshotV1,
  DataFreshness,
  EndpointId,
  FlowId,
  RiskSource,
  SystemMode,
} from '../contracts/gp05-v1'

export const ENDPOINT_LABELS: Record<EndpointId, string> = {
  cluster: '主仪表',
  hud: 'HUD',
  center: '中控',
  passenger: '副驾',
  overview: '多屏总览',
  control: '演示控制台',
}

export const FLOW_LABELS: Record<FlowId, string> = {
  navigation_handoff: '导航接力',
  risk_takeover: '风险接管',
  passenger_collaboration: '副驾协作',
}

export const SYSTEM_MODE_LABELS: Record<SystemMode, string> = {
  normal: '正常',
  warning: '关注',
  takeover: '接管',
  stale: '数据滞后',
  offline: '离线',
  recovery: '恢复中',
}

export const FRESHNESS_LABELS: Record<DataFreshness, string> = {
  fresh: '实时',
  stale: '降级',
  offline: '离线',
}

export type SemanticTone = 'neutral' | 'accent' | 'success' | 'warning' | 'critical'

export function freshnessTone(status: DataFreshness): SemanticTone {
  if (status === 'fresh') return 'success'
  if (status === 'stale') return 'warning'
  return 'neutral'
}

export function systemModeTone(mode?: SystemMode): SemanticTone {
  if (mode === 'takeover') return 'critical'
  if (mode === 'warning' || mode === 'stale' || mode === 'recovery') return 'warning'
  if (mode === 'normal') return 'success'
  return 'neutral'
}

export function riskSourceLabel(source: RiskSource): string {
  const labels: Record<RiskSource, string> = {
    live_camera: '实时摄像头',
    video_inference: '视频推理',
    simulated_event: '模拟事件',
  }
  return labels[source]
}

export function formatDistance(meters?: number | null): string {
  if (meters === undefined || meters === null || meters <= 0) return '—'
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)} km`
  return `${Math.round(meters)} m`
}

export function formatEta(seconds?: number | null): string {
  if (seconds === undefined || seconds === null || seconds <= 0) return '—'
  const minutes = Math.max(1, Math.round(seconds / 60))
  return `${minutes} min`
}

export function formatTimestamp(value?: string): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function snapshotSummary(snapshot: CockpitSnapshotV1 | null): string {
  if (!snapshot) return '等待权威状态'
  return `${FLOW_LABELS[snapshot.activeFlow]} · ${SYSTEM_MODE_LABELS[snapshot.systemMode]}`
}

export function onlineEndpointCount(snapshot: CockpitSnapshotV1 | null): number {
  if (!snapshot) return 0
  return Object.values(snapshot.endpointConnectivity).filter(
    (connection) => connection.status === 'fresh',
  ).length
}

export function navigationSourceLabel(snapshot: CockpitSnapshotV1 | null): string {
  if (!snapshot) return '等待路线数据'
  if (snapshot.navigation.provider === 'amap') return '高德地图 · 实时服务'
  if (snapshot.navigation.provider === 'local_fallback') return '本地确定性路线 · 降级'
  return '未启用路线服务'
}

export function screenStateClass(snapshot: CockpitSnapshotV1 | null): string {
  if (!snapshot) return 'is-loading'
  if (snapshot.systemMode === 'takeover') return 'is-takeover'
  if (snapshot.systemMode === 'offline') return 'is-offline'
  if (snapshot.systemMode === 'stale' || snapshot.systemMode === 'recovery') {
    return 'is-degraded'
  }
  return 'is-normal'
}
