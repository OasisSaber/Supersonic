# Supersonic — Project Lessons Learned

## Purpose

This retrospective records two categories of learning:

1. long-running collaboration with LLMs, Agents and coding Harnesses;
2. software-engineering experience gained from the Supersonic technology stack.

It is not a model leaderboard and does not claim that any one model authored a particular subsystem.

---

# 1. Agent / LLM / Harness Collaboration

## 1.1 LLM, Agent and Harness are different layers

The project gradually separated three concepts:

- **LLM**: the reasoning/generation model;
- **Harness**: the execution environment exposing repository, terminal, files, GitHub, context, tools
  and session state;
- **Agent**: the working unit formed by model + Harness + prompt + tools + authority + current state.

The practical lesson was that long-running engineering reliability depends on all three layers.

A strong model with weak context, poor repository state or vague authority can still produce unreliable
work. A bounded task with good tools and validation can make a less expensive model productive.

## 1.2 Workflow evolved from prompt-driven coding to governed delivery

Early collaboration was close to:

```text
human request
→ Agent reads code
→ Agent modifies
→ output appears to work
```

As the repository grew, recurring problems appeared:

- scope expansion;
- stale assumptions about `main`;
- different Agents holding different project models;
- polluted contexts;
- architecture decisions mixed into implementation;
- “tests passed” treated as equivalent to system correctness;
- handoff problems between sessions/worktrees.

The later workflow became:

```text
exact baseline
→ Issue / explicit task source
→ invariants
→ bounded scope
→ implementation
→ focused validation
→ full validation
→ independent review
→ PR
→ human merge gate
```

## 1.3 Task asset packs became context engineering

Complex phases increasingly used structured packs containing:

- baseline facts;
- finding IDs;
- architecture invariants;
- implementation constraints;
- validation matrices;
- adversarial cases;
- Agent prompts;
- PR templates;
- helper guards.

The pack never replaced repository inspection. It compressed prior reasoning into an auditable,
reusable task boundary.

This was more reliable than reconstructing project context from long chat history each time.

## 1.4 Exact project state matters more than Agent confidence

A repeated risk was stale world state.

Before implementation, the Agent increasingly had to resolve:

```text
current main
current Issue
current PR
current CI
current docs
current task baseline
```

Core lesson:

> Resolve project facts before reasoning about changes.

An Agent can understand code correctly and still create an invalid change if its baseline is wrong.

## 1.5 Single Delivery Owner is more reliable than uncontrolled multi-Agent editing

Parallel Agents are useful for research and review, but concurrent write ownership introduces ambiguity.

A more reliable pattern:

```text
Human
  ↓
Single Delivery Agent
  ├─ Research reviewer
  ├─ Security reviewer
  ├─ Spec reviewer
  └─ Test reviewer
```

Only one worker owns the task change, final diff and PR. Other Agents are preferably read-only.

This reduces conflicting edits, mismatched baselines, duplicated fixes and unclear responsibility.

## 1.6 Builder and Reviewer are different roles

Even when powered by similar models, building and reviewing should be separate tasks.

The G5 review showed this clearly. A fresh review identified problems ordinary implementation work had
not forced into view, including:

- established WebSocket expiry behavior;
- revoke versus failed close propagation;
- durable attempted Audit ordering;
- frontend command credentials;
- client-invented truth before an authoritative snapshot;
- invalid route fallback;
- recovery evidence missing from required CI;
- stale current-state documentation.

The useful distinction:

> A builder asks “how do I make this work?”
> A reviewer asks “under what conditions is this claim false?”

## 1.7 Agent “done” is a hypothesis until external evidence confirms it

The project evolved toward an evidence chain:

```text
implementation
→ focused tests
→ full tests
→ real integration
→ real-process smoke
→ diff review
→ independent CodeReview
→ CI
→ human merge
```

For recovery, no Agent statement could substitute for real `pg_dump → pg_restore`.

For WebSocket lifecycle, static reasoning alone could not substitute for integration/runtime evidence.

For CI, merely adding a command was insufficient; negative proof had to show invalid evidence actually
made the required gate fail.

## 1.8 Human-in-the-loop is most valuable at irreversible decisions

Human approval was most valuable for:

- scope;
- architecture;
- merge;
- freeze;
- release;
- destructive/external operations.

It was less useful to request approval for every harmless local command.

The final G5 flow made this explicit:

```text
Agent review verdict = FREEZE_READY
```

did not itself freeze the project. The human made the freeze decision and the repository recorded it.

## 1.9 Harness quality is engineering infrastructure

A coding Harness is not merely a chat UI. Useful capabilities include:

- repository-aware context;
- terminal execution;
- tool calls;
- VCS/worktree/change ownership;
- GitHub integration;
- CI feedback;
- persistent sessions;
- reviewer/subagent support;
- reliable model/provider configuration.

The project also reinforced a general operational rule:

> Prefer observed runtime/configuration evidence over labels presented by a Harness UI.

## 1.10 Context hygiene is a first-class engineering problem

Long-running Agent development introduced context debt.

Mitigation included:

- canonical project docs;
- exact baselines;
- narrow Issues;
- one change per task;
- short-lived bookmarks/worktrees;
- task packs;
- final-diff review;
- stale-fact scans.

