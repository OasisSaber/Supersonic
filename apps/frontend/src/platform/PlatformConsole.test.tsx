import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PlatformConsole } from './PlatformConsole'
import { PlatformApiError, platformApi, type AuditEventView, type PlatformIdentity } from './platformApi'

vi.mock('./platformApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./platformApi')>()
  return {
    ...actual,
    platformApi: {
      me: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      users: vi.fn(),
      sessions: vi.fn(),
      changeRole: vi.fn(),
      setDisabled: vi.fn(),
      revokeSession: vi.fn(),
      audit: vi.fn(),
    },
  }
})

const mockedApi = vi.mocked(platformApi)

const adminIdentity: PlatformIdentity = {
  userId: 'user-current',
  displayName: 'Current Admin',
  role: 'admin',
  platformSessionId: 'session-current',
  expiresAt: '2026-08-22T12:00:00Z',
}

const alice = {
  id: 'user-alice',
  username: 'alice',
  displayName: 'Alice Operator',
  role: 'operator' as const,
  disabledAt: null,
  createdAt: '2026-08-20T12:00:00Z',
  updatedAt: '2026-08-21T12:00:00Z',
}

const currentUser = {
  id: 'user-current',
  username: 'admin',
  displayName: 'Current Admin',
  role: 'admin' as const,
  disabledAt: null,
  createdAt: '2026-08-19T12:00:00Z',
  updatedAt: '2026-08-21T12:00:00Z',
}

const bob = {
  id: 'user-bob',
  username: 'bob',
  displayName: 'Bob Viewer',
  role: 'viewer' as const,
  disabledAt: null,
  createdAt: '2026-08-20T13:00:00Z',
  updatedAt: '2026-08-21T13:00:00Z',
}

