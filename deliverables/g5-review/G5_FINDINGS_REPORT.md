# G5 Findings Report

Review: [Issue #65](https://github.com/OasisSaber/Supersonic/issues/65)

Baseline: `main@7e1ea06e52964b09c8368943236847525a7deccc`
Reviewed head: `7e1ea06e52964b09c8368943236847525a7deccc`
Date: 2026-08-24
Status: Issue #65 review-only publication; no fixes are included and G5 is not frozen.

## Summary

Traceability artifacts: [G5 Review Matrix](G5_REVIEW_MATRIX.md) and
[G5 Dependency Inventory](G5_DEPENDENCY_INVENTORY.md).

| Severity | Count |
| --- | ---: |
| Critical | 0 |
| High | 4 |
| Medium | 5 |
| Low | 5 |
| Info | 0 |

## High findings

### G5-SEC-001 — Established WebSocket ignores absolute Platform Session expiry

Severity: High

Evidence: `apps/backend/app/api/cockpit_router.py:175-203` resolves once at handshake and runs an unbounded send/receive loop without using `identity.expires_at`; the approved architecture requires expiry to stop sending (`docs/design/2026-08-09-g3-platform-architecture-design.md:286-294`).

Broken invariant: expired Platform Sessions must fail closed for established WebSockets.

Impact: a connection may continue receiving cockpit snapshots after its absolute expiry.

Minimal fix scope: enforce a bounded expiry deadline in the established connection loop and close/cleanup at expiry.

Required validation: short-TTL integration test proving no snapshot is sent after expiry.

Disposition: unresolved; separate Security Fix Issue required.

### G5-SEC-002 — Durable revoke does not block sends when WebSocket close propagation fails

Severity: High

Evidence: `apps/backend/app/platform/websocket_registry.py:42-48` only attempts close and removes successful connections; `apps/backend/app/api/cockpit_router.py:185-203` never checks a blocked/revoked registry state. The design requires mark-not-sendable before best-effort close (`docs/design/2026-08-09-g3-platform-architecture-design.md:274-281`).

Broken invariant: a durably revoked session must stop receiving even when a close frame fails.

Impact: a revoked connection can continue receiving snapshots during degraded propagation.

Minimal fix scope: registry-level blocked state checked by the send loop; mark blocked before close attempts while retaining retry bookkeeping.

Required validation: injected close-hook failure must still stop subsequent snapshot delivery.

Disposition: unresolved; group with Security Fix Issue.

### G5-AUD-001 — Admin mutations omit durable `attempted` pre-audit

Severity: High

Evidence: `apps/backend/app/platform/admin.py:165-201,224-261,282-309` changes state, records only `succeeded`, and commits once. ADR 0001 requires management `attempted` to commit before mutation (`docs/adr/0001-postgresql-platform-boundary.md:30-34`).

Broken invariant: no management mutation may begin without a durable primary attempted fact.

Impact: process failure can leave a security mutation without durable intent provenance.

Minimal fix scope: separate attempted-audit UoW/commit before mutation; block mutation when that commit fails; keep outcome semantics explicit.

Required validation: real PostgreSQL ordering, attempted-commit failure, mutation rollback/no-start, and outcome tests.

Disposition: unresolved; separate Audit Fix Issue required.

### G5-FE-001 — Cockpit command fetch omits Platform credentials

Severity: High

Evidence: `apps/frontend/src/lib/useCockpitCommand.ts:23-35` omits `credentials: 'include'`; default Vite `5173` to FastAPI `8000` is cross-origin. The backend requires the Platform cookie in platform mode (`apps/backend/app/api/cockpit_router.py:98-108`).

Broken invariant: Center/Passenger/Control mutations must authenticate with the server-resolved Platform Session.

Impact: authenticated cockpit users receive 401 for real platform-mode commands.

Minimal fix scope: include credentials and test exact fetch options/live cross-origin command flow.

Required validation: component contract plus restored/local platform-mode browser acceptance.

Disposition: unresolved; separate Frontend Truth Fix Issue required.

## Medium findings

### G5-SEC-003 — Cockpit command mutations lack exact Origin enforcement

Severity: Medium

Evidence: `apps/backend/app/api/cockpit_router.py:59-79,98-123` accepts cookie-authenticated POST commands without checking Origin, unlike other platform mutations.

Broken invariant: every cookie-authenticated mutation must enforce the exact configured UI Origin before resolving or using the session.

Impact: the CSRF boundary promised for all cookie-authenticated mutations is incomplete.

Minimal fix scope: exact `platform_ui_origin` gate before session resolution; test missing/null/suffix/path variants and exact success.

Required validation: focused HTTP tests for missing, `null`, suffix-confusable, path-bearing, and exact Origin values, plus the backend regression suite.

Disposition: unresolved; group with Security Fix Issue.

### G5-FE-002 — Null-snapshot UI invents state and leaves commands enabled

Severity: Medium

Evidence: Cluster/HUD/Overview use fallback strings such as seatbelt-unfastened, keep-lane, `paused`, `idle`; Center/Passenger command controls remain active without a snapshot (`apps/frontend/src/components/screens/ClusterScreen.tsx:22-29`, `apps/frontend/src/components/screens/HudScreen.tsx:21-30`, `apps/frontend/src/components/screens/OverviewScreen.tsx:53-68`, `apps/frontend/src/components/screens/CenterScreen.tsx:48-72`, `apps/frontend/src/components/screens/PassengerScreen.tsx:36-93`).

Broken invariant: the UI must not present client-invented cockpit truth or permit business mutations before the first authoritative snapshot.

Impact: loading/offline state appears as authoritative driving/media/navigation truth and permits commands before authoritative state exists.

Minimal fix scope: explicit unavailable/loading rendering and disable business mutations until a snapshot is present.

Required validation: endpoint component tests for null snapshots, disabled command controls, and absence of inferred driving/media/navigation values; then frontend test/build and browser acceptance.

Disposition: unresolved; group with Frontend Truth Fix Issue.

### G5-FE-003 — Unknown cockpit paths silently become Overview

Severity: Medium

Evidence: `apps/frontend/src/App.tsx:7-10` maps every non-endpoint path to `overview`.

Broken invariant: only the six declared cockpit endpoint routes may start a matching endpoint snapshot connection; invalid routes must remain bounded and explicit.

Impact: misspelled or invalid routes hide deployment/configuration errors and connect with the wrong endpoint identity.

Minimal fix scope: explicit route validation and bounded route-error state without starting Overview snapshot.

Required validation: unknown-path routing tests proving an error state is rendered and no Overview snapshot/WebSocket startup occurs.

Disposition: unresolved; group with Frontend Truth Fix Issue.

### G5-CI-001 — Recovery evidence contract is outside required CI

Severity: Medium

Evidence: `scripts/test_recovery_evidence_templates.py` is not invoked by `scripts/validate.sh`, `pnpm check`, or `.github/workflows/check.yml`.

Broken invariant: every mandatory recovery evidence contract must be enforced by the required validation/CI path rather than an optional manual command.

Impact: recovery checkpoint/status/reference/sanitization evidence can regress while required CI stays green.

Minimal fix scope: add the contract test to `validate.sh` or a required CI step.

Required validation: prove an intentionally invalid recovery fixture makes the required gate fail, restore the fixture, then run the focused contract test, `bash scripts/validate.sh`, and the required CI workflow.

Disposition: unresolved; separate CI Fix Issue required.

### G5-DOC-001 — Current docs still describe pre-G4 facts

Severity: Medium

Evidence: root `README.md:26-35,69-71` says PostgreSQL identity/RBAC/Audit/recovery are unimplemented/future; `docs/architecture.md:25-29,82-88` calls persistence conditional; `docs/development.md:22,48-67,84` says single-user/no accounts and DB not wired. The recovery acceptance template's `pending`/`not_run` state was separately reviewed as intentional template state and is not part of this finding.

Broken invariant: current-state contributor and evaluator documentation must describe capabilities and phase status that match the reviewed `main` runtime.

Impact: contributors and evaluators are directed to an architecture and phase state contradicted by current main.

Minimal fix scope: synchronize only the current-state facts in root `README.md`, `docs/architecture.md`, and `docs/development.md`; preserve the intentional recovery template state unchanged.

Required validation: link/path checks, stale-term scan, and manual cross-check of README/architecture/development claims against composition, configuration, and current project phase records.

Disposition: unresolved; separate Docs Truth Fix Issue required.

## Low findings / proposed dispositions

### G5-ARCH-001 — Legacy gateway/Audit runtime remains canonically exported

Severity: Low

Evidence: `apps/backend/app/platform/__init__.py:9-19` exports `AuthorizedCockpitGateway`/`AuditRecord` from `apps/backend/app/platform/gateway.py` and `apps/backend/app/platform/models.py`; they coexist with the composed `PlatformCommandGateway`/`AuditEvent`.

Broken invariant: the composed Platform runtime should have one canonical command gateway and Audit model; compatibility code must not remain an ambiguous package-level authority.

Impact: future callers can import and extend the obsolete runtime, recreating split authorization/Audit behavior.

Minimal fix scope: remove the obsolete exports/runtime or isolate them behind an explicitly deprecated compatibility module without changing `gp05.v1` behavior.

Required validation: repository import scan plus focused gateway tests and the full backend suite.

Disposition: proposed backlog removal/deprecation issue; current composition uses only the new runtime.

### G5-ARCH-002 — Router retains the `control_enabled` policy decision

Severity: Low

Evidence: `apps/backend/app/api/cockpit_router.py:68-73` decides `control_disabled` before the gateway.

Broken invariant: transport routers should adapt/authenticate/map errors rather than own reusable business authorization policy.

Impact: another command adapter could bypass or diverge from the HTTP-only control switch.

Minimal fix scope: consolidate the switch in the existing command policy/gateway without broad router refactoring.

Required validation: focused parity tests across all command entry points plus backend regression.

Disposition: proposed accepted local-adapter limitation or backlog consolidation after security fixes.

### G5-REC-001 — Hard termination can leave an orphan dump before manifest publication

Severity: Low

Evidence: `scripts/platform_backup.py:435-440` publishes dump then manifest. Exception cleanup is strong, and an orphan dump is not a valid/false-success pair, but abrupt process death requires manual cleanup before retry.

Broken invariant: a backup publication should have an explicit, operator-detectable incomplete-artifact recovery story across abrupt termination boundaries.

Impact: a hard kill between publications can occupy the final dump path without its manifest and block a clean retry, though it cannot be mistaken for a valid pair.

Minimal fix scope: document orphan cleanup or introduce a bounded bundle/commit marker protocol without weakening checksum and restore preflight.

Required validation: publication-boundary failure injection or kill test proving incomplete output is detected and safely recoverable.

Disposition: proposed accepted limitation documented in recovery operator guidance or backlog bundle-publication design.

### G5-REC-002 — Some application acceptance items self-reference the report

Severity: Low

Evidence: `deliverables/platform-recovery/acceptance.json` points WebSocket/GP05 evidence to itself; public Issue/PR rehearsal records and the strict manifest provide external context, but the repository reference alone is weak.

Broken invariant: recovery claims should be traceable to bounded, independently reviewable sanitized evidence rather than only to the claim-bearing record itself.

Impact: future repository-only reviewers cannot independently distinguish those two checks from self-attestation, despite the public rehearsal context.

Minimal fix scope: define a sanitized summary/provenance reference policy for these checks without committing raw logs, secrets, dumps, or private payloads.

Required validation: evidence-contract tests for non-self references plus manual public-checkpoint traceability review.

Disposition: proposed accepted limitation with explicit link/provenance policy, or future sanitized summary artifact.

### G5-LIC-001 — Direct/optional dependency provenance records are incomplete

Severity: Low

Evidence: Direct and optional dependencies are declared/locked, while `docs/08-data-and-license-log.md` has missing versions/entries and `THIRD_PARTY_NOTICES.md` does not classify them. `pwdlib-0.3.0.dist-info/licenses/LICENSE` is MIT, but its installed metadata License/License-Expression fields are undeclared; optional OpenCV/MediaPipe/OpenAI extras remain not currently distributed.

Broken invariant: declared direct/optional dependencies need traceable version, source, license, and distribution-status documentation.

Impact: direct dependency notices and future optional-extra enablement could lack a reviewable provenance trail; the current optional extras are not distributed and no incompatible current distribution was found.

Minimal fix scope: synchronize the license/data log and notices with the direct dependency inventory and lockfile, record `pwdlib`'s bundled MIT license plus undeclared metadata fields, and clearly identify optional/non-distributed extras.

Required validation: manifest/lock/license cross-check and notices scan; no runtime dependency upgrade.

Disposition: proposed fix with Docs Truth issue; no incompatible current distribution was found.

## Axis verdicts

- Architecture: FINDINGS (Low; security findings affect runtime boundary)
- Security/Auth: CHANGES_REQUIRED
- Persistence/Audit/Recovery: CHANGES_REQUIRED
- Frontend/Visual: CHANGES_REQUIRED
- Test/CI: CHANGES_REQUIRED
- Dependencies/License: PASS WITH LOW DOCUMENTATION FINDING
- Documentation Truth: CHANGES_REQUIRED

## Exact validation evidence

- Pack verification: PASS, 31 files.
- Exact baseline clone: clean HEAD `7e1ea06e...`.
- Local `pnpm check`: PASS (Windows backend 682 passed / 4 platform-specific skips; frontend 69; build PASS).
- Local `bash scripts/validate.sh`: PASS.
- Local GP05: PASS, `gp05.v1`, four clients.
- Local recovery contract: 11/11 PASS.
- Exact-head GitHub Actions push run [`32646133935`](https://github.com/OasisSaber/Supersonic/actions/runs/32646133935): PASS.
- CI PostgreSQL integration: 61/61 PASS.
- CI GP05 real-process step: PASS.
- Sensitive scan hits: manually classified as examples/tests/ephemeral CI values; no real credential found.
- Local destructive PostgreSQL reset was not run because this G5 task has no explicit database authorization; exact-head CI supplies real PostgreSQL evidence.

## Review tooling limitations (not findings)

Two defects in temporary review helpers were observed and are recorded transparently; neither is included in the Critical/High/Medium/Low counts:

- `g5_freeze_diff_guard.py` uses `f"{args.baseline}^{commit}"` and the analogous head expression, which raises `NameError`. This review therefore does not use that helper's assertion as freeze evidence.
- `g5_inventory.py` uses non-`-z` `ls-files` output, so paths containing quotes can be assigned the wrong extension. Inventory results were manually reviewed; this helper defect is not a repository finding.

## Current verdict

`CHANGES_REQUIRED`
