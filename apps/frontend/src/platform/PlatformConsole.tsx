import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent, ReactNode } from 'react'
import {
  PlatformApiError,
  platformApi,
  type AdminMutationResponse,
  type AuditEventView,
  type PlatformIdentity,
  type PlatformRole,
  type PlatformSession,
  type PlatformUser,
} from './platformApi'
import './platform-console.css'

type Panel = 'users' | 'sessions' | 'audit'
type Notice = { kind: 'error' | 'committed'; message: string } | null

export function PlatformConsole() {
  const [identity, setIdentity] = useState<PlatformIdentity | null>(null)
  const [checkingIdentity, setCheckingIdentity] = useState(true)
  const [identityError, setIdentityError] = useState<string | null>(null)
  const [panel, setPanel] = useState<Panel>('audit')
  const [users, setUsers] = useState<PlatformUser[]>([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [usersError, setUsersError] = useState<string | null>(null)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<PlatformSession[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [auditEvents, setAuditEvents] = useState<AuditEventView[]>([])
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [mutationBusy, setMutationBusy] = useState(false)
  const [auditPaging, setAuditPaging] = useState(false)
  const authEpochRef = useRef(0)
  const identityRequestRef = useRef(0)
  const usersRequestRef = useRef(0)
  const sessionsRequestRef = useRef(0)
  const auditRequestRef = useRef(0)
  const auditPageRequestRef = useRef(0)
  const mutationRequestRef = useRef(0)
  const selectedUserIdRef = useRef<string | null>(null)
  const auditPagingRef = useRef(false)
  const tabRefs = useRef<Partial<Record<Panel, HTMLButtonElement | null>>>({})

  const clearPrivilegedState = useCallback((message: string | null) => {
    authEpochRef.current += 1
    usersRequestRef.current += 1
    sessionsRequestRef.current += 1
    auditRequestRef.current += 1
    auditPageRequestRef.current += 1
    mutationRequestRef.current += 1
    selectedUserIdRef.current = null
    setIdentity(null)
    setIdentityError(null)
    setUsers([])
    setUsersLoading(false)
    setUsersError(null)
    setSelectedUserId(null)
    setSessions([])
    setSessionsLoading(false)
    setSessionsError(null)
    setAuditEvents([])
    setAuditLoading(false)
    setAuditError(null)
    setNextCursor(null)
    setNotice(message ? { kind: 'error', message } : null)
    setMutationBusy(false)
    auditPagingRef.current = false
    setAuditPaging(false)
  }, [])

  const acceptIdentity = useCallback((current: PlatformIdentity) => {
    authEpochRef.current += 1
    usersRequestRef.current += 1
    sessionsRequestRef.current += 1
    auditRequestRef.current += 1
    auditPageRequestRef.current += 1
    mutationRequestRef.current += 1
    selectedUserIdRef.current = null
    setIdentity(current)
    setIdentityError(null)
    setPanel(current.role === 'admin' ? 'users' : 'audit')
    setUsers([])
    setUsersLoading(false)
    setUsersError(null)
    setSelectedUserId(null)
    setSessions([])
    setSessionsLoading(false)
    setSessionsError(null)
    setAuditEvents([])
    setAuditLoading(false)
    setAuditError(null)
    setNextCursor(null)
    setNotice(null)
    setMutationBusy(false)
    auditPagingRef.current = false
    setAuditPaging(false)
  }, [])

  const handleAuthenticatedError = useCallback((
    value: unknown,
    epoch: number,
    setScopedError?: (message: string) => void,
  ) => {
    if (epoch !== authEpochRef.current) return
    if (value instanceof PlatformApiError && value.status === 401) {
      clearPrivilegedState('会话已失效，已清除受保护数据。请重新登录。')
      return
    }
    const message = value instanceof Error ? value.message : '平台请求失败，请稍后重试。'
    if (setScopedError) setScopedError(message)
    else setNotice({ kind: 'error', message })
  }, [clearPrivilegedState])

  const verifyIdentity = useCallback(async () => {
    const requestId = ++identityRequestRef.current
    setCheckingIdentity(true)
    setIdentityError(null)
    try {
      const current = await platformApi.me()
      if (requestId !== identityRequestRef.current) return
      acceptIdentity(current)
    } catch (value) {
      if (requestId !== identityRequestRef.current) return
      if (value instanceof PlatformApiError && value.status === 401) {
        clearPrivilegedState(null)
      } else {
        clearPrivilegedState(null)
        setIdentityError(value instanceof Error ? value.message : '无法核验平台会话。')
      }
    } finally {
      if (requestId === identityRequestRef.current) setCheckingIdentity(false)
    }
  }, [acceptIdentity, clearPrivilegedState])

  const selectUser = useCallback((userId: string | null) => {
    if (selectedUserIdRef.current === userId) return
    selectedUserIdRef.current = userId
    sessionsRequestRef.current += 1
    setSelectedUserId(userId)
    setSessions([])
    setSessionsError(null)
    setSessionsLoading(userId !== null)
  }, [])

  const loadUsers = useCallback(async () => {
    const epoch = authEpochRef.current
    const requestId = ++usersRequestRef.current
    setUsersLoading(true)
    setUsersError(null)
    try {
      const result = await platformApi.users()
      if (epoch !== authEpochRef.current || requestId !== usersRequestRef.current) return
      setUsers(result.users)
      const current = selectedUserIdRef.current
      if (!current || !result.users.some((user) => user.id === current)) {
        selectUser(
          result.users.find((user) => user.id !== identity?.userId)?.id
            ?? result.users[0]?.id
            ?? null,
        )
      }
    } catch (value) {
      if (epoch === authEpochRef.current && requestId === usersRequestRef.current) {
        handleAuthenticatedError(value, epoch, setUsersError)
      }
    } finally {
      if (epoch === authEpochRef.current && requestId === usersRequestRef.current) {
        setUsersLoading(false)
      }
    }
  }, [handleAuthenticatedError, identity?.userId, selectUser])

  const loadSessions = useCallback(async (userId: string) => {
    const epoch = authEpochRef.current
    const requestId = ++sessionsRequestRef.current
    setSessionsLoading(true)
    setSessionsError(null)
    try {
      const result = await platformApi.sessions(userId)
      if (
        epoch !== authEpochRef.current
        || requestId !== sessionsRequestRef.current
        || selectedUserIdRef.current !== userId
      ) return
      if (result.sessions.some((session) => session.userId !== userId)) {
        throw new PlatformApiError(502, 'invalid_response', 'Session response did not match the selected user.')
      }
      setSessions(result.sessions)
    } catch (value) {
      if (
        epoch === authEpochRef.current
        && requestId === sessionsRequestRef.current
        && selectedUserIdRef.current === userId
      ) {
        handleAuthenticatedError(value, epoch, setSessionsError)
      }
    } finally {
      if (
        epoch === authEpochRef.current
        && requestId === sessionsRequestRef.current
        && selectedUserIdRef.current === userId
      ) setSessionsLoading(false)
    }
  }, [handleAuthenticatedError])

  const loadAudit = useCallback(async () => {
    const epoch = authEpochRef.current
    const requestId = ++auditRequestRef.current
    auditPageRequestRef.current += 1
    auditPagingRef.current = false
    setAuditPaging(false)
    setAuditLoading(true)
    setAuditError(null)
    try {
      const result = await platformApi.audit()
      if (epoch !== authEpochRef.current || requestId !== auditRequestRef.current) return
      setAuditEvents(result.events)
      setNextCursor(result.nextCursor)
    } catch (value) {
      if (epoch === authEpochRef.current && requestId === auditRequestRef.current) {
        handleAuthenticatedError(value, epoch, setAuditError)
      }
    } finally {
      if (epoch === authEpochRef.current && requestId === auditRequestRef.current) {
        setAuditLoading(false)
      }
    }
  }, [handleAuthenticatedError])

  useEffect(() => {
    void verifyIdentity()
  }, [verifyIdentity])

  useEffect(() => {
    if (!identity) return
    void loadAudit()
    if (identity.role === 'admin') void loadUsers()
  }, [identity, loadAudit, loadUsers])

  useEffect(() => {
    if (identity?.role === 'admin' && panel === 'sessions' && selectedUserId) {
      void loadSessions(selectedUserId)
    }
  }, [identity?.role, loadSessions, panel, selectedUserId])

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? null,
    [selectedUserId, users],
  )

  const runMutation = useCallback(async (
    action: () => Promise<AdminMutationResponse>,
    refresh: () => Promise<void>,
  ) => {
    if (mutationBusy) return
    const epoch = authEpochRef.current
    const requestId = ++mutationRequestRef.current
    setMutationBusy(true)
    setNotice(null)
    try {
      const result = await action()
      if (epoch !== authEpochRef.current || requestId !== mutationRequestRef.current) return
      await Promise.all([refresh(), loadAudit()])
      if (epoch !== authEpochRef.current || requestId !== mutationRequestRef.current) return
      if (result.revokePropagation === 'degraded') {
        setNotice({
          kind: 'committed',
          message: `数据库变更已提交；以下实时会话的关闭确认未送达：${result.failedRevokePropagationSessionIds.join(', ')}。`,
        })
      }
    } catch (value) {
      if (epoch === authEpochRef.current && requestId === mutationRequestRef.current) {
        handleAuthenticatedError(value, epoch)
      }
    } finally {
      if (epoch === authEpochRef.current && requestId === mutationRequestRef.current) {
        setMutationBusy(false)
      }
    }
  }, [handleAuthenticatedError, loadAudit, mutationBusy])

  const loadMoreAudit = useCallback(async () => {
    if (!nextCursor || auditPagingRef.current) return
    const epoch = authEpochRef.current
    const requestId = ++auditPageRequestRef.current
    auditPagingRef.current = true
    setAuditPaging(true)
    setAuditError(null)
    try {
      const result = await platformApi.audit(nextCursor)
      if (epoch !== authEpochRef.current || requestId !== auditPageRequestRef.current) return
      setAuditEvents((current) => [...current, ...result.events])
      setNextCursor(result.nextCursor)
    } catch (value) {
      if (epoch === authEpochRef.current && requestId === auditPageRequestRef.current) {
        handleAuthenticatedError(value, epoch, setAuditError)
      }
    } finally {
      if (epoch === authEpochRef.current && requestId === auditPageRequestRef.current) {
        auditPagingRef.current = false
        setAuditPaging(false)
      }
    }
  }, [handleAuthenticatedError, nextCursor])

  if (checkingIdentity) {
    return (
      <PlatformShell>
        <div className="platform-state" role="status">
          <span className="platform-pulse" aria-hidden="true" />
          <p>正在核验平台会话…</p>
        </div>
      </PlatformShell>
    )
  }

  if (!identity) {
    return (
      <PlatformShell>
        <LoginPanel
          initialError={identityError ?? (notice?.kind === 'error' ? notice.message : null)}
          busy={mutationBusy}
          onRetry={() => void verifyIdentity()}
          onLogin={async (username, password) => {
            const requestId = ++identityRequestRef.current
            setMutationBusy(true)
            setNotice(null)
            try {
              const current = await platformApi.login(username, password)
              if (requestId === identityRequestRef.current) acceptIdentity(current)
            } catch (value) {
              if (requestId === identityRequestRef.current) {
                setNotice({
                  kind: 'error',
                  message: value instanceof Error ? value.message : '登录请求失败，请重试。',
                })
              }
            } finally {
              if (requestId === identityRequestRef.current) setMutationBusy(false)
            }
          }}
        />
      </PlatformShell>
    )
  }

  const isAdmin = identity.role === 'admin'
  const panels: Panel[] = isAdmin ? ['users', 'sessions', 'audit'] : ['audit']
  const movePanel = (item: Panel) => {
    setPanel(item)
    tabRefs.current[item]?.focus()
  }
  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, item: Panel) => {
    const index = panels.indexOf(item)
    let nextIndex: number | null = null
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % panels.length
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + panels.length) % panels.length
    if (event.key === 'Home') nextIndex = 0
    if (event.key === 'End') nextIndex = panels.length - 1
    if (nextIndex === null || nextIndex === index) return
    event.preventDefault()
    movePanel(panels[nextIndex])
  }

  return (
    <PlatformShell>
      <header className="platform-identity-rail">
        <div className="platform-brand-lockup">
          <span className="platform-recorder-mark" aria-hidden="true" />
          <div>
            <p className="platform-eyebrow">Supersonic / evidence ledger</p>
            <h1>Platform Console</h1>
          </div>
        </div>
        <dl className="platform-identity-facts">
          <div><dt>Identity</dt><dd>{identity.displayName}</dd></div>
          <div><dt>Role</dt><dd><RoleBadge role={identity.role} /></dd></div>
          <div><dt>Expires</dt><dd>{formatTime(identity.expiresAt)}</dd></div>
        </dl>
        <button
          className="platform-button platform-button-quiet"
          disabled={mutationBusy}
          onClick={() => {
            const epoch = authEpochRef.current
            const requestId = ++mutationRequestRef.current
            setMutationBusy(true)
            void platformApi.logout()
              .then(() => {
                if (epoch === authEpochRef.current && requestId === mutationRequestRef.current) {
                  clearPrivilegedState(null)
                }
              })
              .catch((value: unknown) => {
                if (epoch === authEpochRef.current && requestId === mutationRequestRef.current) {
                  handleAuthenticatedError(value, epoch)
                }
              })
              .finally(() => {
                if (epoch === authEpochRef.current && requestId === mutationRequestRef.current) {
                  setMutationBusy(false)
                }
              })
          }}
        >
          退出登录
        </button>
      </header>

      {notice && (
        <div
          className={`platform-notice platform-notice-${notice.kind}`}
          role={notice.kind === 'error' ? 'alert' : 'status'}
        >
          <strong>{notice.kind === 'committed' ? '已提交 · 传播降级' : '请求未完成'}</strong>
          <span>{notice.message}</span>
        </div>
      )}

      <div className="platform-workspace">
         <nav className="platform-index" aria-label="平台功能" role="tablist">
           <p className="platform-index-label">Ledger index</p>
           {panels.map((item) => {
             const label = panelLabel(item, isAdmin)
             return (
               <button
                 key={item}
                 id={`platform-tab-${item}`}
                 className="platform-index-item"
                 role="tab"
                 aria-selected={panel === item}
                 aria-controls={`platform-panel-${item}`}
                 tabIndex={panel === item ? 0 : -1}
                 ref={(element) => { tabRefs.current[item] = element }}
                 onClick={() => movePanel(item)}
                 onKeyDown={(event) => handleTabKeyDown(event, item)}
               >
                <span aria-hidden="true">{item === 'users' ? '01' : item === 'sessions' ? '02' : '03'}</span>
                {label}
              </button>
            )
          })}
        </nav>

        <main className="platform-ledger">
           {panels.map((item) => item === panel ? (
             item === 'users' ? (
               <UsersPanel
                 key={item}
                 users={users}
                 loading={usersLoading}
                 error={usersError}
                 currentUserId={identity.userId}
                 busy={mutationBusy}
                 onRetry={() => void loadUsers()}
                 onRole={(user, role) => {
                   if (!window.confirm(`将 ${user.displayName} 的角色变更为 ${role}？其现有会话将被撤销。`)) return
                   void runMutation(() => platformApi.changeRole(user.id, role), loadUsers)
                 }}
                 onDisabled={(user, disabled) => {
                   const action = disabled ? '禁用' : '启用'
                   if (!window.confirm(`${action} ${user.displayName}？${disabled ? '其现有会话将被撤销。' : ''}`)) return
                   void runMutation(() => platformApi.setDisabled(user.id, disabled), loadUsers)
                 }}
               />
             ) : item === 'sessions' ? (
               <SessionsPanel
                 key={item}
                 users={users}
                 selectedUser={selectedUser}
                 sessions={sessions}
                 loading={sessionsLoading}
                 error={sessionsError}
                 busy={mutationBusy}
                 onRetry={() => {
                   if (selectedUserIdRef.current) void loadSessions(selectedUserIdRef.current)
                 }}
                 onSelect={selectUser}
                 onRevoke={(session) => {
                   const selectedAtConfirmation = selectedUserIdRef.current
                   if (!selectedAtConfirmation || session.userId !== selectedAtConfirmation) {
                     setSessionsError('所选身份已变化；请刷新会话登记册后重试。')
                     return
                   }
                   if (!window.confirm(`撤销会话 ${session.id}？目标在线会话将立即终止。`)) return
                   void runMutation(
                     () => platformApi.revokeSession(session.id),
                     () => selectedUserIdRef.current === selectedAtConfirmation
                       ? loadSessions(selectedAtConfirmation)
                       : Promise.resolve(),
                   )
                 }}
               />
             ) : (
               <AuditPanel
                 key={item}
                 title={isAdmin ? 'Audit' : 'Operational Audit'}
                 events={auditEvents}
                 loading={auditLoading}
                 error={auditError}
                 nextCursor={nextCursor}
                 paging={auditPaging}
                 onRetry={() => void loadAudit()}
                 onLoadMore={loadMoreAudit}
               />
             )
           ) : (
             <div
               key={item}
               id={`platform-panel-${item}`}
               role="tabpanel"
               aria-labelledby={`platform-tab-${item}`}
               hidden
             />
           ))}
        </main>
      </div>
    </PlatformShell>
  )
}

