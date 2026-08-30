# G5 Low Findings Disposition Record

> Decision record for [Issue #79](https://github.com/OasisSaber/Supersonic/issues/79).
> This record does not implement a finding fix and does not declare G5 frozen.

## Baseline and gate

- disposition baseline: `main@ca58b7c15dcd9c8b508c90e26ab63eaaf7924d34`
- original review: [G5 Findings Report](G5_FINDINGS_REPORT.md)
- allowed values: `FIXED`, `BACKLOG`, `ACCEPTED_LIMITATION`
- current G5 verdict: `CHANGES_REQUIRED`; final re-review has not started

## G5-ARCH-001

**Disposition:** `BACKLOG`

The composed runtime uses `PlatformCommandGateway` and `AuditEvent`, but legacy
`AuthorizedCockpitGateway` / `AuditRecord` package exports remain an ambiguous future import
surface. No runtime cleanup is claimed by this record.

- Follow-up: [Issue #80 — deprecate legacy gateway and Audit exports](https://github.com/OasisSaber/Supersonic/issues/80)
- Operator guidance: new code must use the composed `PlatformCommandGateway` / `AuditEvent`
  path and must not add callers of the legacy package exports; Issue #80 needs separate
  authorization before cleanup.
- Freeze risk: bounded for the current single composed runtime because the legacy objects are not
  its authority; future callers could still recreate split authorization or Audit behavior until
  the backlog is completed.

## G5-ARCH-002

**Disposition:** `ACCEPTED_LIMITATION`

The current local prototype has one supported cockpit command transport composition, and
`control_enabled` remains enforced in the HTTP Router before delegation. Keeping this decision at
the adapter boundary is accepted for that single-adapter topology; it is not a reusable policy
guarantee.

- Follow-up trigger: any second command adapter or command-entry refactor must first consolidate
  the switch in the shared command policy/gateway and add parity tests.
- Operator guidance: treat `control_enabled` only as the current HTTP adapter's local Control
  switch; it does not replace Principal/RBAC, Origin, Session, or endpoint-policy checks.
- Freeze risk: accepted as Low because the present route is covered and Control remains explicitly
  disabled by default; a future adapter must not inherit this acceptance without review.

## G5-REC-001

**Disposition:** `ACCEPTED_LIMITATION`

A hard process termination between dump publication and manifest publication can leave a final
dump without its adjacent manifest. Restore preflight requires the manifest and validates its dump
checksum and repository head, so the orphan cannot be mistaken for a valid backup pair; it can
still block a clean retry at the same output path.

### Operator guidance

1. Treat a dump with a missing, unreadable, or non-matching adjacent manifest as incomplete; do not
   restore it and do not fabricate a manifest.
2. Verify that the dump and manifest paths are the exact operator-selected backup output, outside
   the repository, before cleanup.
3. Remove only the incomplete pair at that verified output path, then rerun the backup to a clean
   destination and require normal manifest/checksum preflight before restore.

- Follow-up trigger: if unattended backup publication is introduced, replace this manual boundary
  with a separately authorized bundle/commit-marker design and failure-injection validation.
- Freeze risk: accepted as Low because incomplete output fails closed and cannot pass restore
  preflight; manual cleanup after abrupt termination remains required.

## G5-REC-002

**Disposition:** `BACKLOG`

The current recovery acceptance record keeps public rehearsal context and sanitized aggregate
results, but its WebSocket and GP05 items still point to the claim-bearing report itself. This is
truthful but weak for repository-only provenance review; no evidence content is changed here.

- Follow-up: [Issue #81 — replace self-referential acceptance evidence](https://github.com/OasisSaber/Supersonic/issues/81)
- Operator guidance: a future evidence refresh must use a bounded, repository-relative, sanitized
  summary/reference and must leave the intentional recovery example `pending` / `not_run` states
  unchanged unless separately authorized.
- Freeze risk: bounded as a documented provenance limitation; the backlog must preserve
  sanitization and must not introduce dumps, credentials, cookies, raw sensitive logs, or private
  payloads.

## G5-LIC-001

**Disposition:** `BACKLOG`

Direct and optional dependencies are declared and locked, and the review found no incompatible
current distribution. Their version/source/license/distribution-status documentation remains
incomplete, including `pwdlib` metadata context and optional, non-distributed OpenCV, MediaPipe,
and OpenAI extras. No license record is declared complete here.

- Follow-up: [Issue #82 — complete dependency provenance records](https://github.com/OasisSaber/Supersonic/issues/82)
- Operator guidance: complete the version, source, license-text, and distribution-status cross-check
  before enabling or distributing optional extras; Issue #82 needs separate documentation scope.
- Freeze risk: bounded for the current non-distribution posture; provenance review is required
  before optional extras are enabled or distributed.

## Disposition gate

| Finding | Disposition | Follow-up |
| --- | --- | --- |
| `G5-ARCH-001` | `BACKLOG` | [#80](https://github.com/OasisSaber/Supersonic/issues/80) |
| `G5-ARCH-002` | `ACCEPTED_LIMITATION` | second-adapter trigger recorded above |
| `G5-REC-001` | `ACCEPTED_LIMITATION` | unattended-publication trigger recorded above |
| `G5-REC-002` | `BACKLOG` | [#81](https://github.com/OasisSaber/Supersonic/issues/81) |
| `G5-LIC-001` | `BACKLOG` | [#82](https://github.com/OasisSaber/Supersonic/issues/82) |

All five original Low findings have exactly one allowed disposition and none remains without a
decision.
This satisfies only the Low-disposition input to the final G5 re-review. The authoritative verdict
remains `CHANGES_REQUIRED` until a fresh seven-axis review determines otherwise.
