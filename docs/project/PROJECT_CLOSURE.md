# Supersonic Project Closure

- Closure date: 2026-09-04
- Repository: `OasisSaber/Supersonic`
- Lifecycle: `FROZEN / MAINTENANCE_ONLY`
- G5 quality state: `G5_FROZEN`
- G5 freeze decision head: `d0b2bafdeea9af69210b0640e5945abe34ffd630`
- Active graduation-design project: `OasisSaber/Pioneer`

## 1. Closure decision

Supersonic active product development ends on 2026-09-04.

The repository is retained as:

- historical engineering project;
- portfolio/reference implementation;
- record of G3/G4/G5 architecture, platform and quality work;
- source of reusable engineering lessons.

Closure does not invalidate or rewrite the G5 freeze.

## 2. Why active development ended

The graduation-design direction changed. The active project is now Pioneer, a separate desktop
task-assistant Agent interaction system.

Pioneer is a new product direction and repository. This Closure does not claim it is a code fork of
Supersonic.

## 3. Preserved completed scope

High-level completed scope includes:

- six cockpit endpoints;
- React + TypeScript frontend;
- FastAPI + WebSocket authoritative cockpit runtime;
- PostgreSQL-backed Platform users / Sessions / Audit;
- server-owned Principal/RBAC;
- Admin/session management;
- recovery tooling/evidence;
- GP22 design asset baseline;
- required CI and G5 review evidence.

Detailed claims remain governed by existing architecture and evidence.

## 4. Planned but not completed

The former roadmap included:

- real map / place search;
- VehicleVision;
- constrained AI voice;
- multi-display deployment orchestration;
- Web3D.

These are **not completed Supersonic features** and are no longer an active Supersonic roadmap.

## 5. Maintenance policy

Future work is normally limited to factual docs, security/privacy, license/provenance, repository
hygiene and serious evidence reproducibility repairs.

New product features require explicit project reactivation.

## 6. Evidence preservation

Do not delete/rewrite merely because the project closes:

- original G5 findings;
- remediation history;
- final re-review;
- freeze declaration;
- G4 recovery evidence;
- GP22 design baseline;
- historical roadmap/direction.

## 7. Lessons carried forward

See [PROJECT_LESSONS_LEARNED.md](./PROJECT_LESSONS_LEARNED.md).

The primary transferable output is engineering method, not Supersonic domain code.

## 8. Archive / tag

No GitHub Archive setting, tag or release is performed by this Closure PR.
Those remain separate human decisions.
