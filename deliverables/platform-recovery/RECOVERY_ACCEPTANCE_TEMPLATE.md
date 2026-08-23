# Slice E recovery acceptance record

Use this record with the [operator guidance](README.md), the [backup manifest example](backup-manifest.example.json), the [restore report example](restore-report.example.json), the [application acceptance example](acceptance.example.json), and the verified [backup manifest](backup-manifest.json), [restore report](restore-report.json), and [application acceptance](acceptance.json). Sanitized screenshots belong under [screenshots/](screenshots/). Template entries begin as `pending` or `not_run`; the verified JSON records capture the completed Task 11 checks while the human gate stays pending.

## Identification

| Field | Value |
|---|---|
| Issue | `#61` |
| Candidate commit SHA | `618b10271fd0c30bf7c53b6bb098e2df448bf27c` |
| Source commit SHA | `2522c93cf77deb1fcd2a141e97c1b39be26a5752` |
| Backup manifest reference | `backup-manifest.json` |
| Restore report reference | `restore-report.json` |
| Acceptance report reference | `acceptance.json` |
| Target kind | `isolated_restore_test` |
| Dump committed | `false` |

## Operator gates

- [ ] `pending` — maintenance window is active and stop platform writers before backup.
- [ ] `pending` — runtime dump and logs are outside Git and scheduled for removal after rehearsal.
- [ ] `pending` — `SUPERSONIC_ALLOW_DB_RESTORE=1` is scoped only to this isolated rehearsal.
- [ ] `pending` — `RESTORE_DATABASE_URL` identifies a different database ending `_restore_test`.
- [ ] `pending` — operator understands the restore does not create or drop a whole database and does not run Alembic upgrade.

## Recovery sequence

Record only sanitized observations. Never include a password, token, cookie, DSN, host/user detail, private user payload, raw command stderr, or absolute local path.

| Check | Initial status | Sanitized evidence reference |
|---|---|---|
| Checksum and repository-head preflight | `not_run` | `pending` |
| `pg_restore --clean --if-exists --no-owner --no-acl --single-transaction` | `not_run` | `pending` |
| Restored Alembic revision | `not_run` | `pending` |
| Exact `users`, `platform_sessions`, and `audit_events` row counts | `not_run` | `pending` |
| Enabled-admin/session/revoke invariants | `not_run` | `pending` |
| Disabled-account persistence | `not_run` | `pending` |
| Session-revocation persistence | `not_run` | `pending` |
| Restored admin login | `not_run` | `pending` |
| Restored audit visibility | `not_run` | `pending` |
| Relevant GP05 smoke and app acceptance | `not_run` | `pending` |

## Evidence review

- [ ] `pending` — report references are relative repository paths.
- [ ] `pending` — screenshot references are sanitized relative paths under `screenshots/`, or use reviewed external PR attachments.
- [ ] `pending` — log references point only to deliberately sanitized summaries, never raw output.
- [ ] `pending` — no dump, SQL export, credentials, private records, or local absolute paths are retained.
- [ ] `pending` — Task 11 real rehearsal evidence has been reviewed for Issue #61.

Automated checks and sanitized evidence are present, but this checkbox remains pending for the
human reviewer. The candidate SHA above identifies the tested code-and-screenshot snapshot;
evidence-only and documentation edits follow it in the same Issue #61 change.

## Human gate

Human review and human merge remain required. Do not record `G4 PLATFORM COMPLETE` in this template; that label is permitted only after human merge.