function PlatformShell({ children }: { children: ReactNode }) {
  return (
    <div className="platform-page" data-theme="night">
      <div className="platform-shell">{children}</div>
    </div>
  )
}

function LoginPanel({
  onLogin,
  onRetry,
  busy,
  initialError,
}: {
  onLogin: (username: string, password: string) => Promise<void>
  onRetry: () => void
  busy: boolean
  initialError: string | null
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submittedPassword = password
    setPassword('')
    void onLogin(username, submittedPassword)
  }

  return (
    <div className="platform-login-layout">
      <section className="platform-login-context">
        <span className="platform-recorder-mark" aria-hidden="true" />
        <p className="platform-eyebrow">Supersonic / evidence ledger</p>
        <h1>身份状态与审计证据，保持同一条事实链。</h1>
        <p>管理员维护角色和会话；每个角色只读取服务端授予范围内的运行证据。</p>
      </section>
      <form className="platform-login" onSubmit={submit}>
        <p className="platform-sequence">Platform access / 01</p>
        <h2>平台登录</h2>
        {initialError && (
          <div className="platform-login-error" role="alert">
            <span>{initialError}</span>
            <button type="button" className="platform-text-button" onClick={onRetry}>
              重试会话核验
            </button>
          </div>
        )}
        <label>
          <span>用户名</span>
          <input
            autoComplete="username"
            value={username}
            maxLength={256}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
        </label>
        <label>
          <span>密码</span>
          <input
            autoComplete="current-password"
            type="password"
            value={password}
            maxLength={1024}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        <p className="platform-field-note">凭据仅用于本次请求；会话由 HttpOnly Cookie 承载。</p>
        <button className="platform-button platform-button-primary" disabled={busy}>
          {busy ? '登录中…' : '登录'}
        </button>
      </form>
    </div>
  )
}

