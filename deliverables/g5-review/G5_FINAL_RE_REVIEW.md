# G5 Final Re-Review Report

Review: [Issue #84](https://github.com/OasisSaber/Supersonic/issues/84) — fresh seven-axis
re-review of current `main`, executed as workflow steps 7–8 of the
original [G5 review Issue #65](https://github.com/OasisSaber/Supersonic/issues/65)
and required by the Low disposition record
([G5 Low Findings Disposition](G5_LOW_FINDINGS_DISPOSITION.md)).

- Review change: publication-only; no runtime, frontend, migration, recovery tooling, or finding fix is included.
- Baseline: `main@7e1ea06e52964b09c8368943236847525a7deccc` (original review baseline)
- Reviewed head: `main@6cfbe9f83f9d82bc2ff0afb523fbf1277817e993`
- Delta under re-review: `7e1ea06e..6cfbe9f8` — 8 commits, exactly the five approved
  remediation groups, the GP22 asset intake, and two records:
  - `21f1579` docs: publish G5 final review findings (#66)
  - `ec98f71` fix: close G5 platform WebSocket security findings (#69)
  - `9de5b2a` design: intake GP22 asset baseline (#70)
  - `9012739` fix: add durable attempted audit for admin mutations (#72)
  - `38700e6` fix(frontend): enforce authenticated and truthful cockpit state (#74)
  - `eb17d49` ci: require recovery evidence contract (#76)
  - `ca58b7c` docs: synchronize current platform state (#78)
  - `6cfbe9f` docs: record G5 low finding dispositions (#83)
- Original report (historical, preserved as published):
  [G5 Findings Report](G5_FINDINGS_REPORT.md) / [G5 Freeze Report](G5_FREEZE_REPORT.md)

## Remediation verification (4 High + 5 Medium)

Every original Critical/High/Medium finding was re-verified against the reviewed head
code and its required regression evidence. None is claimed fixed without matching
in-repo tests or recorded proof.

| Finding | Fix | Re-review evidence at `6cfbe9f8` | Result |
| --- | --- | --- | --- |
| G5-SEC-001 (High) — established WS ignores absolute expiry | PR #69 | `apps/backend/app/api/cockpit_router.py:187-237`: established loop runs inside `asyncio.timeout_at` bounded by `identity.expires_at`; expiry closes with 1008 and cleans up; zero remaining TTL cannot send. Tests: `test_platform_router_wiring.py` `test_established_platform_websocket_stops_before_post_expiry_snapshot`, `test_two_established_connections_expire_and_unregister`, `test_session_expiry_cancels_snapshot_already_in_send`, plus `test_platform_websocket_does_not_misreport_inner_timeout_as_session_expiry`. | FIXED |
| G5-SEC-002 (High) — durable revoke does not block sends when close fails | PR #69 | `apps/backend/app/platform/websocket_registry.py:52-65`: `close_all` marks the session blocked and cancels in-flight sends before any close attempt; failed closes keep connections tombstoned and non-sendable. Sends go through `send_if_allowed` (`:67-92`). Tests: `test_websocket_registry.py:78,113,142,166,176,199`; `test_platform_router_wiring.py` `test_failed_revoke_close_blocks_later_snapshot_until_explicit_retry`, `test_failed_revoke_close_cancels_snapshot_already_in_send`. | FIXED |
| G5-AUD-001 (High) — admin mutations omit durable `attempted` pre-audit | PR #72 | `apps/backend/app/platform/admin.py:505-540`: `_commit_attempted` commits the `ATTEMPTED` audit in its own UoW before any mutation and raises `AuditUnavailable` on failure, so the mutation never starts; `change_role`/`set_disabled`/`revoke_session` follow this order (`admin.py:179-190,297,410`); failures are recorded as linked error outcomes (`_record_failed_outcome`). Tests: `test_platform_admin_service.py:324` ordering, `:356` attempted-commit failure blocks mutation, `:384` mutation failure keeps attempted and records outcome, `:744` commit failure never calls revoke callback. | FIXED |
| G5-FE-001 (High) — cockpit command fetch omits credentials | PR #74 | `apps/frontend/src/lib/useCockpitCommand.ts` sends `credentials: 'include'` on the cross-origin command fetch. Component contract tests pass in the required gate. | FIXED |
| G5-SEC-003 (Medium) — cockpit command mutations lack exact Origin enforcement | PR #69 | `apps/backend/app/api/cockpit_router.py:71-76`: exact `platform_ui_origin` gate runs before cookie/session resolution on `POST /api/v1/commands/{endpoint}`; `ExactOriginPolicy.allows` is strict equality (`security.py`). Parametrized variants all rejected before session resolution: missing, `null`, suffix `.evil`, prefix-path confusion, path-bearing, untrusted host (`test_platform_router_wiring.py:285-296`). | FIXED |
| G5-FE-002 (Medium) — null-snapshot UI invents state and leaves commands enabled | PR #74 | Cluster renders `—`/“等待权威状态” and an explicit route EmptyState; HUD renders a dedicated null EmptyState without lane/navigation/risk text; Center gates input, submit, and risk mutations on `hasSnapshot`; Passenger disables media/privacy/suggestion on `!hasSnapshot`; Control computes `commandsDisabled` including `snapshot === null`; Overview shows previews only with a snapshot. Tests: `CockpitScreen.test.tsx` “does not invent …”, “disables … before the first authoritative snapshot” for all four business screens. | FIXED |
| G5-FE-003 (Medium) — unknown cockpit paths silently become Overview | PR #74 | `apps/frontend/src/App.tsx`: `endpointFromPath` admits only the six declared endpoint paths; anything else renders the `role="alert"` route-boundary panel and never mounts `useCockpitSnapshot`, so no snapshot WebSocket starts. Tests: `App.test.tsx` route boundary suite. | FIXED |
| G5-CI-001 (Medium) — recovery evidence contract outside required CI | PR #76 | `scripts/validate.sh` runs `scripts/test_recovery_evidence_templates.py` under `set -euo pipefail`, so a contract failure fails the authoritative validation and the required GitHub `check` job (step “Validate”). Negative proof recorded in PR #76: a controlled invalid example made `scripts/validate.sh` exit 1 post-fix (exit 0 pre-fix), fixture restored byte-for-byte. | FIXED |
| G5-DOC-001 (Medium) — current docs describe pre-G4 facts | PR #78 | Root `README.md`, `docs/architecture.md`, `docs/development.md` now state the G4 platform truth: PostgreSQL-backed users/Platform Session/RBAC/Audit wired via `DATABASE_URL`, `/platform` surfaces, single-process revoke propagation boundary, and mock-source labeling; no stale “unimplemented platform” claims remain. Remaining “Conditional” wording in `docs/development.md` describes future conditional scope, not current-state denial. Spot-checked against composition, configuration, and phase records. | FIXED |

## Low disposition verification

All five original Low findings have exactly one approved disposition recorded in
[G5 Low Findings Disposition](G5_LOW_FINDINGS_DISPOSITION.md) (merged via PR #83):

| Finding | Disposition | Re-review check |
| --- | --- | --- |
| G5-ARCH-001 | `BACKLOG` | Open follow-up [Issue #80](https://github.com/OasisSaber/Supersonic/issues/80); composed `PlatformCommandGateway`/`AuditEvent` remains the only runtime authority; legacy package exports still present and must not gain new callers. Consistent with the record. |
| G5-ARCH-002 | `ACCEPTED_LIMITATION` | `control_enabled` remains enforced at the HTTP adapter boundary (`cockpit_router.py:77-82`); single-adapter topology unchanged. Consistent. |
| G5-REC-001 | `ACCEPTED_LIMITATION` | Backup publication boundary unchanged; restore preflight still fail-closed against orphan dumps; operator guidance recorded. Consistent. |
| G5-REC-002 | `BACKLOG` | Open follow-up [Issue #81](https://github.com/OasisSaber/Supersonic/issues/81); acceptance record unchanged (no evidence content edited in this delta). Consistent. |
| G5-LIC-001 | `BACKLOG` | Open follow-up [Issue #82](https://github.com/OasisSaber/Supersonic/issues/82); [G5 Dependency Inventory](G5_DEPENDENCY_INVENTORY.md) remains the reviewed baseline. Consistent. |

The freeze gate permits unresolved Low findings only with explicit approved dispositions;
this input gate is satisfied.

## New findings from this re-review

0 Critical / 0 High / 0 Medium / 0 new Low. The GP22 asset intake (#70) touched only
`deliverables/design-baselines/gp22/**` and `docs/design/GP22_SOURCE_MANIFEST.md`
(no runtime surface); the two docs records (#78, #83) are publication-only.

## Axis verdicts

| Axis | Verdict | Basis |
| --- | --- | --- |
| Architecture | PASS (with recorded BACKLOG #80 and accepted limitation G5-ARCH-002) | composed runtime is the sole authority; legacy exports quarantined by operator guidance |
| Security/Auth | PASS | G5-SEC-001/002/003 and G5-FE-001 fixed with required regression evidence |
| Persistence/Audit/Recovery | PASS | G5-AUD-001 fixed; recovery contract in required gate; REC-001/002 dispositioned |
| Frontend/Visual | PASS | G5-FE-002/003 fixed; null-snapshot truth and route boundary tests in required gate |
| Test/CI Validity | PASS | G5-CI-001 fixed; recovery contract failure now fails `validate.sh` and required CI |
| Dependencies/License | PASS WITH LOW (BACKLOG recorded as Issue #82) | unchanged since baseline; no incompatible current distribution |
| Documentation Truth | PASS | G5-DOC-001 fixed; disposition record published |

## Exact validation evidence at reviewed head

- Local `bash scripts/validate.sh` (working copy identical to `6cfbe9f8`): PASS —
  validator suites, Markdown links, YAML, shell modes, then `pnpm check`:
  Ruff/ESLint PASS; backend **724 passed, 4 skipped**; frontend **85 passed**; production build PASS.
- Exact-head GitHub Actions `check` run [`33299616699`](https://github.com/OasisSaber/Supersonic/actions/runs/33299616699)
  on `6cfbe9f8`: success — Validate PASS, PostgreSQL integration PASS, GP05 runtime smoke PASS (four endpoints).
- Sensitive-pattern scan over the re-review delta: no hardcoded secret patterns; the
  delta adds only code, tests, docs, and approved GP22 design assets.
- No destructive local PostgreSQL reset was run; exact-head CI supplies the real
  PostgreSQL integration evidence.

## Freeze invariants (re-checked)

| Invariant | Verdict |
| --- | --- |
| CockpitService sole realtime authority | PASS |
| `gp05.v1` no unrecorded drift | PASS |
| Server-resolved Principal, incl. established WS expiry and revoke-send fail-closed | PASS |
| RolePolicy AND EndpointPolicy | PASS |
| PostgreSQL non-realtime authority | PASS |
| Audit integrity incl. management `attempted` pre-audit | PASS |
| Recovery provenance | PASS (REC-001/002 bounded by recorded dispositions) |
| Docs truth | PASS |
| No scope creep in the re-review change | PASS (publication-only) |

## Final verdict

`FREEZE_READY`

This verdict states that the seven-axis review gate now passes with all High/Medium
findings fixed and all Low findings dispositioned. It does not itself declare the G5
freeze: the freeze declaration is a human decision taken after this publication is
merged. Issues #80, #81, and #82 remain open, separately authorized backlog work and
do not block the verdict.
