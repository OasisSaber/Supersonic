# G4 Slice D Command / WebSocket Integration Design

- Status: approved in the current conversation on 2026-08-15
- Source: [Issue #57](https://github.com/OasisSaber/Supersonic/issues/57)
- Base: `main@436eb777` after PR #56

## Goal

Wire server-side identity, joint authorization, and `AuditEvent` audit into the
existing `gp05.v1` HTTP command and WebSocket snapshot channels, without changing
`CockpitService` authority or the `gp05.v1` protocol.

## Scope and boundaries

Slice D adds a server-side `PrincipalResolver`, a platform command gateway that
joins `RolePolicy` with the existing endpoint policy while recording `AuditEvent`
facts, a single-process WebSocket session registry with revoke propagation, and
the `app.main` composition that activates them when a database is configured.

It does not add login/UI/admin surfaces, change `gp05.v1`, add a second protocol,
persist real-time cockpit state, or remove the legacy router chain. The
no-database degraded path keeps today's direct behavior.

`CockpitService` remains the unique authority for real-time vehicle, navigation,
risk, media, Cockpit Session, and snapshot state. The gateway never replays
commands and never treats audit delivery as the business outcome.

## Identity flow

```text
HTTP Router
  -> origin validation (same exact-origin rule as session router)
  -> PrincipalResolver (platform-session cookie -> SessionService.resolve)
  -> RolePolicy AND EndpointPolicy
  -> PlatformCommandGateway
  -> CockpitAuthority (apply_command)
```

```text
WebSocket handshake
  -> exact Origin allowlist (ExactOriginPolicy)
  -> PrincipalResolver
  -> WebSocketSessionRegistry (platform_session_id -> connections)
  -> CockpitService snapshot broker
```

- The client payload/source/role is never a permission fact; only the resolved
  `Principal` from `SessionService.resolve()` is used for authorization.
- Missing/invalid session yields 401 (`authentication_required`) and no state
  mutation; no audit fact is written for unauthenticated attempts unless the
  caller is already a valid principal.
- Role changes and user disable take effect at the next `resolve()`; revoking a
  Platform Session also closes its registered WebSocket connections.

## Command gateway

`PlatformCommandGateway` joins:

1. `RoleCommandPolicy` (existing operator/admin/viewer rules);
2. the existing endpoint policy inside `CockpitService.apply_command`
   (`CommandPolicy.validate` with `server_endpoint`).

It records one `AuditEvent` per authorized attempt with `delivery=primary`
through the existing `AuditEventRepository.append` path (PostgreSQL adapter),
falling back to the bounded JSONL fallback only for non-management commands so an
audit outage never turns a successful mutation into a false error. Management
commands (`set_theme`, `set_system_mode`, `reset_session`) require a durable
`attempted` event before mutation, preserving the Slice-B/C semantics.

Audit facts use the existing allowlisted sanitization; parameters, endpoint,
command name, correlation id, actor ids, and role come from the resolved
principal and the sanitized command payload.

## WebSocket registry

`WebSocketSessionRegistry` is an in-memory single-process registry:

- `register(session_id, connection)` adds one connection;
- `close_all(session_id)` closes every connection of a session and removes them;
- `disconnect(session_id, connection)` removes one connection.

`SessionService.revoke()` and logout notify the registry so revoked sessions stop
receiving snapshots immediately. The registry is not distributed and holds no
state other than connection objects; it is composed in `app.main` and injected
into the WebSocket endpoint and the session-service revoke path.

## Composition root

`app.main` composes the gateway, resolver, registry, and router wiring only when
`database_url` is configured. The degraded no-database path keeps the current
direct cockpit router behavior. All components are injected; no global state.

## Verification contract

- Unit tests cover joint authorization (role AND endpoint), attempted-before-
  mutation ordering for management commands, 401 on missing/invalid session,
  registry register/close/disconnect, revoke propagation to open connections,
  and read-only enforcement for Viewer/Overview.
- PostgreSQL integration tests cover command audit persistence (attempted/
  succeeded/rejected facts with the correct actor/endpoint fields) and
  revoke-closes-connection behavior.
- Full project validation remains `bash scripts/validate.sh`; PostgreSQL
  integration tests remain an explicit `TEST_DATABASE_URL` gate; `pnpm smoke:gp05`
  must stay green.