This experience is directly relevant to Pioneer, whose product direction itself focuses on making Agent
state and workflows understandable through UI.

---

# 2. Software Engineering and Technical Stack

## 2.1 React + TypeScript: state ownership matters more than component syntax

The main frontend lesson was not JSX or a specific state library.

The hard question was:

> Which state is allowed to exist on the client?

Supersonic established server-authoritative cockpit business state. Frontend-local state is appropriate
for transient UI details, not for inventing vehicle/navigation/risk/media truth.

The null-snapshot G5 finding demonstrated why this matters: a visually polished fallback can still be a
false business claim.

## 2.2 FastAPI: framework code should stay at the system edge

The backend evolved toward clearer layering:

```text
Router / Adapter
→ Policy / Application boundary
→ Service / Domain
→ Repository / Persistence adapter
```

`CockpitService` remained the realtime authority instead of allowing router code or PostgreSQL to
become accidental business owners.

Lesson:

> A framework is an adapter, not the architecture.

## 2.3 WebSocket: realtime behavior requires lifecycle design

A working connection is only the beginning.

The project had to model:

- session identity;
- revision ordering;
- reconnect;
- full-snapshot recovery;
- absolute session expiry;
- revoke;
- concurrent close;
- in-flight send;
- stale registration;
- degraded propagation.

A useful design for this project scale was:

```text
HTTP = commands
WebSocket = complete authoritative snapshots
```

Reconnect obtains the latest full snapshot rather than depending on event replay.

## 2.4 PostgreSQL: durable state and realtime state are different ownership domains

A major architecture lesson was resisting “put every state in the database”.

Supersonic separated:

```text
CockpitService
= realtime cockpit authority
```

from:

```text
PostgreSQL
= durable platform users / sessions / audit
```

This avoided a second realtime authority.

## 2.5 Transaction semantics matter more than CRUD syntax

Later persistence work focused less on ORM mechanics and more on:

- what must commit first;
- what survives failure;
- what rolls back atomically;
- how concurrent mutations avoid overwriting newer state.

The Admin Audit finding led to:

```text
durable attempted audit
→ business mutation
→ truthful outcome
```

If the attempted fact cannot be durably committed, the management mutation must not start.

This gave practical experience with Unit of Work, transaction boundaries, compare-and-set,
idempotency, rollback and concurrency semantics.

## 2.6 Authentication, authorization and Origin protection are separate concerns

The project distinguished:

- password authentication;
- opaque Platform Session;
- server-resolved Principal;
- role authorization;
- endpoint authorization;
- Origin protection;
- session expiry/revoke lifecycle.

A client-provided role has no authority by itself.

## 2.7 Audit is not ordinary logging

Application logs primarily help debugging.

Audit must answer:

```text
who
attempted what
against which target
when
with what outcome
```

The project introduced actor/target/correlation, attempted/succeeded/failed facts,
idempotency/conflict handling, fallback and reconciliation.

It also established negative rules: passwords, cookies, raw tokens and sensitive text do not belong in
Audit.

## 2.8 Backup tooling is not recovery capability until restore is rehearsed

A backup command existing in the repository was not treated as proof.

Recovery required:

```text
source PostgreSQL
→ real pg_dump
→ checksum / manifest
→ isolated restore database
→ real pg_restore
→ revision checks
→ row/invariant checks
→ application acceptance
```

The distinction between *tool availability* and *proven capability* is one of the strongest project
lessons.

## 2.9 CI should prove failure as well as success

The project moved beyond “tests are green” to negative verification.

For example:

```text
invalid recovery evidence
→ required validation must fail
```

and after restoration:

```text
valid evidence
→ required validation passes
```

This is stronger than checking that a test command appears in CI configuration.

## 2.10 Figma and design assets also need provenance

GP22 treated design material as engineering input with:

- source identity;
- version/node scope;
- classification;
- export;
- provenance;
- integrity hashes;
- runtime mapping.

This prevents implementation from silently becoming the source of design truth.

## 2.11 Git / Jujutsu / repository hygiene affect Agent reliability

The project gained practical experience with:

- GitHub Issues/PRs;
- Git worktrees;
- Jujutsu changes/bookmarks;
- Squash Merge;
- CI gates;
- CRLF noise and `.gitattributes`.

Repository hygiene proved to be Agent infrastructure: noisy worktrees and ambiguous task ownership
degrade both human and Agent review.

---

# 3. What Supersonic Carries Forward to Pioneer

The primary inheritance should be **method**, not domain code.

Carry forward:

```text
clear source of truth
→ explicit module ownership
→ bounded task
→ single Delivery Owner
→ real-environment validation
→ independent review
→ evidence
→ human gate
```

Also carry forward:

- server-owned authoritative state;
- explicit Mock / real / degraded distinctions;
- UI must not invent authoritative truth;
- narrow transaction boundaries;
- truthful failure semantics;
- provenance for design and evidence;
- negative tests;
- recoverability;
- exact-baseline Agent workflows.

Do not automatically carry forward:

- cockpit domain models;
- `gp05.v1`;
- GP22 cockpit components;
- Platform code whose abstractions are specific to Supersonic.

Reusable scripts or workflow ideas should be independently reviewed and introduced into Pioneer through
Pioneer's own governed tasks.
