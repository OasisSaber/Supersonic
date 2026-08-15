# G4 Slice D Command / WebSocket Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Issue #57 — wire server-side identity, joint authorization, and AuditEvent audit into the gp05.v1 HTTP command and WebSocket snapshot channels.

**Architecture:** Extend `app.platform` with a framework-free command gateway and WebSocket registry; FastAPI routers stay adapters; `app.main` remains the only composition root. `CockpitService` keeps full real-time authority.

**Tech Stack:** Python 3.11, FastAPI, dataclasses/Protocols, SQLAlchemy 2 async, psycopg, pytest/pytest-asyncio, uv, pnpm, Jujutsu.

## Global Constraints

- Implement only [Issue #57](https://github.com/OasisSaber/Supersonic/issues/57), in one jj change based on merged `main@436eb777`.
- Do not change `gp05.v1` contracts, `CockpitService` authority, session/login/revoke semantics, the legacy router chain, deployment, or release.
- Do not add UI, admin surfaces, OAuth/SSO/JWT platforms, Redis, message queues, or distributed registries.
- Audit facts go through the existing sanitization allowlists; never log raw secrets, cookies, tokens, private text, or full paths.
- Management commands require a durable `attempted` AuditEvent before mutation.
- Push and Draft PR creation are not authorized by this plan; they require a later, separate authorization.

---

## File structure

- Create `apps/backend/app/platform/command_gateway.py`: `PlatformCommandGateway` + `GatewayResult` (AuditEvent boundary).
- Create `apps/backend/app/platform/websocket_registry.py`: `WebSocketSessionRegistry`.
- Modify `apps/backend/app/api/cockpit_router.py`: optional platform wiring (resolver/gateway/registry), 401 handling, revoke-aware WS serving.
- Modify `apps/backend/app/api/platform_session_router.py`: notify registry on logout/revoke (via injected hook) — only if needed; prefer composition in main.
- Modify `apps/backend/app/main.py`: compose gateway/resolver/registry into routers when `database_url` is configured.
- Create unit tests: `apps/backend/tests/test_platform_command_gateway.py`, `apps/backend/tests/test_websocket_registry.py`.
- Create PostgreSQL integration tests: `apps/backend/integration_tests/test_slice_d_command_audit.py`.
- Docs: this plan + `docs/superpowers/specs/2026-08-15-g4-slice-d-command-websocket-integration-design.md`.

### Task 1: WebSocket session registry

**Files:**
- Create: `apps/backend/app/platform/websocket_registry.py`
- Test: `apps/backend/tests/test_websocket_registry.py`

**Interfaces:**

```python
class WebSocketSessionRegistry:
    def register(self, session_id: str, connection: object) -> None: ...
    def close_all(self, session_id: str) -> None: ...
    def disconnect(self, session_id: str, connection: object) -> None: ...
    def active_sessions(self) -> set[str]: ...
```

- [ ] Write failing tests: register adds; close_all closes and removes all connections of one session; disconnect removes only the given connection; close_all is idempotent for unknown session.
- [ ] Run the focused test and observe missing-module failures.
- [ ] Implement a thread-safe in-memory registry (asyncio-aware; connections are closed via their `close()` coroutine through a small protocol, or callers close them — decide: registry stores connections and a close callback).

**Decision:** The registry stores `(session_id -> set[connection])` plus an async close hook provided by the caller (`close_connection: Callable[[object], Awaitable[None]]`); `close_all` awaits all closes via the hook and clears the set. Tests inject a recording hook.
- [ ] Re-run focused tests and `ruff check apps/backend`.

### Task 2: Platform command gateway on the AuditEvent boundary

**Files:**
- Create: `apps/backend/app/platform/command_gateway.py`
- Test: `apps/backend/tests/test_platform_command_gateway.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class GatewayResult:
    envelope: SnapshotEnvelopeV1
    audit_delivery: AuditDelivery

class PlatformCommandGateway:
    def __init__(self, *, authority: CockpitService, policy: RoleCommandPolicy,
                 audit: AuditEventAppendPort, fallback: AuditFallbackPort | None,
                 id_factory, clock) -> None: ...
    async def apply_command(self, principal: Principal, command: CommandEnvelopeV1,
                            *, server_endpoint: EndpointId) -> GatewayResult: ...
```

Ports (framework-free, mirror existing audit boundary):
- `AuditEventAppendPort`: `async def append(self, event: AuditEvent) -> bool` (true = inserted) — implemented by a thin adapter over `PlatformUnitOfWork.audit_events` + commit (reuse `PostgresAuditSink`).
- `AuditFallbackPort`: `append(self, event: AuditEvent) -> None` — `JsonlAuditFallback` or in-memory buffer for tests.

Semantics (must match legacy gateway behavior exactly):
- Role forbidden → record `rejected/role_forbidden`, allow fallback, raise `RoleForbidden`.
- Management command → require primary available; record `attempted` without fallback before mutation; then apply.
- Command rejected by cockpit → record `rejected/<code>`, allow fallback, re-raise.
- Unexpected exception → record `error/internal_error`, allow fallback, re-raise.
- Success → record `succeeded`, allow fallback, return result.
- Audit event fields: action `cockpit.command`, result, delivery, actor ids/role from principal, endpoint, command_name, correlation_id, sanitized parameters (existing `sanitize_audit_event` path), error_code, source_type `local_hmi`, occurred_at UTC, id from id_factory.

- [ ] Write failing tests covering the five branches above with fake ports (assert event contents, order, fallback usage, and that conflicts propagate).
- [ ] Run the focused test and observe import failures.
- [ ] Implement gateway; reuse `_MANAGEMENT_COMMANDS` set and `RoleCommandPolicy` from existing authorization module.
- [ ] Re-run focused tests and lint.

### Task 3: Cockpit router platform wiring

**Files:**
- Modify: `apps/backend/app/api/cockpit_router.py`

**Behavior:**
- Extend `create_cockpit_router` with optional `platform: PlatformCommandWire | None` and `ws_registry: WebSocketSessionRegistry | None`.
- `PlatformCommandWire` protocol: `resolve(raw_secret: str) -> SessionIdentity`, `apply(principal, command, server_endpoint) -> GatewayResult`, plus cookie name from settings.
- HTTP command: if platform wire present → read cookie, resolve (401 `authentication_required` on `InvalidSession`/missing), call gateway; map `RoleForbidden` → 403; otherwise fall back to today's direct path.
- WebSocket: if platform wire present → exact-Origin check (403), resolve principal from cookie (close on failure), register connection, serve snapshots, deregister on disconnect; revoke closes via registry.
- Keep the existing direct path byte-for-byte when platform is None.

- [ ] Write/adjust router tests (existing `test_api_v1.py`/smoke must keep passing in degraded mode).
- [ ] Implement wiring with minimal diff; do not alter the snapshot/WS message loop beyond registration/deregistration.

### Task 4: Composition root and revoke propagation

**Files:**
- Modify: `apps/backend/app/main.py`
- Modify: `apps/backend/app/api/platform_session_router.py` (only if logout/revoke wiring needs a hook; prefer composing registry into SessionService through a callback).

**Behavior:**
- When `database_url` is set: build `PostgresAuditSink` (existing), registry, gateway, wire resolver = `SessionService.resolve` (already exists), pass into `create_cockpit_router`.
- Revoke propagation: `SessionService.revoke` already exists as a trusted internal API; add an optional `on_revoke: Callable[[str], Awaitable[None]]` hook (or compose registry into main and call `close_all` after revoke via the platform_session router's admin path — check what exists; if no admin revoke route exists, wire the hook into `logout` and `revoke` at composition time).

- [ ] Inspect existing `platform_session_router` for revoke surface; decide hook placement.
- [ ] Implement composition; keep degraded path intact.
- [ ] Run `test_api_composition.py` and smoke; fix regressions.

### Task 5: PostgreSQL integration coverage

**Files:**
- Create: `apps/backend/integration_tests/test_slice_d_command_audit.py`

- [ ] Write integration tests: authorized command persists attempted+succeeded facts (actor/endpoint/command fields); rejected command persists rejected fact; management command persists attempted before mutation; revoke closes registered connections (registry behavior with fake connections against real DB session service).
- [ ] Run with `TEST_DATABASE_URL` + `SUPERSONIC_ALLOW_TEST_DB_RESET=1` (WSL PostgreSQL 16 as in Slice C).

### Task 6: Review and verify the complete Slice D change

- [ ] Run targeted backend tests, `pnpm lint:backend`, `pnpm test:backend`, and the authoritative `& 'C:\Program Files\Git\bin\bash.exe' scripts/validate.sh`.
- [ ] Run PostgreSQL integration gate and `pnpm smoke:gp05`.
- [ ] Inspect `jj status`, full `jj diff`, sensitive-data scans; confirm no Router/protocol/legacy changes outside scope.
- [ ] Re-read Issue #57 against the implementation; document actual verification results and known limits.
- [ ] Do not push or create a Draft PR; await a separate authorization for those external operations.

## Verification record (2026-08-15)

- WebSocket registry unit suite: 7 passed (register/close_all/disconnect/active sessions).
- Platform command gateway unit suite: 10 passed (role-forbidden, attempted-before-mutation,
  endpoint rejection, primary outage fallback, management-command hard failure, lost delivery
  with and without a configured fallback, conflict propagation).
- Router wiring tests: 7 passed (401 missing cookie, 401 invalid session, 503 database outage
  during resolve, 403 role forbidden, 200 success, control-disabled 403, WS dual-flag gate).
- Session service suite with on_revoke hook: 38 passed (logout/revoke notify hook after commit;
  failed revoke does not notify).
- Full backend unit suite: 448 passed, 2 skipped.
- pnpm check: passed - backend 448 passed / 2 skipped; frontend 46 passed; production build OK;
  ruff + eslint clean.
- bash scripts/validate.sh: passed (exit 0).
- PostgreSQL integration (real PostgreSQL test database, TEST_DATABASE_URL ending _test,
  SUPERSONIC_ALLOW_TEST_DB_RESET=1): 53 passed, including Slice D command-audit persistence
  (attempted+succeeded, rejected) and registry close-on-revoke semantics.
- pnpm smoke:gp05: passed (real-process gp05.v1 runtime chain).
- git diff --check: passed. Sensitive-data scan: no secrets, paths, or artifacts added.
- Adversarial code review findings addressed in head: HIGH (production composition now degrades
  to LOST without a configured fallback and maps AuditUnavailable to a structured 503), MEDIUM
  (resolve DB/migration outages surface as 503 not 401 with preserved chain; WS platform/registry
  dual-flag gate moved to router construction), LOW (dead code removed; management-command
  attempted remains durable while outcomes are best-effort, documented).
- Scope: no Router re-composition outside cockpit_router, no protocol change, no legacy router
  removal, no UI, no deployment. Degraded no-database path unchanged and covered by existing tests.
- No push or Draft PR was attempted, per the current authorization boundary.
