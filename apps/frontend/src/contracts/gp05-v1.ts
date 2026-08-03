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

export const EVENT_DOMAINS = [
  'system',
  'navigation',
  'risk',
  'passenger',
  'vision',
  'persistence',
  'map',
] as const
export type EventDomain = (typeof EVENT_DOMAINS)[number]

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

const ROUTE_PROVIDERS = ['amap', 'local_fallback', 'none'] as const
const MAP_SERVICE_STATUSES = ['live', 'degraded', 'unavailable'] as const
const ROUTE_STATUSES = ['idle', 'planning', 'preview', 'active', 'arrived', 'unavailable'] as const
const REQUIRED_DATA_HEALTH_DOMAINS = ['vehicle', 'navigation', 'vision'] as const

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
  endpointConnectivity: Record<EndpointId, EndpointConnection>
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
    domain: EventDomain
    name: string
    data: Record<string, JsonValue>
  }
}

export interface SnapshotEnvelopeV1 extends EnvelopeBase {
  kind: 'snapshot'
  payload: CockpitSnapshotV1
}

export type MessageEnvelopeV1 = CommandEnvelopeV1 | EventEnvelopeV1 | SnapshotEnvelopeV1

const SNAPSHOT_KEYS = [
  'sessionId',
  'revision',
  'timestamp',
  'theme',
  'systemMode',
  'activeFlow',
  'dataHealth',
  'vehicle',
  'navigation',
  'risks',
  'passenger',
  'endpointConnectivity',
  'capabilities',
] as const
const ENVELOPE_KEYS = [
  'protocolVersion',
  'messageId',
  'correlationId',
  'timestamp',
  'source',
  'target',
  'kind',
  'payload',
] as const

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const includes = <T extends string>(values: readonly T[], value: unknown): value is T =>
  typeof value === 'string' && values.includes(value as T)

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value)
  return actual.length === keys.length && keys.every((key) => key in value)
}

function isBoundedString(value: unknown, minimum: number, maximum: number): value is string {
  return typeof value === 'string' && value.length >= minimum && value.length <= maximum
}

const isTimestamp = (value: unknown): value is string =>
  isBoundedString(value, 1, 128) && Number.isFinite(Date.parse(value))

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const isUuid = (value: unknown): value is string =>
  typeof value === 'string' && UUID_PATTERN.test(value)

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

const isNumberInRange = (value: unknown, minimum: number, maximum = Infinity) =>
  isFiniteNumber(value) && value >= minimum && value <= maximum

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return true
  if (isFiniteNumber(value)) return true
  if (Array.isArray(value)) return value.every(isJsonValue)
  return isRecord(value) && Object.values(value).every(isJsonValue)
}

function isJsonRecord(value: unknown): value is Record<string, JsonValue> {
  return isRecord(value) && Object.values(value).every(isJsonValue)
}

function isStringArray(
  value: unknown,
  maximumItems = Infinity,
  maximumLength = Infinity,
  minimumLength = 0,
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= maximumItems &&
    value.every((item) => isBoundedString(item, minimumLength, maximumLength))
  )
}

function isDataHealth(value: unknown): value is DataHealth {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['status', 'updatedAt']) &&
    includes(DATA_FRESHNESS, value.status) &&
    isTimestamp(value.updatedAt)
  )
}

function isVehicleStateV1(value: unknown): value is VehicleStateV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      'speedKph',
      'gear',
      'batteryPercent',
      'rangeKm',
      'driveMode',
      'seatbeltFastened',
    ]) &&
    isNumberInRange(value.speedKph, 0, 320) &&
    isBoundedString(value.gear, 1, 8) &&
    isNumberInRange(value.batteryPercent, 0, 100) &&
    isNumberInRange(value.rangeKm, 0) &&
    isBoundedString(value.driveMode, 1, 40) &&
    typeof value.seatbeltFastened === 'boolean'
  )
}

function isCoordinate(value: unknown): value is Coordinate {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['longitude', 'latitude']) &&
    isNumberInRange(value.longitude, -180, 180) &&
    isNumberInRange(value.latitude, -90, 90)
  )
}

function isNavigationStep(value: unknown): value is NavigationStep {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      'index',
      'instruction',
      'roadName',
      'distanceMeters',
      'maneuver',
    ]) &&
    Number.isInteger(value.index) &&
    isNumberInRange(value.index, 0) &&
    isBoundedString(value.instruction, 1, 200) &&
    isBoundedString(value.roadName, 0, 120) &&
    isNumberInRange(value.distanceMeters, 0) &&
    isBoundedString(value.maneuver, 1, 60)
  )
}

function isNavigationStateV1(value: unknown): value is NavigationStateV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      'provider',
      'serviceStatus',
      'status',
      'destinationName',
      'remainingDistanceMeters',
      'etaSeconds',
      'currentStep',
      'steps',
      'polyline',
      'updatedAt',
    ]) &&
    includes(ROUTE_PROVIDERS, value.provider) &&
    includes(MAP_SERVICE_STATUSES, value.serviceStatus) &&
    includes(ROUTE_STATUSES, value.status) &&
    (value.destinationName === null || isBoundedString(value.destinationName, 0, 160)) &&
    isNumberInRange(value.remainingDistanceMeters, 0) &&
    Number.isInteger(value.etaSeconds) &&
    isNumberInRange(value.etaSeconds, 0) &&
    (value.currentStep === null || isNavigationStep(value.currentStep)) &&
    Array.isArray(value.steps) &&
    value.steps.every(isNavigationStep) &&
    Array.isArray(value.polyline) &&
    value.polyline.every(isCoordinate) &&
    isTimestamp(value.updatedAt)
  )
}

