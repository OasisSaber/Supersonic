# G4 Slice C Audit Persistence Design

- Status: approved in the current conversation on 2026-08-13
- Source: [Issue #55](https://github.com/OasisSaber/Supersonic/issues/55)
- Base: `main@origin` after PR #54

## Goal

Implement the storage and query boundary for immutable `AuditEvent` facts without
adding an HTTP route, connecting the Command Gateway, or changing the Cockpit
runtime authority.

## Scope and boundaries

Slice C adds a framework-free audit query service, a PostgreSQL primary sink, a
bounded JSONL fallback, and a manual reconciliation CLI. It extends the existing
PostgreSQL audit repository with a bounded keyset query.

It does not add a FastAPI Router, Gateway wiring, WebSocket behavior, UI, admin
surface, background worker, runtime fallback selection, deployment, merge, or
release. Slice D owns runtime command and transport integration.

`CockpitService` remains the unique authority for real-time vehicle, navigation,
risk, media, Cockpit Session, and snapshot state. Reconciliation imports audit
facts only; it never replays a Cockpit command.

## Query model

`AuditQueryService.list_for_role(role, cursor, limit)` is a service-layer API.
It checks platform readiness and opens a short Unit of Work. The service maps:

- `admin` to all sanitized audit facts;
- `operator` and `viewer` to operational facts only.

Operational facts are a fail-closed allowlist: `cockpit.command` (and nested
`cockpit.command.*` actions), `risk.*`, and `recovery.*`. Authentication, user
administration, Session administration, security administration, and unknown
actions are therefore unavailable to Operator and Viewer.

The repository accepts an `AuditQuery` with a maximum page size of 100 and a
cursor containing `(occurred_at, id)`. It orders descending by these columns,
fetches `limit + 1`, and returns a cursor based on the final returned event. It
does not expose arbitrary predicates or a SQL-like filter language.

## Primary PostgreSQL sink

`PostgresAuditSink` is an outboard adapter over `PlatformReadinessPort` and a
Unit-of-Work factory. For each event it checks readiness, calls
`AuditEventRepository.append()`, commits explicitly, and returns whether the
UUID was newly inserted. UUID uniqueness alone is not treated as idempotency:
when `append()` reports no insert, the sink reads the existing fact with
`get_by_id()` and compares canonical durable identity. The same UUID with the
same canonical fact is an idempotent duplicate; the same UUID with a different
canonical fact raises `AuditEventConflict` before commit. Canonical identity
is computed after sanitization with UUID and UTC normalization, and compares
every durable field including delivery, so PRIMARY/FALLBACK differences and
un-redacted content differences fail visibly instead of being silently dropped.
Canonical comparison operates on the sanitized durable fact only: differences
confined to fields the audit schema deliberately discards (unknown parameter
keys, raw secrets redacted to `[redacted]`) are intentionally treated as
duplicates because the durable fact cannot distinguish them.

The sink is not wired into the existing legacy `AuditSink` or Gateway in this
slice. The interface is intentionally about `AuditEvent`, not the older
command-specific `AuditRecord`.

## Fallback format and handling

`JsonlAuditFallback` serializes a versioned (`schemaVersion: 1`) event line.
It sets `delivery` to `fallback`, validates IDs/timestamps/length limits, and
always sanitizes `parameters` before writing. A `lost` delivery and the legacy
`degraded` result are rejected because neither is a persistent audit fact.
Every durable boundary also requires the exact built-in runtime types for an
`AuditEvent`, timestamp, result, delivery, and optional role. Duck-typed
date/enum objects and string subclasses are rejected or redacted before they
can control serialized values or bypass the allowlists.
AuditEvent parameters use a positive, typed field allowlist: bounded counters,
closed operational enums, known command names, UUIDs or the runtime-generated
`simulated-takeover-<uuid>` risk-ID form, temperature, and privacy state.
Unknown fields are discarded; explicitly sensitive fields and invalid values
become `[redacted]`. Top-level string metadata also uses field-specific positive
rules: fixed audit actions, endpoint names, command names, target types, error
codes, UUID correlation/Cockpit Session IDs, and UUID or runtime-generated
simulated-risk target IDs. This prevents raw private keys or free-form text from
becoming durable audit data.

The fallback caps one file at 1 MiB by default. A new line that would exceed the
cap raises a visible `AuditFallbackFull` error; it does not rotate, overwrite,
or silently discard an existing file. New POSIX directories/files request
owner-only modes (`0700` / `0600`). On Windows the controlled host's directory
ACL remains the enforcement mechanism because the standard library cannot prove
or rewrite inherited NTFS ACLs safely.

The strict decoder rejects malformed JSON (including non-finite constants),
unexpected field sets, invalid enum values, naive timestamps, invalid UUIDs,
non-object parameters, and records whose delivery is not `fallback`. It
validates the decoded raw structure before sanitizing it, so sanitization cannot
turn malformed durable data into an acceptable record. This prevents
reconciliation from accepting partly corrupt data.

## Manual reconciliation

`AuditReconciler` validates the complete fallback source before opening a write
transaction. In dry-run mode it reports the validated count without touching
the database. In normal mode it imports every event through the existing
repository in one Unit of Work, returns inserted and duplicate counts, and
commits once. Events are first scanned for intra-file identity collisions:
duplicate UUIDs with different canonical facts fail before any database work.
When the repository reports a non-insert for an event, the reconciler reads the
existing fact with `get_by_id()`; an equivalent canonical fact counts as a
duplicate, while a different canonical fact raises `AuditEventConflict` and
rolls back the whole batch.

The thin `scripts/reconcile_audit_fallback.py` CLI is local-only. It loads the
database URL through normal runtime settings, never prints the DSN or full input
path, and emits a JSON report. The reconciler holds a same-directory cooperative
lock from source snapshot through database commit, fingerprint verification, and
archiving. After a complete import commits, it creates a collision-free
same-directory `<source>.reconciled-<uuid>` hard-link archive and removes the
source; if source removal fails, it safely removes that new archive and reports
the failure. A parse, database, conflict, or archive error leaves the source unarchived.
Re-running the same source is safe because equivalent UUID facts are idempotent;
a UUID with different content fails visibly and never archives the source.

## Verification contract

- Unit tests cover query role scopes, cursor bounds, fallback sanitization and
  size enforcement, strict decoding, dry-run/no-write behavior, failure/no
  archive behavior, duplicate reporting, hostile runtime-object inputs, and
  canonical audit identity (UUID/timezone normalization, sanitized-equivalent
  payloads, and safe durable-field differences).
- Adapter tests cover compiled PostgreSQL query shape and primary-sink commit
  semantics without a database, including idempotent duplicates and
  `AuditEventConflict` on differing facts before commit.
- PostgreSQL integration tests cover descending `(occurred_at, id)` pagination,
  role scope filtering, the committed-then-retried reconciliation case, and
  same-UUID/different-fact conflicts that roll back without archiving the
  fallback source.
- Full project validation remains `bash scripts/validate.sh`; PostgreSQL
  integration tests remain an explicit `TEST_DATABASE_URL` gate.
