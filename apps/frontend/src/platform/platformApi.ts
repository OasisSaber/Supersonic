export type PlatformRole = 'admin' | 'operator' | 'viewer'

export interface PlatformIdentity {
  userId: string
  displayName: string
  role: PlatformRole
  platformSessionId: string
  expiresAt: string
}

export interface PlatformUser {
  id: string
  username: string
  displayName: string
  role: PlatformRole
  disabledAt: string | null
  createdAt: string
  updatedAt: string
}

export interface PlatformSession {
  id: string
  userId: string
  createdAt: string
  expiresAt: string
  lastSeenAt: string | null
  revokedAt: string | null
  revokeReason: string | null
}

export interface AdminMutationResponse {
  changed: boolean
  revokedSessionIds: string[]
  revokePropagation: 'complete' | 'degraded'
  failedRevokePropagationSessionIds: string[]
}

export interface AuditEventView {
  id: string
  occurredAt: string
  action: string
  result: 'attempted' | 'succeeded' | 'rejected' | 'error' | 'degraded'
  delivery: 'primary' | 'fallback' | 'lost'
  actorUserId: string | null
  actorPlatformSessionId: string | null
  actorRole: PlatformRole | null
  endpoint: string | null
  cockpitSessionId: string | null
  commandName: string | null
  correlationId: string | null
  targetType: string | null
  targetId: string | null
  parameters: Record<string, JsonValue>
  errorCode: string | null
  sourceType: string
}

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }
type Validator<T> = (value: unknown) => T | null
type RecordValue = Record<string, unknown>

export class PlatformApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'PlatformApiError'
  }
}

const apiBase = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
const roles: readonly PlatformRole[] = ['admin', 'operator', 'viewer']
const auditResults: readonly AuditEventView['result'][] = [
  'attempted',
  'succeeded',
  'rejected',
  'error',
  'degraded',
]
const auditDeliveries: readonly AuditEventView['delivery'][] = ['primary', 'fallback', 'lost']

async function request<T>(path: string, validate: Validator<T>, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = validateError(payload)
    throw new PlatformApiError(
      response.status,
      error?.code ?? 'request_failed',
      error?.message ?? 'Platform request failed.',
    )
  }
  const value = validate(payload)
  if (value === null) {
    throw new PlatformApiError(502, 'invalid_response', 'Platform returned an invalid response.')
  }
  return value
}

function recordWithKeys(value: unknown, keys: readonly string[]): RecordValue | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const record = value as RecordValue
  const actual = Object.keys(record).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length && actual.every((key, index) => key === expected[index])
    ? record
    : null
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function nullableString(value: unknown): string | null | undefined {
  return value === null || typeof value === 'string' ? value : undefined
}

function dateString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 && Number.isFinite(Date.parse(value))
    ? value
    : null
}

function nullableDate(value: unknown): string | null | undefined {
  return value === null ? null : dateString(value) ?? undefined
}

function roleValue(value: unknown): PlatformRole | null {
  return typeof value === 'string' && roles.includes(value as PlatformRole)
    ? (value as PlatformRole)
    : null
}

function nullableRole(value: unknown): PlatformRole | null | undefined {
  return value === null ? null : roleValue(value) ?? undefined
}

function stringArray(value: unknown): string[] | null {
  return Array.isArray(value) && value.every((item) => typeof item === 'string') ? value : null
}

function jsonRecord(value: unknown): Record<string, JsonValue> | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  return Object.values(value).every(isJsonValue) ? (value as Record<string, JsonValue>) : null
}

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || ['boolean', 'string'].includes(typeof value)) return true
  if (typeof value === 'number') return Number.isFinite(value)
  if (Array.isArray(value)) return value.every(isJsonValue)
  if (typeof value === 'object') return Object.values(value).every(isJsonValue)
  return false
}

function validateError(value: unknown): { code: string; message: string } | null {
  const envelope = recordWithKeys(value, ['error'])
  const error = envelope ? recordWithKeys(envelope.error, ['code', 'message']) : null
  if (!error || typeof error.code !== 'string' || typeof error.message !== 'string') return null
  return { code: error.code, message: error.message }
}