function isRiskEventV1(value: unknown): value is RiskEventV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, [
      'eventId',
      'sessionId',
      'riskType',
      'lifecycle',
      'severity',
      'source',
      'confidence',
      'occurredAt',
      'updatedAt',
      'message',
      'evidence',
      'metadata',
    ]) &&
    isBoundedString(value.eventId, 1, 80) &&
    isBoundedString(value.sessionId, 1, 80) &&
    includes(RISK_TYPES, value.riskType) &&
    includes(RISK_LIFECYCLES, value.lifecycle) &&
    includes(RISK_SEVERITIES, value.severity) &&
    includes(RISK_SOURCES, value.source) &&
    isNumberInRange(value.confidence, 0, 1) &&
    isTimestamp(value.occurredAt) &&
    isTimestamp(value.updatedAt) &&
    isBoundedString(value.message, 1, 240) &&
    isStringArray(value.evidence, 32) &&
    isJsonRecord(value.metadata)
  )
}

function isEndpointConnection(value: unknown): value is EndpointConnection {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['status', 'lastSeenAt']) &&
    includes(DATA_FRESHNESS, value.status) &&
    isTimestamp(value.lastSeenAt)
  )
}

function isPassengerStateV1(value: unknown): value is PassengerStateV1 {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['mediaState', 'privacyEnabled', 'tripSuggestions']) &&
    includes(['playing', 'paused', 'suppressed'] as const, value.mediaState) &&
    typeof value.privacyEnabled === 'boolean' &&
    isStringArray(value.tripSuggestions, 8, 200, 1)
  )
}

function isCompleteDataHealth(value: unknown): value is Record<string, DataHealth> {
  return (
    isRecord(value) &&
    REQUIRED_DATA_HEALTH_DOMAINS.every((domain) => domain in value) &&
    Object.values(value).every(isDataHealth)
  )
}

function isCompleteEndpointConnectivity(
  value: unknown,
): value is Record<EndpointId, EndpointConnection> {
  return (
    isRecord(value) &&
    hasExactKeys(value, ENDPOINTS) &&
    ENDPOINTS.every((endpoint) => isEndpointConnection(value[endpoint]))
  )
}

export function isCockpitSnapshotV1(value: unknown): value is CockpitSnapshotV1 {
  if (!isRecord(value) || !hasExactKeys(value, SNAPSHOT_KEYS)) return false
  if (!Array.isArray(value.risks) || !Array.isArray(value.capabilities)) return false

  return (
    isBoundedString(value.sessionId, 1, 80) &&
    Number.isInteger(value.revision) &&
    isNumberInRange(value.revision, 0) &&
    isTimestamp(value.timestamp) &&
    includes(THEMES, value.theme) &&
    includes(SYSTEM_MODES, value.systemMode) &&
    includes(FLOWS, value.activeFlow) &&
    isCompleteDataHealth(value.dataHealth) &&
    isVehicleStateV1(value.vehicle) &&
    isNavigationStateV1(value.navigation) &&
    value.risks.every(isRiskEventV1) &&
    isPassengerStateV1(value.passenger) &&
    isCompleteEndpointConnectivity(value.endpointConnectivity) &&
    isStringArray(value.capabilities)
  )
}

function isMessageSource(value: unknown): value is MessageSource {
  return (
    isRecord(value) &&
    hasExactKeys(value, ['kind', 'id']) &&
    includes(['endpoint', 'service'] as const, value.kind) &&
    isBoundedString(value.id, 1, 80)
  )
}

export function isMessageEnvelopeV1(value: unknown): value is MessageEnvelopeV1 {
  if (!isRecord(value) || !hasExactKeys(value, ENVELOPE_KEYS)) return false
  if (!isRecord(value.payload)) return false

  const payload = value.payload
  const hasMetadata =
    value.protocolVersion === CONTRACT_VERSION &&
    isUuid(value.messageId) &&
    isUuid(value.correlationId) &&
    isTimestamp(value.timestamp) &&
    isMessageSource(value.source) &&
    (value.target === null || includes(ENDPOINTS, value.target))

  if (!hasMetadata) return false
  if (value.kind === 'snapshot') return isCockpitSnapshotV1(payload)
  if (value.kind === 'command') {
    return (
      hasExactKeys(payload, ['name', 'endpoint', 'parameters']) &&
      includes(COMMAND_NAMES, payload.name) &&
      includes(ENDPOINTS, payload.endpoint) &&
      isJsonRecord(payload.parameters)
    )
  }
  return (
    value.kind === 'event' &&
    hasExactKeys(payload, ['domain', 'name', 'data']) &&
    includes(EVENT_DOMAINS, payload.domain) &&
    isBoundedString(payload.name, 1, 100) &&
    isJsonRecord(payload.data)
  )
}
