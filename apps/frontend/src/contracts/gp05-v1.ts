export const CONTRACT_VERSION = 'gp05.v1' as const

export const ENDPOINTS = [
  'cluster',
  'hud',
  'center',
  'passenger',
  'overview',
  'control',
] as const
export type EndpointId = (typeof ENDPOINTS)[number]

export const THEMES = ['day', 'night'] as const
export type ThemeMode = (typeof THEMES)[number]

export const COMPONENT_STATES = [
  'normal',
  'active',
  'disabled',
  'warning',
  'critical',
  'loading',
  'empty',
  'stale',
  'offline',
] as const
export type ComponentState = (typeof COMPONENT_STATES)[number]

export const SYSTEM_MODES = [
  'normal',
  'warning',
  'takeover',
  'stale',
  'offline',
  'recovery',
] as const
export type SystemMode = (typeof SYSTEM_MODES)[number]

export const FLOWS = [
  'navigation_handoff',
  'risk_takeover',
  'passenger_collaboration',
] as const
export type FlowId = (typeof FLOWS)[number]

export const DATA_FRESHNESS = ['fresh', 'stale', 'offline'] as const
export type DataFreshness = (typeof DATA_FRESHNESS)[number]

export const RISK_LIFECYCLES = [
  'candidate',
  'active',
  'acknowledged',
  'resolved',
] as const
export type RiskLifecycle = (typeof RISK_LIFECYCLES)[number]

export const RISK_SEVERITIES = ['info', 'warning', 'critical'] as const
export type RiskSeverity = (typeof RISK_SEVERITIES)[number]

export const RISK_SOURCES = [
  'live_camera',
  'video_inference',
  'simulated_event',
] as const
export type RiskSource = (typeof RISK_SOURCES)[number]

export const RISK_TYPES = [
  'driver_fatigue',
  'driver_distraction',
  'parking_guard_motion',
  'occupant_phone_use',
  'occupant_out_of_zone',
] as const
export type RiskType = (typeof RISK_TYPES)[number]

export const COMMAND_NAMES = [
  'set_theme',
  'set_system_mode',
  'select_destination',
  'confirm_route',
  'acknowledge_risk',
  'resolve_risk',
  'set_media_state',
  'submit_trip_suggestion',
  'set_cabin_control',
  'reset_session',
] as const
export type CommandName = (typeof COMMAND_NAMES)[number]

export const ENDPOINT_COMMAND_PERMISSIONS = {
  cluster: ['acknowledge_risk'],
  hud: [],
  center: [
    'select_destination',
    'confirm_route',
    'acknowledge_risk',
    'resolve_risk',
    'set_media_state',
    'set_cabin_control',
  ],
  passenger: ['set_media_state', 'submit_trip_suggestion', 'set_cabin_control'],
  overview: [],
  control: [...COMMAND_NAMES],
} as const satisfies Record<EndpointId, readonly CommandName[]>

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue }

export interface DataHealth {
  status: DataFreshness
  updatedAt: string
}

export interface VehicleStateV1 {
  speedKph: number
  gear: string
  batteryPercent: number
  rangeKm: number
  driveMode: string
  seatbeltFastened: boolean
}

export interface Coordinate {
  longitude: number
  latitude: number
}

export interface NavigationStep {
  index: number
  instruction: string
  roadName: string
  distanceMeters: number
  maneuver: string
}

export type RouteProvider = 'amap' | 'local_fallback' | 'none'
export type MapServiceStatus = 'live' | 'degraded' | 'unavailable'
export type RouteStatus = 'idle' | 'planning' | 'preview' | 'active' | 'arrived' | 'unavailable'

export interface NavigationStateV1 {
  provider: RouteProvider
  serviceStatus: MapServiceStatus
  status: RouteStatus
  destinationName: string | null
  remainingDistanceMeters: number
  etaSeconds: number
  currentStep: NavigationStep | null
  steps: NavigationStep[]
  polyline: Coordinate[]
  updatedAt: string
}

export interface RiskEventV1 {
  eventId: string
  sessionId: string
  riskType: RiskType
  lifecycle: RiskLifecycle
  severity: RiskSeverity
  source: RiskSource
  confidence: number
  occurredAt: string
  updatedAt: string
  message: string
  evidence: string[]
  metadata: Record<string, JsonValue>
}

export interface EndpointConnection {
  status: DataFreshness
  lastSeenAt: string
}

