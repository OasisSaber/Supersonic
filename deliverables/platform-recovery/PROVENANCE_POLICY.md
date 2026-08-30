# Recovery evidence provenance and reference policy

> Decision record for [Issue #81](https://github.com/OasisSaber/Supersonic/issues/81)
> (`G5-REC-002`, disposition `BACKLOG` applied by separately authorized work).
> This policy does not change the recovery checkpoint, the runtime, or the
> intentional `pending` / `not_run` example state.

## Problem

`acceptance.json` originally pointed the `webSocketRevoke` and `gp05Smoke`
acceptance items at `acceptance.json` itself. The record is truthful, but a
repository-only reviewer could not distinguish those two claims from
self-attestation. Acceptance claims must be traceable to bounded, independently
reviewable sanitized evidence instead of only to the claim-bearing record.

## Reference kinds

An acceptance claim item may reference only the following kinds, individually or
together:

1. A repository-relative sanitized file that exists in the repository (for
   example a bounded JSON summary or one of the approved screenshots).
2. A repository-relative test, integration-suite, or script path whose required
   validation run covers the claim.
3. A required-CI check identified by its exact step name and a numeric GitHub
   Actions run identifier (no URLs, no run-scoped artifacts).
4. A public pull-request or issue number that records the original rehearsal
   context.

## Non-self rule

- `persistence` and `applicationAcceptance` items in `acceptance.json` must not
  use `acceptance.json` itself as their `evidenceReference`.
- `recheck-provenance.json` must not reference `acceptance.json` in any
  reference field.
- The top-level `evidence.reportReference` of `acceptance.json` stays pointed at
  the record itself: it is the record's identity pointer, not acceptance
  evidence. It must not be cited as proof of a claim.
- The evidence-contract test in `scripts/test_recovery_evidence_templates.py`
  enforces the non-self rule so it cannot silently regress.

## Sanitization boundary (unchanged and binding)

Never record or reference passwords, tokens, cookies, token digests, DSNs,
host/user details, private payloads, raw stderr or logs, absolute local paths,
SQL exports, or database dumps. Screenshots contain synthetic identities only.
The `.example.json` files intentionally remain `pending` / `not_run` templates;
they are not proof that a rehearsal occurred.

## Evidence refresh gate

Any future evidence refresh or change to this policy requires separate explicit
authorization, must keep the example templates unchanged, and must not commit
dumps, credentials, cookies, raw sensitive logs, or private payloads.