const validateIdentity: Validator<PlatformIdentity> = (value) => {
  const record = recordWithKeys(value, [
    'userId',
    'displayName',
    'role',
    'platformSessionId',
    'expiresAt',
  ])
  if (!record) return null
  const userId = stringValue(record.userId)
  const displayName = stringValue(record.displayName)
  const role = roleValue(record.role)
  const platformSessionId = stringValue(record.platformSessionId)
  const expiresAt = dateString(record.expiresAt)
  return userId && displayName && role && platformSessionId && expiresAt
    ? { userId, displayName, role, platformSessionId, expiresAt }
    : null
}

const validateUser: Validator<PlatformUser> = (value) => {
  const record = recordWithKeys(value, [
    'id',
    'username',
    'displayName',
    'role',
    'disabledAt',
    'createdAt',
    'updatedAt',
  ])
  if (!record) return null
  const id = stringValue(record.id)
  const username = stringValue(record.username)
  const displayName = stringValue(record.displayName)
  const role = roleValue(record.role)
  const disabledAt = nullableDate(record.disabledAt)
  const createdAt = dateString(record.createdAt)
  const updatedAt = dateString(record.updatedAt)
  return id && username && displayName && role && disabledAt !== undefined && createdAt && updatedAt
    ? { id, username, displayName, role, disabledAt, createdAt, updatedAt }
    : null
}

const validateSession: Validator<PlatformSession> = (value) => {
  const record = recordWithKeys(value, [
    'id',
    'userId',
    'createdAt',
    'expiresAt',
    'lastSeenAt',
    'revokedAt',
    'revokeReason',
  ])
  if (!record) return null
  const id = stringValue(record.id)
  const userId = stringValue(record.userId)
  const createdAt = dateString(record.createdAt)
  const expiresAt = dateString(record.expiresAt)
  const lastSeenAt = nullableDate(record.lastSeenAt)
  const revokedAt = nullableDate(record.revokedAt)
  const revokeReason = nullableString(record.revokeReason)
  return id && userId && createdAt && expiresAt && lastSeenAt !== undefined && revokedAt !== undefined
    && revokeReason !== undefined
    ? { id, userId, createdAt, expiresAt, lastSeenAt, revokedAt, revokeReason }
    : null
}

const validateMutation: Validator<AdminMutationResponse> = (value) => {
  const record = recordWithKeys(value, [
    'changed',
    'revokedSessionIds',
    'revokePropagation',
    'failedRevokePropagationSessionIds',
  ])
  if (!record || typeof record.changed !== 'boolean') return null
  const revokedSessionIds = stringArray(record.revokedSessionIds)
  const failedRevokePropagationSessionIds = stringArray(record.failedRevokePropagationSessionIds)
  const revokePropagation = record.revokePropagation
  if (
    !revokedSessionIds
    || !failedRevokePropagationSessionIds
    || (revokePropagation !== 'complete' && revokePropagation !== 'degraded')
  ) return null
  if (
    (revokePropagation === 'complete' && failedRevokePropagationSessionIds.length > 0)
    || failedRevokePropagationSessionIds.some((id) => !revokedSessionIds.includes(id))
  ) return null
  return { changed: record.changed, revokedSessionIds, revokePropagation, failedRevokePropagationSessionIds }
}

