# G5 Review Matrix

Review-only traceability matrix for [Issue #65](https://github.com/OasisSaber/Supersonic/issues/65).

- Baseline: `main@7e1ea06e52964b09c8368943236847525a7deccc`
- Verdict: `CHANGES_REQUIRED`
- Counts: 0 Critical / 4 High / 5 Medium / 5 Low
- Statuses are limited to `PASS`, `FINDING`, and `NOT APPLICABLE`. A `FINDING` row references an existing G5 finding; it does not add to the counts.

## Architecture invariants

| # | Invariant | Status | Repo-relative evidence / finding |
| ---: | --- | --- | --- |
| 1 | `CockpitService` is the sole cockpit realtime state authority. | PASS | `apps/backend/app/cockpit/service.py`; `docs/design/2026-08-09-g3-platform-architecture-design.md` |
| 2 | PostgreSQL does not save or decide current vehicle, route, risk, media, or WebSocket snapshot state. | PASS | `docs/design/2026-08-09-g3-platform-architecture-design.md`; `apps/backend/app/main.py` |
| 3 | DB readiness is not in the per-snapshot hot path. | PASS | `apps/backend/app/cockpit/service.py`; `apps/backend/app/adapters/postgres/readiness.py`; `docs/design/2026-08-09-g3-platform-architecture-design.md` |
| 4 | FastAPI routers only adapt/authenticate/map errors and do not duplicate reusable business policy. | FINDING | `apps/backend/app/api/cockpit_router.py:68-73`; G5-ARCH-002 |
| 5 | `app.platform` remains framework-independent. | PASS | `apps/backend/app/platform/authorization.py`; `apps/backend/app/platform/command_gateway.py`; `docs/design/2026-08-09-g3-platform-architecture-design.md` |
| 6 | `app.main` is the composition root without a second platform container. | PASS | `apps/backend/app/main.py:133-218` |
| 7 | `gp05.v1` has no unrecorded breaking drift. | PASS | `contracts/gp05/v1/manifest.json`; G5 exact-head GP05 validation in `deliverables/g5-review/G5_FINDINGS_REPORT.md` |
| 8 | Cockpit Session and Platform Session concepts/fields are not mixed. | PASS | `apps/backend/app/contracts/v1.py`; `apps/backend/app/platform/models.py`; `apps/backend/app/platform/sessions.py` |
| 9 | Both RolePolicy and EndpointPolicy participate in command authorization. | PASS | `apps/backend/app/platform/authorization.py`; `apps/backend/app/platform/command_gateway.py`; `apps/backend/app/cockpit/policies.py` |
| 10 | Client role/endpoint self-claims are not authority. | PASS | `apps/backend/app/platform/models.py:119-123`; `apps/backend/app/api/cockpit_router.py`; `apps/backend/app/platform/sessions.py` |
| 11 | Overview remains read-only. | PASS | `apps/frontend/src/components/CockpitScreen.tsx`; `apps/frontend/src/components/CockpitScreen.test.tsx` |
| 12 | Degraded mode is not presented as full/real authority. | FINDING | `apps/frontend/src/components/screens/ClusterScreen.tsx`; `apps/frontend/src/components/screens/HudScreen.tsx`; `apps/frontend/src/components/screens/OverviewScreen.tsx`; G5-FE-002 |
| 13 | The single-process WebSocket registry boundary remains explicit and accurate. | PASS | `apps/backend/app/platform/websocket_registry.py`; `docs/design/2026-08-09-g3-platform-architecture-design.md` |
| 14 | No new second Audit model/runtime exists. | FINDING | `apps/backend/app/platform/gateway.py`; `apps/backend/app/platform/models.py`; `apps/backend/app/platform/command_gateway.py`; G5-ARCH-001 |
| 15 | Legacy compatibility code has not become canonical authority. | FINDING | `apps/backend/app/platform/__init__.py:9-19`; G5-ARCH-001 |

## Security / Auth checklist

| Review checklist | Status | Repo-relative evidence / finding |
| --- | --- | --- |
| Argon2id / pwdlib is the password verification boundary. | PASS | `apps/backend/app/adapters/security.py`; `apps/backend/pyproject.toml` |
| Unknown, wrong, and disabled credentials use the reviewed rejection envelope and delay. | PASS | `apps/backend/app/platform/sessions.py`; `apps/backend/app/api/platform_session_router.py` |
| Malformed credential stores are not reported as ordinary password errors. | PASS | `apps/backend/app/platform/sessions.py`; `apps/backend/app/adapters/security.py` |
| Password/hash/raw session secrets are sanitized from logs, Audit, and API payloads. | PASS | `apps/backend/app/platform/sanitization.py`; `apps/backend/app/platform/audit.py` |
| Raw session secret is confined to cookie/request boundary. | PASS | `apps/backend/app/api/platform_session_router.py`; `apps/backend/app/platform/sessions.py` |
| DB stores a session digest rather than the raw secret. | PASS | `apps/backend/app/platform/security.py`; `apps/backend/app/adapters/postgres/repositories.py` |
| Expiry, revoke, and disabled-user checks fail closed for resolve boundaries. | PASS | `apps/backend/app/platform/sessions.py`; `apps/backend/app/platform/admin.py` |
| Established WebSocket expiry and revoke-send enforcement fail closed. | FINDING | `apps/backend/app/api/cockpit_router.py:175-203`; G5-SEC-001/G5-SEC-002 |
| DB resolve failure is truthful `503`, not `401`. | PASS | `apps/backend/app/api/platform_session_router.py`; `apps/backend/app/api/platform_admin_router.py` |
| Session resolution has no sliding expiry. | PASS | `apps/backend/app/platform/sessions.py:130-146` |
| Cookie uses SameSite Strict and HTTPS Secure/`__Host-` semantics. | PASS | `apps/backend/app/config.py`; `apps/backend/app/api/platform_session_router.py` |
| Exact Origin comparison is used at the WebSocket boundary. | PASS | `apps/backend/app/api/cockpit_router.py:170-176`; `apps/backend/app/platform/security.py` |
| Cookie-authenticated command mutations enforce the exact Origin gate. | FINDING | `apps/backend/app/api/cockpit_router.py:59-79,98-123`; G5-SEC-003 |
| CORS methods and headers remain bounded. | PASS | `apps/backend/app/main.py:59-89,228-240` |
| HTTP commands resolve a server-side Platform Session. | PASS | `apps/backend/app/api/cockpit_router.py:88-123`; `apps/backend/app/platform/sessions.py` |
| WS handshake requires exact Origin and a valid session. | PASS | `apps/backend/app/api/cockpit_router.py:168-179` |
| Role policy and endpoint policy both run for a command. | PASS | `apps/backend/app/platform/command_gateway.py`; `apps/backend/app/cockpit/policies.py` |
| Revoke blocks new HTTP/WS identity resolution. | PASS | `apps/backend/app/platform/sessions.py`; `apps/backend/app/platform/admin.py` |
| Live WS close occurs after durable DB commit; degraded close is not reported as rollback. | PASS | `apps/backend/app/platform/admin.py`; `apps/backend/app/api/platform_admin_router.py`; `apps/backend/app/platform/websocket_registry.py` |
| Admin APIs resolve an Admin Principal server-side and deny Operator/Viewer management. | PASS | `apps/backend/app/api/platform_admin_router.py`; `apps/backend/app/platform/admin.py` |
| Self-disable/self-demotion, last-enabled-Admin, role-change revoke, and actor attribution protections are present. | PASS | `apps/backend/app/platform/admin.py`; `apps/backend/tests/test_platform_admin_service.py` |
| Frontend does not store auth tokens and UI hiding does not replace backend authorization. | PASS | `apps/frontend/src/platform/platformApi.ts`; `apps/backend/app/api/platform_admin_router.py` |
| Audit scope is server-resolved rather than query/client-role controlled. | PASS | `apps/backend/app/platform/audit_query.py`; `apps/backend/app/api/platform_admin_router.py` |

## Persistence / Audit / Recovery checklist

| Review checklist | Status | Repo-relative evidence / finding |
| --- | --- | --- |
| One `AsyncSession` is used per UoW/task. | PASS | `apps/backend/app/adapters/postgres/unit_of_work.py` |
| UoW commit/rollback and context-exit rollback are explicit. | PASS | `apps/backend/app/adapters/postgres/unit_of_work.py:30-89` |
| No generic `save()` weakens domain mutations. | PASS | `apps/backend/app/platform/persistence.py`; `apps/backend/app/adapters/postgres/repositories.py` |
| Migration schema matches models/repositories. | PASS | `apps/backend/migrations/versions`; `apps/backend/app/adapters/postgres/orm.py`; G5 PostgreSQL integration evidence |
| `AuditEvent` is the canonical durable fact. | PASS | `apps/backend/app/platform/models.py`; `apps/backend/app/platform/command_gateway.py` |
| Persistent delivery is PRIMARY/FALLBACK only; LOST is runtime-only. | PASS | `apps/backend/app/platform/models.py`; `apps/backend/app/platform/audit.py`; `apps/backend/app/adapters/postgres/audit_sink.py` |
| Same UUID/same fact is idempotent; same UUID/different fact is conflict. | PASS | `apps/backend/app/platform/audit_identity.py`; `apps/backend/app/platform/audit_reconciliation.py` |
| Management `attempted` commits before mutation. | FINDING | `apps/backend/app/platform/admin.py:165-201,224-261,282-309`; G5-AUD-001 |
| Ordinary Audit failure does not turn a real success into a false mutation failure. | PASS | `apps/backend/app/platform/command_gateway.py`; `apps/backend/app/platform/audit.py` |
| Admin-only Audit visibility and fail-closed Operator/Viewer namespaces remain enforced. | PASS | `apps/backend/app/platform/audit_query.py`; `apps/backend/app/api/platform_admin_router.py`; `apps/backend/app/platform/sanitization.py` |
| Fallback sanitizes, bounds files, and rejects malformed/oversized input. | PASS | `apps/backend/app/platform/audit_fallback.py`; `apps/backend/app/platform/sanitization.py` |
| Conflict aborts import; dry-run has no mutation/archive; per-file apply is atomic; archive follows commit; source remains on failure. | PASS | `apps/backend/app/platform/audit_reconciliation.py`; `apps/backend/tests/test_platform_audit_fallback.py` |
| Backup is real custom `pg_dump`; password is absent from argv/report. | PASS | `scripts/platform_backup.py`; `apps/backend/tests/test_backup_restore_contract.py` |
| Dump finalization has an explicit incomplete-artifact boundary. | FINDING | `scripts/platform_backup.py:435-440`; G5-REC-001 |
| Restore requires explicit opt-in, distinct `_restore_test` target, checksum, and no silent Alembic upgrade. | PASS | `scripts/platform_restore.py`; `apps/backend/tests/test_backup_restore_contract.py` |
| Restore verifies revision/count/invariants; dump is not committed. | PASS | `scripts/platform_restore.py`; `deliverables/platform-recovery/restore-report.json`; `.gitignore` |
| Actual recovery uses a public checkpoint and truthful humanGate semantics. | PASS | `deliverables/platform-recovery/backup-manifest.json`; `deliverables/platform-recovery/restore-report.json`; `deliverables/platform-recovery/acceptance.json` |
| Recovery evidence self-reference remains independently traceable. | FINDING | `deliverables/platform-recovery/acceptance.json`; G5-REC-002 |

## Frontend / Visual checklist

| Review checklist | Status | Repo-relative evidence / finding |
| --- | --- | --- |
| All six declared cockpit routes select the matching endpoint identity. | PASS | `apps/frontend/src/App.tsx`; `apps/frontend/src/components/CockpitScreen.tsx` |
| Unknown cockpit paths remain explicit rather than silently becoming Overview. | FINDING | `apps/frontend/src/App.tsx:7-10`; G5-FE-003 |
| Overview is read-only and has no command controls. | PASS | `apps/frontend/src/components/CockpitScreen.tsx`; `apps/frontend/src/components/CockpitScreen.test.tsx` |
| Control does not bypass backend Platform authorization. | PASS | `apps/backend/app/api/cockpit_router.py:88-123`; unauthenticated commands are rejected by the server. |
| Cockpit command client includes Platform credentials for cross-origin requests. | FINDING | `apps/frontend/src/lib/useCockpitCommand.ts:23-35`; G5-FE-001 |
| Normal/degraded/offline labels are truthful. | FINDING | `apps/frontend/src/components/screens/ClusterScreen.tsx`; `apps/frontend/src/components/screens/HudScreen.tsx`; G5-FE-002 |
| Loading/error states are bounded and understandable without invented state. | FINDING | `apps/frontend/src/components/screens/OverviewScreen.tsx`; `apps/frontend/src/components/screens/CenterScreen.tsx`; G5-FE-002 |
| `/platform*` branches before cockpit snapshot/WS startup. | PASS | `apps/frontend/src/App.tsx`; `apps/frontend/src/platform/PlatformConsole.tsx`; `apps/frontend/src/stores/cockpit.ts` |
| Platform console has unauthenticated login, Admin Users/Sessions/Audit, and 401-to-login behavior. | PASS | `apps/frontend/src/platform/PlatformConsole.tsx`; `apps/frontend/src/platform/platformApi.ts` |
| Platform mutation confirmation, degraded revoke visibility, and no token storage are present. | PASS | `apps/frontend/src/platform/PlatformConsole.tsx`; `apps/frontend/src/platform/platformApi.ts`; `apps/frontend/src/platform/platform-console.css` |
| Platform API uses `credentials: include`. | PASS | `apps/frontend/src/platform/platformApi.ts` |
| Keyboard focus, labels, minimum hit targets, color-independent status, and reduced-width tables are addressed. | PASS | `apps/frontend/src/styles.css`; `apps/frontend/src/design/gp05-tokens.css`; `apps/frontend/src/platform/platform-console.css` |
| Stored visual evidence covers normal/degraded/offline/recovery states without implying production deployment. | PASS | `deliverables/visual-acceptance/v3/evidence.jsonl`; `deliverables/platform-recovery/README.md` |

## Test / CI checklist

| Baseline command / gate | Status | Evidence / exit truth |
| --- | --- | --- |
| `pnpm check` | PASS | Local Windows run, exit 0; backend 682 passed with 4 platform-specific skips, frontend 69, build PASS. |
| `bash scripts/validate.sh` | PASS | Local run, exit 0. |
| `pnpm smoke:gp05` | PASS | Local run, exit 0; real backend process chain, four clients, `gp05.v1`. |
| `python scripts/test_recovery_evidence_templates.py -v` | PASS | Local run, exit 0; 11/11 passed. |
| Local PostgreSQL integration | NOT APPLICABLE | Intentionally not run: no G5 destructive DB reset authorization. This is a review execution boundary, not an accepted product limitation. |
| Exact-head PostgreSQL integration | PASS | [Actions run 32646133935](https://github.com/OasisSaber/Supersonic/actions/runs/32646133935), SHA `7e1ea06e52964b09c8368943236847525a7deccc`; `pnpm test:backend:integration` → `uv ... pytest apps/backend/integration_tests -q`; 61 passed in 4.62s, exit success. |
| Exact-head Ubuntu mandatory PostgreSQL path | PASS | CI job ran the real PostgreSQL integration; no silent skip of the mandatory path. |
| Windows-only skip: `apps/backend/tests/test_backup_restore_contract.py:1420` | NOT APPLICABLE | POSIX directory-permission semantics only; Windows platform skip. |
| Windows-only skip: `apps/backend/tests/test_backup_restore_contract.py:1784` | NOT APPLICABLE | Windows prevents replacing a retained open input file. |
| Windows-only skip: `apps/backend/tests/test_platform_audit_fallback.py:110` | NOT APPLICABLE | POSIX permission bits are not NTFS ACLs. |
| Windows-only skip: `apps/backend/tests/test_platform_audit_fallback.py:121` | NOT APPLICABLE | POSIX permission bits are not NTFS ACLs. |
| Recovery contract required-gate coverage | FINDING | `scripts/test_recovery_evidence_templates.py` is not invoked by `scripts/validate.sh`, `pnpm check`, or `.github/workflows/check.yml`; G5-CI-001. |
| Test quality: fail-closed/error/audit/revoke/CORS/token paths | PASS | `apps/backend/tests`; `apps/backend/integration_tests`; `apps/frontend/src/**/*.test.tsx`; exact-head CI evidence. |

## Dependency / License checklist

| Review checklist | Status | Evidence |
| --- | --- | --- |
| Python direct dependency inventory has declared range, lock version, purpose, license, and lifecycle. | PASS | [G5 Dependency Inventory](G5_DEPENDENCY_INVENTORY.md); `apps/backend/pyproject.toml`; `apps/backend/uv.lock` |
| Node direct dependency inventory has manifest range, lock/installed version, purpose, license, and lifecycle. | PASS | [G5 Dependency Inventory](G5_DEPENDENCY_INVENTORY.md); `package.json`; `apps/frontend/package.json`; `pnpm-lock.yaml` |
| `THIRD_PARTY_NOTICES.md`, README, and dependency docs are part of provenance review. | PASS | `THIRD_PARTY_NOTICES.md`; `README.md`; `docs/08-data-and-license-log.md` |
| `ultralytics` is absent and no CDN/runtime injection was found. | PASS | `package.json`; `apps/frontend/package.json`; `apps/backend/pyproject.toml`; `pnpm-lock.yaml`; `apps/backend/uv.lock` |
| Optional vision/LLM dependencies have complete license/log/notice provenance. | FINDING | `apps/backend/pyproject.toml`; `apps/backend/uv.lock`; `docs/08-data-and-license-log.md`; `THIRD_PARTY_NOTICES.md`; G5-LIC-001 |
| Model/font/image/icon/map asset provenance is bounded; future VehicleVision licensing remains separate. | PASS | `THIRD_PARTY_NOTICES.md`; `docs/08-data-and-license-log.md`; `docs/project/IMPLEMENTATION_ROADMAP.md` |

## Documentation truth checklist

| Review checklist | Status | Evidence / finding |
| --- | --- | --- |
| Project progress and roadmap accurately distinguish G4 complete from G5 incomplete. | PASS | `docs/project/PROJECT_PROGRESS.md`; `docs/project/IMPLEMENTATION_ROADMAP.md` |
| README current-state capability claims match reviewed G4 runtime. | FINDING | `README.md:26-35,69-71`; G5-DOC-001 |
| Architecture current-state persistence and boundary claims match runtime. | FINDING | `docs/architecture.md:25-29,82-88`; G5-DOC-001 |
| Development/setup current-state claims match runtime. | FINDING | `docs/development.md:22,48-67,84`; G5-DOC-001 |
| Recovery README distinguishes live close/revoked handshake and records actual checkpoint. | PASS | `deliverables/platform-recovery/README.md`; `deliverables/platform-recovery/acceptance.json` |
| Deployment/environment docs do not claim production deployment or distributed WS. | PASS | `docs/development.md`; `docs/architecture.md`; `apps/backend/app/platform/websocket_registry.py` |
| Recovery checkpoint is not confused with cockpit runtime restore. | PASS | `deliverables/platform-recovery/README.md`; `docs/project/PROJECT_PROGRESS.md` |
| G5 is not represented as complete/frozen by this publication. | PASS | `deliverables/g5-review/G5_FINDINGS_REPORT.md`; `deliverables/g5-review/G5_FREEZE_REPORT.md` |

## Resolution boundary

This matrix records the three Important review resolutions without changing runtime behavior:

1. The Architecture invariant set and all six review axes now have traceable status/evidence rows.
2. Direct Python and Node dependency provenance is recorded in [G5 Dependency Inventory](G5_DEPENDENCY_INVENTORY.md).
3. Test/CI rows record command exit truth, exact-head PostgreSQL evidence, and Windows-only skips.

No accepted limitation is granted. Existing low findings remain findings, the verdict remains
`CHANGES_REQUIRED`, and the 0/4/5/5 counts are unchanged.