export interface PassengerStateV1 {
  mediaState: 'playing' | 'paused' | 'suppressed'
  privacyEnabled: boolean
  tripSuggestions: string[]
}

export interface CockpitSnapshotV1 {
  sessionId: string
  revision: number
  timestamp: string
  theme: ThemeMode
  systemMode: SystemMode
  activeFlow: FlowId
  dataHealth: Record<string, DataHealth>
  vehicle: VehicleStateV1
  navigation: NavigationStateV1
  risks: RiskEventV1[]
  passenger: PassengerStateV1
  endpointConnectivity: Partial<Record<EndpointId, EndpointConnection>>
  capabilities: string[]
}

export interface MessageSource {
  kind: 'endpoint' | 'service'
  id: string
}

interface EnvelopeBase {
  protocolVersion: typeof CONTRACT_VERSION
  messageId: string
  correlationId: string
  timestamp: string
  source: MessageSource
  target: EndpointId | null
}

export interface CommandEnvelopeV1 extends EnvelopeBase {
  kind: 'command'
  payload: {
    name: CommandName
    endpoint: EndpointId
    parameters: Record<string, JsonValue>
  }
}

export interface EventEnvelopeV1 extends EnvelopeBase {
  kind: 'event'
  payload: {
    domain: 'system' | 'navigation' | 'risk' | 'passenger' | 'vision' | 'persistence' | 'map'
    name: string
    data: Record<string, JsonValue>
  }
}

export interface SnapshotEnvelopeV1 extends EnvelopeBase {
  kind: 'snapshot'
  payload: CockpitSnapshotV1
}

export type MessageEnvelopeV1 = CommandEnvelopeV1 | EventEnvelopeV1 | SnapshotEnvelopeV1

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const includes = <T extends string>(values: readonly T[], value: unknown): value is T =>
  typeof value === 'string' && values.includes(value as T)

export function isCockpitSnapshotV1(value: unknown): value is CockpitSnapshotV1 {
  if (!isRecord(value) || !isRecord(value.vehicle) || !isRecord(value.navigation)) return false
  if (!isRecord(value.dataHealth) || !isRecord(value.endpointConnectivity) || !isRecord(value.passenger)) return false
  if (!Array.isArray(value.risks) || !Array.isArray(value.capabilities)) return false

  return (
    typeof value.sessionId === 'string' &&
    Number.isInteger(value.revision) &&
    typeof value.timestamp === 'string' &&
    includes(THEMES, value.theme) &&
    includes(SYSTEM_MODES, value.systemMode) &&
    includes(FLOWS, value.activeFlow) &&
    typeof value.vehicle.speedKph === 'number' &&
    (value.passenger.mediaState === 'playing' || value.passenger.mediaState === 'paused' || value.passenger.mediaState === 'suppressed') &&
    typeof value.passenger.privacyEnabled === 'boolean' &&
    Array.isArray(value.passenger.tripSuggestions) &&
    typeof value.vehicle.batteryPercent === 'number' &&
    typeof value.navigation.provider === 'string' &&
    typeof value.navigation.serviceStatus === 'string' &&
    value.risks.every(
      (risk) =>
        isRecord(risk) &&
        includes(RISK_TYPES, risk.riskType) &&
        includes(RISK_LIFECYCLES, risk.lifecycle) &&
        includes(RISK_SEVERITIES, risk.severity) &&
        includes(RISK_SOURCES, risk.source) &&
        typeof risk.confidence === 'number' &&
        risk.confidence >= 0 &&
        risk.confidence <= 1,
    )
  )
}

export function isMessageEnvelopeV1(value: unknown): value is MessageEnvelopeV1 {
  if (!isRecord(value) || !isRecord(value.source) || !isRecord(value.payload)) return false

  const hasMetadata =
    value.protocolVersion === CONTRACT_VERSION &&
    typeof value.messageId === 'string' &&
    typeof value.correlationId === 'string' &&
    typeof value.timestamp === 'string' &&
    typeof value.source.id === 'string' &&
    (value.source.kind === 'endpoint' || value.source.kind === 'service')

  if (!hasMetadata) return false
  if (value.kind === 'snapshot') return isCockpitSnapshotV1(value.payload)
  if (value.kind === 'command') return includes(COMMAND_NAMES, value.payload.name)
  return value.kind === 'event' && typeof value.payload.name === 'string'
}