const validateAuditEvent: Validator<AuditEventView> = (value) => {
  const record = recordWithKeys(value, [
    'id', 'occurredAt', 'action', 'result', 'delivery', 'actorUserId',
    'actorPlatformSessionId', 'actorRole', 'endpoint', 'cockpitSessionId',
    'commandName', 'correlationId', 'targetType', 'targetId', 'parameters',
    'errorCode', 'sourceType',
  ])
  if (!record) return null
  const id = stringValue(record.id)
  const occurredAt = dateString(record.occurredAt)
  const action = stringValue(record.action)
  const actorUserId = nullableString(record.actorUserId)
  const actorPlatformSessionId = nullableString(record.actorPlatformSessionId)
  const actorRole = nullableRole(record.actorRole)
  const endpoint = nullableString(record.endpoint)
  const cockpitSessionId = nullableString(record.cockpitSessionId)
  const commandName = nullableString(record.commandName)
  const correlationId = nullableString(record.correlationId)
  const targetType = nullableString(record.targetType)
  const targetId = nullableString(record.targetId)
  const parameters = jsonRecord(record.parameters)
  const errorCode = nullableString(record.errorCode)
  const sourceType = stringValue(record.sourceType)
  if (
    !id || !occurredAt || !action || !auditResults.includes(record.result as AuditEventView['result'])
    || !auditDeliveries.includes(record.delivery as AuditEventView['delivery'])
    || actorUserId === undefined || actorPlatformSessionId === undefined || actorRole === undefined
    || endpoint === undefined || cockpitSessionId === undefined || commandName === undefined
    || correlationId === undefined || targetType === undefined || targetId === undefined
    || !parameters || errorCode === undefined || !sourceType
  ) return null
  return {
    id,
    occurredAt,
    action,
    result: record.result as AuditEventView['result'],
    delivery: record.delivery as AuditEventView['delivery'],
    actorUserId,
    actorPlatformSessionId,
    actorRole,
    endpoint,
    cockpitSessionId,
    commandName,
    correlationId,
    targetType,
    targetId,
    parameters,
    errorCode,
    sourceType,
  }
}

function arrayEnvelope<T>(key: string, validate: Validator<T>): Validator<Record<string, T[]>> {
  return (value) => {
    const record = recordWithKeys(value, [key])
    const raw = record?.[key]
    if (!Array.isArray(raw)) return null
    const values: T[] = []
    for (const item of raw) {
      const parsed = validate(item)
      if (parsed === null) return null
      values.push(parsed)
    }
    return { [key]: values }
  }
}

const validateUsers = arrayEnvelope('users', validateUser) as Validator<{ users: PlatformUser[] }>
const validateSessions = arrayEnvelope('sessions', validateSession) as Validator<{ sessions: PlatformSession[] }>

const validateAuditPage: Validator<{ events: AuditEventView[]; nextCursor: string | null }> = (value) => {
  const record = recordWithKeys(value, ['events', 'nextCursor'])
  if (!record || !Array.isArray(record.events)) return null
  const events: AuditEventView[] = []
  for (const item of record.events) {
    const event = validateAuditEvent(item)
    if (!event) return null
    events.push(event)
  }
  const nextCursor = nullableString(record.nextCursor)
  return nextCursor === undefined ? null : { events, nextCursor }
}

const validateLogout: Validator<{ loggedOut: boolean }> = (value) => {
  const record = recordWithKeys(value, ['loggedOut'])
  return record && record.loggedOut === true ? { loggedOut: true } : null
}

export const platformApi = {
  me: () => request('/api/platform/session/me', validateIdentity),
  login: (username: string, password: string) => request(
    '/api/platform/session/login',
    validateIdentity,
    { method: 'POST', body: JSON.stringify({ username, password }) },
  ),
  logout: () => request('/api/platform/session/logout', validateLogout, { method: 'POST' }),
  users: () => request('/api/platform/admin/users', validateUsers),
  sessions: (userId: string) => request(
    `/api/platform/admin/users/${encodeURIComponent(userId)}/sessions`,
    validateSessions,
  ),
  changeRole: (userId: string, role: PlatformRole) => request(
    `/api/platform/admin/users/${encodeURIComponent(userId)}/role`,
    validateMutation,
    { method: 'POST', body: JSON.stringify({ role }) },
  ),
  setDisabled: (userId: string, disabled: boolean) => request(
    `/api/platform/admin/users/${encodeURIComponent(userId)}/disabled`,
    validateMutation,
    { method: 'POST', body: JSON.stringify({ disabled }) },
  ),
  revokeSession: (sessionId: string) => request(
    `/api/platform/admin/sessions/${encodeURIComponent(sessionId)}/revoke`,
    validateMutation,
    { method: 'POST', body: JSON.stringify({ reason: 'admin_revoke' }) },
  ),
  audit: (cursor?: string) => {
    const query = new URLSearchParams({ limit: '50' })
    if (cursor) query.set('cursor', cursor)
    return request(`/api/platform/audit?${query.toString()}`, validateAuditPage)
  },
}
