# Platform recovery evidence

This directory defines the repository-safe evidence contract for the Slice E recovery rehearsal in Issue #61. Task 10 supplied empty examples and guidance. Task 11 ran the approved isolated rehearsal; the repository retains sanitized aggregate evidence and never the database dump.

## Files

- [Backup manifest example](backup-manifest.example.json) mirrors the strict seven-key backup schema.
- [Restore report example](restore-report.example.json) records checksum, repository-head, restore, revision, row-count, and invariant verification.
- [Application acceptance example](acceptance.example.json) records persistence, restored-app, audit, and GP05 checks.
- [Verified backup manifest](backup-manifest.json) retains the exact seven-key aggregate manifest from the rehearsal.
- [Verified restore report](restore-report.json) records checksum, revision, row-count, invariant, and destructive-restore results.
- [Verified application acceptance](acceptance.json) records restored login, role-scoped audit, persistence, WebSocket revoke, and GP05 results.
- [Recovery acceptance template](RECOVERY_ACCEPTANCE_TEMPLATE.md) is the operator checklist and review record.
- [Sanitized screenshots](screenshots/) contain only synthetic identities and bounded UI evidence.

## Task 11 browser evidence

- [Platform service unavailable](screenshots/platform-service-unavailable.png) records the
  expected `/platform` degraded state when the backend is intentionally started without a
  configured platform database. The username is synthetic, the password field is blank, and
  no cookie, token, connection string, host/user detail, or private database payload is shown.

This screenshot proves only the unavailable-service UI path. The real restored-database checks
are recorded separately below.

- [Restored admin Users](screenshots/restored-admin-users.png) shows the synthetic admin identity,
  restored disabled account, and restored role change.
- [Restored revoked Sessions](screenshots/restored-revoked-sessions.png) shows two synthetic
  `user_disabled` session records after restore.
- [Restored admin Audit](screenshots/restored-admin-audit.png) shows the synthetic security facts,
  including `user.role_change`, `user.disable`, and `session.revoke`.

The browser views contain only synthetic names and identifiers. No password field, cookie,
token digest, connection string, host/user detail, or private database payload is retained.

## Task 11 verified rehearsal

- Source aggregate: 4 users, 6 platform sessions, and 9 audit events at Alembic revision
  `20260809_0001`.
- `pg_dump` custom backup and adjacent strict manifest completed with PostgreSQL 16.15.
- The dump checksum matched before destructive `pg_restore --clean` into the isolated
  `_restore_test` target; restored revision and exact row counts matched.
- Enabled-admin, disabled-user active-session, and revoke-reason invariants passed.
- Restored admin login, disabled-account rejection, revoked-session persistence, admin security
  audit visibility, operator/viewer scope restriction, post-commit WebSocket close, old-cookie
  rejection, old-WebSocket rejection, and `gp05.v1` four-client smoke were exercised.
- The rehearsal candidate SHA in the JSON reports is the code-and-screenshot snapshot tested
  before these evidence records were written. Final-head validation will be recorded in the Draft PR.

The runtime dump, temporary credentials, wrappers, and raw operational output remain outside Git
and are removed during rehearsal cleanup. Human review and human merge remain pending.

The `.example.json` files remain inert placeholders. They use only `pending` and `not_run`; do not treat a schema-valid example as rehearsal evidence. The three non-example JSON files are the sanitized Task 11 records.

## Safe rehearsal procedure

1. Schedule a maintenance window and stop platform writers before creating the backup. This keeps the dump snapshot and manifest row counts aligned.
2. Keep the dump and runtime artifacts outside Git or in ignored local storage. Remove them after the rehearsal. Never put a dump, SQL export, or database-derived record in this directory.
3. Confirm the source and candidate commit SHAs. Record only commit identifiers and the relative sanitized manifest reference.
4. For the isolated rehearsal only, set `SUPERSONIC_ALLOW_DB_RESTORE=1`. Set `RESTORE_DATABASE_URL` to a different database whose name ends `_restore_test`.
5. Run checksum and repository-head preflight before the destructive restore.
6. Restore with `pg_restore --clean --if-exists --no-owner --no-acl --single-transaction`.
7. Verify the restored Alembic revision, exact table row counts, and database invariants.
8. Start the application against the isolated restored database and verify disabled-account persistence, session-revocation persistence, restored admin login, audit visibility, and the relevant GP05 smoke/app acceptance.
9. Sanitize the retained evidence, remove runtime artifacts, and leave the human review and merge gate pending for a human decision.

The restore script does not create or drop a whole database and does not run Alembic upgrade. A revision mismatch is evidence of a failed preflight or verification, not permission to migrate the restored database silently.

## Sanitization boundary

Never record a password, token, cookie, DSN, host/user detail, private user payload, raw command stderr, or absolute local path. Do not paste connection strings or shell environments. Record only safe aggregates, statuses, commit SHAs, sanitized excerpts, and relative repository references.

Screenshots must be sanitized before retention. Prefer relative references below `screenshots/` or external PR attachments when that is safer; do not commit an image merely to make a checklist look populated. Logs must be short, sanitized summaries rather than raw output and should be referenced by relative path only when they are deliberately committed.

`G4 PLATFORM COMPLETE` may be recorded only after human merge. Neither an example nor the Task 11 rehearsal can cross that human merge gate.
