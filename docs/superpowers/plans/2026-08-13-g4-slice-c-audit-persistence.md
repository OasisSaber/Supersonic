# G4 Slice C Audit Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the Issue #55 audit storage/query boundary locally, with tests and no runtime Router or Gateway integration.

**Architecture:** Keep audit policy and services framework-free in `app.platform`; extend the existing PostgreSQL repository only through an explicit query port; implement the primary sink in the PostgreSQL adapter; use an independent strict JSONL/reconciliation subsystem. The CLI is a thin local adapter around the domain service and existing database factory.

**Tech Stack:** Python 3.11, dataclasses/Protocols, SQLAlchemy 2 async, PostgreSQL/psycopg, pytest/pytest-asyncio, uv, pnpm, Jujutsu.

## Global Constraints

- Implement only [Issue #55](https://github.com/OasisSaber/Supersonic/issues/55), in one jj change based on PR #54's merged `main@origin`.
- Do not modify FastAPI Router composition, `app.main`, `app.platform.gateway`, WebSocket handling, UI, role-admin UI, migrations, deployment, release, or the `gp05.v1` protocol.
- `AuditEvent` stays immutable; reconciliation imports facts and never replays a Cockpit command.
- No raw secret, cookie, token, private text, private path, SQL error, DSN, or uncontrolled full fallback path may appear in persisted audit data or CLI output.
- `AuditEvent.parameters` uses a positive typed allowlist; unknown keys are dropped and invalid
  known values are replaced with `[redacted]` before PostgreSQL, JSONL, query, or reconciliation.
- Query pages are bounded to 1--100 events and use descending `(occurred_at, id)` keyset pagination only.
- Operator and Viewer may see only the fail-closed operational action allowlist; Admin sees all sanitized facts.
- Fallback default cap is exactly `1_048_576` bytes; capacity exhaustion must be observable and must not overwrite/rotate data.
- Push and Draft PR creation are not authorized by this plan.

---

## File structure

- Modify `apps/backend/app/platform/models.py`: query cursor/page value types.
- Modify `apps/backend/app/platform/persistence.py`: typed audit-query port.
- Create `apps/backend/app/platform/audit_query.py`: role-scoped query service.
- Create `apps/backend/app/platform/audit_fallback.py`: versioned codec and bounded JSONL writer/reader.
- Create `apps/backend/app/platform/audit_reconciliation.py`: transactional import/report/archive policy.
- Create `apps/backend/app/platform/audit_validation.py`: shared exact runtime-type gate for durable audit facts.
- Modify `apps/backend/app/platform/sanitization.py`: positive persisted-metadata and parameter allowlists.
- Modify `apps/backend/app/adapters/postgres/repositories.py`: query translation and keyset SQL.
- Create `apps/backend/app/adapters/postgres/audit_sink.py`: explicit primary PostgreSQL sink.
- Create `scripts/reconcile_audit_fallback.py`: local-only CLI.
- Create focused unit tests under `apps/backend/tests/` and PostgreSQL integration coverage under `apps/backend/integration_tests/`.

### Task 1: Define the framework-free query contract

**Files:**
- Modify: `apps/backend/app/platform/models.py`
- Modify: `apps/backend/app/platform/persistence.py`
- Create: `apps/backend/app/platform/audit_query.py`
- Test: `apps/backend/tests/test_platform_audit_query.py`

**Interfaces:**

```python
class AuditQueryScope(StrEnum):
    ALL = "all"
    OPERATIONAL = "operational"

@dataclass(frozen=True, slots=True)
class AuditCursor:
    occurred_at: datetime
    event_id: str

@dataclass(frozen=True, slots=True)
class AuditQuery:
    scope: AuditQueryScope
    cursor: AuditCursor | None
    limit: int

@dataclass(frozen=True, slots=True)
class AuditPage:
    events: tuple[AuditEvent, ...]
    next_cursor: AuditCursor | None
```

- [x] Write failing tests showing Admin maps to `ALL`, Operator/Viewer map to `OPERATIONAL`, `limit=0` and `limit=101` fail before a UoW, and a repository page is returned unchanged.
- [x] Run `uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_platform_audit_query.py -q` and confirm collection/import failure.
- [x] Add the dataclasses, `AuditEventRepository.list_page(query)`, and `AuditQueryService.list_for_role()` with readiness/UoW behavior.
- [x] Re-run the focused test and `ruff check` for the changed platform files; record the red and green output.

### Task 2: Add strict, bounded fallback serialization

**Files:**
- Create: `apps/backend/app/platform/audit_fallback.py`
- Test: `apps/backend/tests/test_platform_audit_fallback.py`

**Interfaces:**

```python
class AuditFallbackError(RuntimeError): ...
class AuditFallbackFull(AuditFallbackError): ...
class AuditFallbackFormatError(AuditFallbackError): ...

class JsonlAuditFallback:
    def append(self, event: AuditEvent) -> AuditEvent: ...
    def load_events(self) -> list[AuditEvent]: ...
```

- [x] Write failing tests that prove a fallback event receives `delivery=fallback`, secret/private parameters are redacted, a capacity breach preserves the original file, malformed/unknown JSONL is rejected, and a naive timestamp cannot be encoded.
- [x] Run the focused test and observe missing-module failures.
- [x] Implement the schema-v1 codec, validation, owner-only creation request, strict reader, and no-rotation capacity rule.
- [x] Re-run focused tests and lint. Do not modify the legacy `JsonlAuditBuffer` or Gateway tests.

### Task 3: Implement reconciliation policy before its CLI

**Files:**
- Create: `apps/backend/app/platform/audit_reconciliation.py`
- Test: `apps/backend/tests/test_platform_audit_reconciliation.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class AuditReconciliationReport:
    validated: int
    imported: int
    duplicates: int
    dry_run: bool

class AuditReconciler:
    async def reconcile(
        self, events: Sequence[AuditEvent], *, dry_run: bool
    ) -> AuditReconciliationReport: ...
```

- [x] Write failing tests for dry-run/no-UoW writes, single transaction imports, duplicate count, primary/lost delivery rejection, and archive only after a successful report.
- [x] Run the focused test and observe the expected failure.
- [x] Implement full input validation before writing, one explicit commit, rollback-on-failure through the UoW, and collision-free same-directory archive creation after success.
- [x] Re-run focused tests and lint.

### Task 4: Add PostgreSQL query and primary-sink adapters

**Files:**
- Modify: `apps/backend/app/adapters/postgres/repositories.py`
- Create: `apps/backend/app/adapters/postgres/audit_sink.py`
- Test: `apps/backend/tests/test_postgres_audit_query.py`
- Test: `apps/backend/tests/test_postgres_audit_sink.py`

**Interfaces:**

```python
class PostgresAuditSink:
    async def append(self, event: AuditEvent) -> bool: ...
```

- [x] Write failing adapter tests asserting the compiled query filters operational actions, uses strict `<` keyset comparison and `limit + 1`, and that the sink checks readiness, commits, and returns the repository insertion result.
- [x] Run the two focused tests and observe import/method failures.
- [x] Implement SQLAlchemy query mapping, stable `next_cursor`, database-error translation, and a UoW-backed sink without importing FastAPI or Gateway code.
- [x] Re-run focused tests and `ruff check apps/backend/app/adapters/postgres`.

### Task 5: Add the local reconciliation CLI and integration coverage

**Files:**
- Create: `scripts/reconcile_audit_fallback.py`
- Create: `apps/backend/tests/test_reconcile_audit_fallback_cli.py`
- Create: `apps/backend/integration_tests/test_audit_persistence.py`

- [x] Write failing CLI tests for dry-run report, missing database configuration, malformed input/no archive, and success archive naming that excludes the full source path.
- [x] Run the CLI unit test and observe its failure.
- [x] Implement argument parsing (`--input`, `--dry-run`), sanitized JSON report, engine disposal, and archive-after-success behavior.
- [x] Write PostgreSQL integration tests for descending keyset pages, operational role scope, and executing the same fallback event twice to prove `imported=1` then `duplicates=1`.
- [x] Run the unit tests. The PostgreSQL integration gate is intentionally unrun because `TEST_DATABASE_URL` and `SUPERSONIC_ALLOW_TEST_DB_RESET=1` are not both configured.

### Task 6: Review and verify the complete Slice C change

- [x] Run targeted backend tests, `pnpm lint:backend`, `pnpm test:backend`, and the authoritative `& 'C:\Program Files\Git\bin\bash.exe' scripts/validate.sh`.
- [x] Inspect `jj status`, full `jj diff`, and sensitive-data scans. `jj diff --check` is unavailable in the installed jj version; the equivalent `git diff --check` against the base passed. The isolated Windows worktree emitted only ambient LF/CRLF conversion warnings. The diff contains no Router/Gateway/main changes, caches, generated artifacts, or credentials.
- [x] Re-read Issue #55 against the implementation and document actual verification results and the unrun PostgreSQL integration gate.
- [x] Do not push or create a Draft PR; await a separate authorization for those external operations.

## Verification record (2026-08-14)

- Focused Slice C security and persistence suite: `144 passed, 2 skipped` with
  pytest cache disabled. This includes runtime-type, string-subclass, and
  hostile-container regressions at JSONL, reconciliation, and PostgreSQL
  boundaries.
- Targeted Slice C Ruff check: passed.
- `pnpm check`: backend `411 passed, 2 skipped`; frontend `46 passed`; production
  frontend build succeeded. The test run emitted one existing FastAPI/TestClient
  deprecation warning.
- `bash scripts/validate.sh`: passed. Markdown links, YAML syntax, and shell
  validation passed; it then repeated the passing backend, frontend, and build
  checks. The isolated Windows worktree emitted one non-fatal pytest-cache
  permission warning in addition to the existing TestClient deprecation warning.
- Base-relative `git diff --check`: passed; its only output was the isolated
  worktree's ambient LF/CRLF conversion warnings.
- PostgreSQL integration tests are intentionally unrun: neither
  `TEST_DATABASE_URL` nor `SUPERSONIC_ALLOW_TEST_DB_RESET=1` is configured.
- Independent security review passed with no remaining blocking findings.
- No push or Draft PR was attempted, per the current authorization boundary.