function UsersPanel({
  users,
  loading,
  error,
  currentUserId,
  busy,
  onRetry,
  onRole,
  onDisabled,
}: {
  users: PlatformUser[]
  loading: boolean
  error: string | null
  currentUserId: string
  busy: boolean
  onRetry: () => void
  onRole: (user: PlatformUser, role: PlatformRole) => void
  onDisabled: (user: PlatformUser, disabled: boolean) => void
}) {
  return (
    <section
      id="platform-panel-users"
      role="tabpanel"
      aria-labelledby="platform-tab-users"
      className="platform-panel"
    >
      <PanelHeading
        sequence="Identity registry / 01"
        title="Users"
        description="角色和账户状态来自持久化平台身份。变更会留下审计记录，并可能撤销在线会话。"
      />
      {error && <PanelError label="Users" message={error} onRetry={onRetry} />}
      {loading ? (
        <PanelLoading>正在读取身份登记册…</PanelLoading>
      ) : users.length === 0 && !error ? (
        <EmptyState>当前没有可管理用户。</EmptyState>
      ) : users.length > 0 ? (
        <div className="platform-table-wrap">
          <table className="platform-table">
            <thead><tr><th>Identity</th><th>Role</th><th>Status</th><th>Updated</th><th>Action</th></tr></thead>
            <tbody>
              {users.map((user) => {
                const self = user.id === currentUserId
                return (
                  <tr key={user.id}>
                    <td><strong>{user.displayName}</strong><span>@{user.username}</span></td>
                    <td>
                      <select
                        value={user.role}
                        disabled={busy || self}
                        aria-label={`${user.displayName} 角色`}
                        title={self ? '当前账户不能变更自身角色' : undefined}
                        onChange={(event) => onRole(user, event.target.value as PlatformRole)}
                      >
                        <option value="admin">admin</option>
                        <option value="operator">operator</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </td>
                    <td>
                      <span className={`platform-status ${user.disabledAt ? 'is-disabled' : 'is-active'}`}>
                        {user.disabledAt ? 'Disabled' : 'Enabled'}
                      </span>
                    </td>
                    <td><time dateTime={user.updatedAt}>{formatTime(user.updatedAt)}</time></td>
                    <td>
                      <button
                        className="platform-button platform-button-quiet"
                        disabled={busy || self}
                        aria-label={`${user.disabledAt ? '启用' : '禁用'} ${user.displayName}`}
                        title={self ? '当前账户不能禁用自身' : undefined}
                        onClick={() => onDisabled(user, !user.disabledAt)}
                      >
                        {user.disabledAt ? '启用' : '禁用'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}

function SessionsPanel({
  users,
  selectedUser,
  sessions,
  loading,
  error,
  busy,
  onRetry,
  onSelect,
  onRevoke,
}: {
  users: PlatformUser[]
  selectedUser: PlatformUser | null
  sessions: PlatformSession[]
  loading: boolean
  error: string | null
  busy: boolean
  onRetry: () => void
  onSelect: (userId: string) => void
  onRevoke: (session: PlatformSession) => void
}) {
  return (
    <section
      id="platform-panel-sessions"
      role="tabpanel"
      aria-labelledby="platform-tab-sessions"
      className="platform-panel"
    >
      <div className="platform-panel-heading platform-panel-heading-split">
        <PanelHeading
          sequence="Session registry / 02"
          title="Sessions"
          description="查看指定身份的持久化会话；撤销会终止目标在线会话。"
        />
        <label className="platform-compact-field">
          <span>Identity</span>
          <select
            value={selectedUser?.id ?? ''}
            onChange={(event) => onSelect(event.target.value)}
            aria-label="选择用户"
            disabled={users.length === 0}
          >
            {users.map((user) => <option key={user.id} value={user.id}>{user.displayName}</option>)}
          </select>
        </label>
      </div>
      {error && <PanelError label="Sessions" message={error} onRetry={onRetry} />}
      {loading ? (
        <PanelLoading>正在读取会话登记册…</PanelLoading>
      ) : sessions.length === 0 && !error ? (
        <EmptyState>该身份当前没有可显示会话。</EmptyState>
      ) : sessions.length > 0 ? (
        <div className="platform-table-wrap">
          <table className="platform-table platform-session-table">
            <thead><tr><th>Session evidence</th><th>Created</th><th>Expires</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id}>
                  <td><code title={session.id}>{shortSessionId(session.id)}</code></td>
                  <td>{formatTime(session.createdAt)}</td>
                  <td>{formatTime(session.expiresAt)}</td>
                  <td>
                    <span className={`platform-status ${session.revokedAt ? 'is-disabled' : 'is-active'}`}>
                      {session.revokedAt ? `Revoked · ${session.revokeReason ?? 'reason unavailable'}` : 'Active / not revoked'}
                    </span>
                  </td>
                  <td>
                    <button
                      className="platform-button platform-button-danger"
                      disabled={busy || session.revokedAt !== null}
                      aria-label={`撤销 ${session.id}`}
                      onClick={() => onRevoke(session)}
                    >
                      撤销
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}

function AuditPanel({
  title,
  events,
  loading,
  error,
  nextCursor,
  paging,
  onRetry,
  onLoadMore,
}: {
  title: 'Audit' | 'Operational Audit'
  events: AuditEventView[]
  loading: boolean
  error: string | null
  nextCursor: string | null
  paging: boolean
  onRetry: () => void
  onLoadMore: () => Promise<void>
}) {
  return (
    <section
      id="platform-panel-audit"
      role="tabpanel"
      aria-labelledby="platform-tab-audit"
      className="platform-panel"
    >
      <PanelHeading
        sequence="Recorder tape / 03"
        title={title}
        description={title === 'Audit'
          ? '按服务端全局审计范围读取，不使用客户端提供的 scope。'
          : '仅显示服务端依据当前角色授予的运行审计范围。'}
      />
      {error && <PanelError label={title} message={error} onRetry={onRetry} />}
      {loading ? (
        <PanelLoading>正在读取审计证据…</PanelLoading>
      ) : events.length === 0 && !error ? (
        <EmptyState>当前角色范围内暂无审计事件。</EmptyState>
      ) : events.length > 0 ? (
        <ol className="platform-recorder-tape">
          {events.map((event) => (
            <li key={event.id} className="platform-audit-event">
              <div className="platform-tape-marker" aria-hidden="true" />
              <article>
                <header>
                  <div><strong>{event.action}</strong><code>{event.id}</code></div>
                  <time dateTime={event.occurredAt}>{formatTime(event.occurredAt)}</time>
                </header>
                <div className="platform-event-facts">
                  <span className={`platform-result result-${event.result}`}>{event.result}</span>
                  <span>{event.delivery}</span>
                  {(event.actorUserId || event.actorRole) && (
                    <span>actor / {[event.actorUserId, event.actorRole].filter(Boolean).join(' · ')}</span>
                  )}
                  {event.commandName && <span>command / {event.commandName}</span>}
                  {event.targetType && <span>target / {event.targetType}:{event.targetId ?? '—'}</span>}
                  {event.endpoint && <span>endpoint / {event.endpoint}</span>}
                  {event.errorCode && <span className="platform-error-code">error / {event.errorCode}</span>}
                </div>
                {Object.keys(event.parameters).length > 0 && (
                  <details>
                    <summary>Evidence payload</summary>
                    <pre>{JSON.stringify(event.parameters, null, 2)}</pre>
                  </details>
                )}
              </article>
            </li>
          ))}
        </ol>
      ) : null}
      {nextCursor && !error && (
        <button
          className="platform-button platform-load-more"
          disabled={paging}
          onClick={() => void onLoadMore()}
        >
          {paging ? '正在读取下一段…' : '加载更多证据'}
        </button>
      )}
    </section>
  )
}

function PanelHeading({ sequence, title, description }: { sequence: string; title: string; description: string }) {
  return (
    <header className="platform-panel-heading">
      <p className="platform-sequence">{sequence}</p>
      <h2>{title}</h2>
      <p>{description}</p>
    </header>
  )
}

function EmptyState({ children }: { children: ReactNode }) {
  return <div className="platform-empty"><span aria-hidden="true">○</span><p>{children}</p></div>
}

function PanelLoading({ children }: { children: ReactNode }) {
  return <div className="platform-empty" role="status"><span className="platform-pulse" aria-hidden="true" /><p>{children}</p></div>
}

function PanelError({ label, message, onRetry }: { label: string; message: string; onRetry: () => void }) {
  return (
    <div className="platform-panel-error" role="alert">
      <div><strong>{label} 暂时不可用</strong><p>{message}</p></div>
      <button className="platform-button platform-button-quiet" onClick={onRetry}>重试 {label}</button>
    </div>
  )
}

function RoleBadge({ role }: { role: PlatformRole }) {
  return <span className={`platform-role role-${role}`}>{role}</span>
}

function panelLabel(panel: Panel, isAdmin: boolean) {
  if (panel === 'users') return 'Users'
  if (panel === 'sessions') return 'Sessions'
  return isAdmin ? 'Audit' : 'Operational Audit'
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function shortSessionId(value: string) {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
  return uuid.test(value) ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
}