function auditEvent(id: string, action: string): AuditEventView {
  return {
    id,
    occurredAt: '2026-08-21T12:00:00Z',
    action,
    result: 'succeeded',
    delivery: 'primary',
    actorUserId: 'user-current',
    actorPlatformSessionId: 'session-current',
    actorRole: 'admin',
    endpoint: null,
    cockpitSessionId: null,
    commandName: null,
    correlationId: null,
    targetType: 'user',
    targetId: 'user-alice',
    parameters: {},
    errorCode: null,
    sourceType: 'local_hmi',
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function useAdminDefaults() {
  mockedApi.me.mockResolvedValue(adminIdentity)
  mockedApi.users.mockResolvedValue({ users: [currentUser, alice] })
  mockedApi.sessions.mockResolvedValue({
    sessions: [
      {
        id: 'session-alice-active',
        userId: alice.id,
        createdAt: '2026-08-21T08:00:00Z',
        expiresAt: '2026-08-22T08:00:00Z',
        lastSeenAt: null,
        revokedAt: null,
        revokeReason: null,
      },
    ],
  })
  mockedApi.audit.mockResolvedValue({ events: [], nextCursor: null })
  mockedApi.changeRole.mockResolvedValue({
    changed: true,
    revokedSessionIds: ['session-alice-active'],
    revokePropagation: 'complete',
    failedRevokePropagationSessionIds: [],
  })
  mockedApi.setDisabled.mockResolvedValue({
    changed: true,
    revokedSessionIds: ['session-alice-active'],
    revokePropagation: 'complete',
    failedRevokePropagationSessionIds: [],
  })
  mockedApi.revokeSession.mockResolvedValue({
    changed: true,
    revokedSessionIds: ['session-alice-active'],
    revokePropagation: 'complete',
    failedRevokePropagationSessionIds: [],
  })
  mockedApi.logout.mockResolvedValue({ loggedOut: true })
}

describe('PlatformConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAdminDefaults()
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('shows a truthful loading state, then an unauthenticated login whose password is cleared', async () => {
    const me = deferred<PlatformIdentity>()
    mockedApi.me.mockReturnValue(me.promise)
    mockedApi.login.mockResolvedValue({ ...adminIdentity, role: 'viewer' })

    render(<PlatformConsole />)
    expect(screen.getByText('正在核验平台会话…')).toBeInTheDocument()

    me.reject(new PlatformApiError(401, 'session_required', 'Session required.'))
    expect(await screen.findByRole('heading', { name: '平台登录' })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'alice' } })
    const password = screen.getByLabelText('密码') as HTMLInputElement
    fireEvent.change(password, { target: { value: 'secret-value' } })
    fireEvent.submit(screen.getByRole('button', { name: '登录' }).closest('form')!)

    await waitFor(() => expect(mockedApi.login).toHaveBeenCalledWith('alice', 'secret-value'))
    await waitFor(() => expect(password.value).toBe(''))
    expect(await screen.findByRole('tab', { name: 'Operational Audit' })).toBeInTheDocument()
  })

  it('shows all admin ledgers and disables self-protected controls', async () => {
    render(<PlatformConsole />)

    expect(await screen.findByRole('tab', { name: 'Users' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Sessions' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Audit' })).toBeInTheDocument()
    expect(await screen.findByText('Alice Operator')).toBeInTheDocument()
    const aliceRow = screen.getByText('Alice Operator').closest('tr')!
    expect(aliceRow.querySelector(`time[datetime="${alice.updatedAt}"]`)).not.toBeNull()
    expect(screen.getByLabelText('Current Admin 角色')).toBeDisabled()
    expect(screen.getByRole('button', { name: '禁用 Current Admin' })).toBeDisabled()
  })

  it('shortens UUID session evidence while retaining the full identifier metadata', async () => {
    const sessionId = '33333333-3333-4333-8333-333333333333'
    mockedApi.sessions.mockResolvedValue({
      sessions: [{
        id: sessionId,
        userId: alice.id,
        createdAt: '2026-08-21T08:00:00Z',
        expiresAt: '2026-08-22T08:00:00Z',
        lastSeenAt: null,
        revokedAt: null,
        revokeReason: null,
      }],
    })
    render(<PlatformConsole />)

    fireEvent.click(await screen.findByRole('tab', { name: 'Sessions' }))

    const evidence = await screen.findByText('33333333…3333')
    expect(evidence).toHaveAttribute('title', sessionId)
  })

  it('renders audit actor identity and command evidence when present', async () => {
    mockedApi.audit.mockResolvedValue({
      events: [{
        ...auditEvent('event-command', 'command.execute'),
        actorUserId: 'user-current',
        commandName: 'set_theme',
      }],
      nextCursor: null,
    })
    render(<PlatformConsole />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Audit' }))

    expect(await screen.findByText('actor / user-current · admin')).toBeInTheDocument()
    expect(screen.getByText('command / set_theme')).toBeInTheDocument()
  })

  it('keeps the platform tabs as a coherent roving tab pattern with keyboard navigation', async () => {
    render(<PlatformConsole />)

    const usersTab = await screen.findByRole('tab', { name: 'Users' })
    const sessionsTab = screen.getByRole('tab', { name: 'Sessions' })
    const auditTab = screen.getByRole('tab', { name: 'Audit' })

    expect(usersTab).toHaveAttribute('id', 'platform-tab-users')
    expect(sessionsTab).toHaveAttribute('id', 'platform-tab-sessions')
    expect(auditTab).toHaveAttribute('id', 'platform-tab-audit')
    expect(usersTab).toHaveAttribute('tabindex', '0')
    expect(sessionsTab).toHaveAttribute('tabindex', '-1')
    expect(auditTab).toHaveAttribute('tabindex', '-1')

    for (const tab of [usersTab, sessionsTab, auditTab]) {
      const panelId = tab.getAttribute('aria-controls')
      expect(panelId).toBeTruthy()
      expect(document.getElementById(panelId!)).toHaveAttribute('role', 'tabpanel')
    }

    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'platform-tab-users')

    fireEvent.keyDown(usersTab, { key: 'ArrowRight' })
    expect(sessionsTab).toHaveFocus()
    expect(sessionsTab).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'platform-tab-sessions')

    fireEvent.keyDown(sessionsTab, { key: 'End' })
    expect(auditTab).toHaveFocus()
    expect(auditTab).toHaveAttribute('aria-selected', 'true')

    fireEvent.keyDown(auditTab, { key: 'Home' })
    expect(usersTab).toHaveFocus()
    expect(usersTab).toHaveAttribute('aria-selected', 'true')
  })

  it.each(['operator', 'viewer'] as const)('%s sees only role-scoped Operational Audit', async (role) => {
    mockedApi.me.mockResolvedValue({ ...adminIdentity, role })
    mockedApi.audit.mockResolvedValue({ events: [], nextCursor: null })

    render(<PlatformConsole />)

    expect(await screen.findByRole('tab', { name: 'Operational Audit' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Users' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Sessions' })).not.toBeInTheDocument()
    expect(screen.getByText('当前角色范围内暂无审计事件。')).toBeInTheDocument()
    expect(mockedApi.users).not.toHaveBeenCalled()
  })

  it('clears every privileged panel when any request returns 401', async () => {
    const audit = deferred<{ events: AuditEventView[]; nextCursor: string | null }>()
    mockedApi.audit.mockReturnValue(audit.promise)
    render(<PlatformConsole />)

    expect(await screen.findByText('Alice Operator')).toBeInTheDocument()
    audit.reject(new PlatformApiError(401, 'session_invalid', 'Expired.'))

    expect(await screen.findByRole('heading', { name: '平台登录' })).toBeInTheDocument()
    expect(screen.queryByText('Alice Operator')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('never lets mutation refresh from an old auth generation overwrite a new login after 401', async () => {
    const initialAudit = deferred<{ events: AuditEventView[]; nextCursor: string | null }>()
    const mutation = deferred<Awaited<ReturnType<typeof platformApi.setDisabled>>>()
    mockedApi.audit
      .mockReturnValueOnce(initialAudit.promise)
      .mockResolvedValueOnce({ events: [auditEvent('event-fresh', 'fresh.viewer.audit')], nextCursor: null })
      .mockResolvedValueOnce({ events: [auditEvent('event-stale', 'stale.admin.refresh')], nextCursor: null })
    mockedApi.setDisabled.mockReturnValue(mutation.promise)
    mockedApi.login.mockResolvedValue({ ...adminIdentity, role: 'viewer' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PlatformConsole />)

    const aliceRow = (await screen.findByText('Alice Operator')).closest('tr')!
    fireEvent.click(within(aliceRow).getByRole('button', { name: '禁用 Alice Operator' }))
    expect(mockedApi.setDisabled).toHaveBeenCalledWith(alice.id, true)

    initialAudit.reject(new PlatformApiError(401, 'session_invalid', 'Expired.'))
    expect(await screen.findByRole('heading', { name: '平台登录' })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'viewer' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'viewer-secret' } })
    fireEvent.submit(screen.getByRole('button', { name: '登录' }).closest('form')!)
    expect(await screen.findByText('fresh.viewer.audit')).toBeInTheDocument()

    await act(async () => {
      mutation.resolve({
        changed: true,
        revokedSessionIds: [],
        revokePropagation: 'complete',
        failedRevokePropagationSessionIds: [],
      })
    })
    expect(mockedApi.audit).toHaveBeenCalledTimes(2)
    expect(screen.getByText('fresh.viewer.audit')).toBeInTheDocument()
    expect(screen.queryByText('stale.admin.refresh')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('ignores delayed load-more success from an invalidated auth generation', async () => {
    const users = deferred<Awaited<ReturnType<typeof platformApi.users>>>()
    const oldPage = deferred<Awaited<ReturnType<typeof platformApi.audit>>>()
    mockedApi.users.mockReturnValue(users.promise)
    mockedApi.audit
      .mockResolvedValueOnce({ events: [auditEvent('event-initial', 'initial.admin.audit')], nextCursor: 'old-cursor' })
      .mockReturnValueOnce(oldPage.promise)
      .mockResolvedValueOnce({ events: [auditEvent('event-fresh', 'fresh.viewer.audit')], nextCursor: null })
    mockedApi.login.mockResolvedValue({ ...adminIdentity, role: 'viewer' })
    render(<PlatformConsole />)

    fireEvent.click(await screen.findByRole('tab', { name: 'Audit' }))
    expect(await screen.findByText('initial.admin.audit')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '加载更多证据' }))
    expect(mockedApi.audit).toHaveBeenLastCalledWith('old-cursor')

    users.reject(new PlatformApiError(401, 'session_invalid', 'Expired.'))
    expect(await screen.findByRole('heading', { name: '平台登录' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'viewer' } })
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'viewer-secret' } })
    fireEvent.submit(screen.getByRole('button', { name: '登录' }).closest('form')!)
    expect(await screen.findByText('fresh.viewer.audit')).toBeInTheDocument()

    await act(async () => {
      oldPage.resolve({ events: [auditEvent('event-stale', 'stale.admin.page')], nextCursor: null })
    })
    expect(screen.getByText('fresh.viewer.audit')).toBeInTheDocument()
    expect(screen.queryByText('stale.admin.page')).not.toBeInTheDocument()
  })

  it('keys session results to the selected user when responses resolve out of order', async () => {
    const aliceSessions = deferred<Awaited<ReturnType<typeof platformApi.sessions>>>()
    const bobSessions = deferred<Awaited<ReturnType<typeof platformApi.sessions>>>()
    mockedApi.users.mockResolvedValue({ users: [currentUser, alice, bob] })
    mockedApi.sessions.mockImplementation((userId) => (
      userId === alice.id ? aliceSessions.promise : bobSessions.promise
    ))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PlatformConsole />)

    fireEvent.click(await screen.findByRole('tab', { name: 'Sessions' }))
    expect(mockedApi.sessions).toHaveBeenCalledWith(alice.id)
    fireEvent.change(screen.getByLabelText('选择用户'), { target: { value: bob.id } })
    await waitFor(() => expect(mockedApi.sessions).toHaveBeenCalledWith(bob.id))

    await act(async () => {
      bobSessions.resolve({
        sessions: [{
          id: 'session-bob-active',
          userId: bob.id,
          createdAt: '2026-08-21T09:00:00Z',
          expiresAt: '2026-08-22T09:00:00Z',
          lastSeenAt: null,
          revokedAt: null,
          revokeReason: null,
        }],
      })
    })
    expect(await screen.findByText('session-bob-active')).toBeInTheDocument()

    await act(async () => {
      aliceSessions.resolve({
        sessions: [{
          id: 'session-alice-stale',
          userId: alice.id,
          createdAt: '2026-08-21T08:00:00Z',
          expiresAt: '2026-08-22T08:00:00Z',
          lastSeenAt: null,
          revokedAt: null,
          revokeReason: null,
        }],
      })
    })
    expect(screen.queryByText('session-alice-stale')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '撤销 session-bob-active' }))
    await waitFor(() => expect(mockedApi.revokeSession).toHaveBeenCalledWith('session-bob-active'))
    expect(mockedApi.revokeSession).not.toHaveBeenCalledWith('session-alice-stale')
  })

  it('shows a Users panel error and retries only the users loader', async () => {
    mockedApi.users
      .mockRejectedValueOnce(new PlatformApiError(503, 'database_unavailable', 'Users unavailable.'))
      .mockResolvedValueOnce({ users: [currentUser, alice] })
    render(<PlatformConsole />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Users unavailable.')
    fireEvent.click(screen.getByRole('button', { name: '重试 Users' }))
    expect(await screen.findByText('Alice Operator')).toBeInTheDocument()
    expect(mockedApi.users).toHaveBeenCalledTimes(2)
  })

  it('shows a Sessions panel error and retries for the selected user', async () => {
    mockedApi.sessions
      .mockRejectedValueOnce(new PlatformApiError(503, 'database_unavailable', 'Sessions unavailable.'))
      .mockResolvedValueOnce({
        sessions: [{
          id: 'session-alice-retried',
          userId: alice.id,
          createdAt: '2026-08-21T08:00:00Z',
          expiresAt: '2026-08-22T08:00:00Z',
          lastSeenAt: null,
          revokedAt: null,
          revokeReason: null,
        }],
      })
    render(<PlatformConsole />)

    fireEvent.click(await screen.findByRole('tab', { name: 'Sessions' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sessions unavailable.')
    fireEvent.click(screen.getByRole('button', { name: '重试 Sessions' }))
    expect(await screen.findByText('session-alice-retried')).toBeInTheDocument()
    expect(mockedApi.sessions).toHaveBeenLastCalledWith(alice.id)
  })

  it('shows an Audit panel error and retries the role-scoped audit loader', async () => {
    mockedApi.me.mockResolvedValue({ ...adminIdentity, role: 'viewer' })
    mockedApi.audit
      .mockRejectedValueOnce(new PlatformApiError(503, 'database_unavailable', 'Audit unavailable.'))
      .mockResolvedValueOnce({ events: [auditEvent('event-retried', 'audit.retried')], nextCursor: null })
    render(<PlatformConsole />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Audit unavailable.')
    fireEvent.click(screen.getByRole('button', { name: '重试 Operational Audit' }))
    expect(await screen.findByText('audit.retried')).toBeInTheDocument()
    expect(mockedApi.audit).toHaveBeenCalledTimes(2)
  })

  it('gates role, disable, and revoke mutations behind explicit confirmation', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm')
    render(<PlatformConsole />)
    await screen.findByText('Alice Operator')

    const aliceRow = screen.getByText('Alice Operator').closest('tr')!
    confirmSpy.mockReturnValueOnce(false)
    fireEvent.change(within(aliceRow).getByLabelText('Alice Operator 角色'), {
      target: { value: 'viewer' },
    })
    expect(mockedApi.changeRole).not.toHaveBeenCalled()

    confirmSpy.mockReturnValueOnce(true)
    fireEvent.change(within(aliceRow).getByLabelText('Alice Operator 角色'), {
      target: { value: 'viewer' },
    })
    await waitFor(() => expect(mockedApi.changeRole).toHaveBeenCalledWith(alice.id, 'viewer'))

    confirmSpy.mockReturnValueOnce(false)
    fireEvent.click(within(aliceRow).getByRole('button', { name: '禁用 Alice Operator' }))
    expect(mockedApi.setDisabled).not.toHaveBeenCalled()

    confirmSpy.mockReturnValueOnce(true)
    fireEvent.click(within(aliceRow).getByRole('button', { name: '禁用 Alice Operator' }))
    await waitFor(() => expect(mockedApi.setDisabled).toHaveBeenCalledWith(alice.id, true))

    fireEvent.click(screen.getByRole('tab', { name: 'Sessions' }))
    expect(await screen.findByText('session-alice-active')).toBeInTheDocument()
    const revoke = screen.getByRole('button', { name: '撤销 session-alice-active' })
    confirmSpy.mockReturnValueOnce(false)
    fireEvent.click(revoke)
    expect(mockedApi.revokeSession).not.toHaveBeenCalled()
    confirmSpy.mockReturnValueOnce(true)
    fireEvent.click(revoke)
    await waitFor(() => expect(mockedApi.revokeSession).toHaveBeenCalledWith('session-alice-active'))
  })

  it('reports committed degraded propagation with exact failed realtime session ids', async () => {
    mockedApi.setDisabled.mockResolvedValue({
      changed: true,
      revokedSessionIds: ['session-a', 'session-b'],
      revokePropagation: 'degraded',
      failedRevokePropagationSessionIds: ['session-b'],
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<PlatformConsole />)
    const aliceRow = (await screen.findByText('Alice Operator')).closest('tr')!

    fireEvent.click(within(aliceRow).getByRole('button', { name: '禁用 Alice Operator' }))

    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('数据库变更已提交')
    expect(status).toHaveTextContent('session-b')
    expect(status).not.toHaveTextContent('失败，已回滚')
  })

  it('appends opaque audit pages and blocks duplicate concurrent load-more requests', async () => {
    const secondPage = deferred<{ events: AuditEventView[]; nextCursor: string | null }>()
    mockedApi.audit
      .mockResolvedValueOnce({ events: [auditEvent('event-1', 'user.role.changed')], nextCursor: 'opaque-1' })
      .mockReturnValueOnce(secondPage.promise)
    render(<PlatformConsole />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Audit' }))
    expect(await screen.findByText('user.role.changed')).toBeInTheDocument()

    const loadMore = screen.getByRole('button', { name: '加载更多证据' })
    fireEvent.click(loadMore)
    fireEvent.click(loadMore)
    expect(mockedApi.audit).toHaveBeenCalledTimes(2)
    expect(mockedApi.audit).toHaveBeenLastCalledWith('opaque-1')
    expect(loadMore).toBeDisabled()

    secondPage.resolve({ events: [auditEvent('event-2', 'session.revoked')], nextCursor: null })
    expect(await screen.findByText('session.revoked')).toBeInTheDocument()
    expect(screen.getByText('user.role.changed')).toBeInTheDocument()
  })

  it('shows actionable retry for non-auth identity errors', async () => {
    mockedApi.me
      .mockRejectedValueOnce(new PlatformApiError(503, 'database_unavailable', 'Database unavailable.'))
      .mockResolvedValueOnce({ ...adminIdentity, role: 'viewer' })
    render(<PlatformConsole />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable.')
    fireEvent.click(screen.getByRole('button', { name: '重试会话核验' }))
    expect(await screen.findByRole('tab', { name: 'Operational Audit' })).toBeInTheDocument()
  })
})
