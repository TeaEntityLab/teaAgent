# Documentation Critical Questioning
# 2026-06-04

## Review Mode

Primary mode: documentation-system review.

Secondary lenses: user trust, agent maintainability, roadmap governance, test
integrity, and cost-effectiveness.

This document challenges the documentation corpus itself. It asks whether the
project is producing durable clarity or only producing more artifacts.

## Findings

### 1. The corpus is impressive, but impression can become camouflage

Question:

> Are we using document volume as evidence of maturity, or are we proving that
> the documents help users and agents make better decisions?

TeaAgent has an unusually rich documentation corpus for a young project. That
is valuable only while each document has a role. A large corpus can hide stale
claims because readers assume someone else already reconciled them.

Required response: keep a curated index and require each new governance-sensitive
document to declare its class: current truth, evidence, plan, reference,
governance, or work log.

### 2. The most dangerous docs are the partly guarded docs

Question:

> Which documents look machine-verified but still contain unguarded prose claims?

`docs/acceptance.md` is the proof case. The acceptance-count headline was
guarded, but the body still carried stale full-suite failure prose. A reader
would trust the whole file because one fact in it is tested.

Required response: define guarded-claim blocks for volatile facts and expand the
docs consistency tests only where the ROI is high.

### 3. Historical evidence is useful, but historical language can sound current

Question:

> Can a future maintainer tell the difference between "this was true then" and
> "this is true now" without reading five surrounding files?

Dated docs should not be erased. They preserve learning. But dated docs must not
present stale defects, stale fixes, stale competitor observations, or stale test
counts as current truth.

Required response: add supersession notes where stale claims are likely to
mislead, and route readers from dated packages to current front doors.

### 4. Roadmap and risk docs can silently diverge

Question:

> If a risk is P0/P1 in a module doc, where is the central owner, ticket, or
> defer decision?

The module risk inventory is detailed, but detail is not ownership. A risk can
be well-described and still be unmanaged if it never reaches a ticket, roadmap,
or explicit defer decision.

Required response: audit high-severity module risks and require upward links.

### 5. The docs can overfit to agent reviewers instead of daily users

Question:

> Would a new daily user understand the recommended command path faster after
> reading the docs, or would they mostly learn the project history?

The current corpus is strongest for maintainers and future agents. User-facing
docs must stay shorter and more operational: what to run, what to trust, what
not to rely on yet, and how to recover.

Required response: keep historical rationale out of daily-use front doors unless
it changes a user's immediate choice.

### 6. "More docs" is not free

Question:

> What is the maintenance cost of each new document, and what future search does
> it eliminate?

Every new Markdown file adds a claim surface, an index obligation, and a future
staleness risk. The correct standard is not "write less." The correct standard
is "write documents that make later work easier to verify."

Required response: each new plan or review should either become a front door,
carry dated evidence, or produce executable work items.

### 7. The current state model is necessary but not yet operational enough

Question:

> Are canonical states actually applied by active docs, or do they only exist as
> a governance file?

`document-state-model.md` is good. The next step is operational adoption:
roadmap rows, work-item ledgers, findings ledgers, and module risk rollups need
to converge on the vocabulary.

Required response: add a lightweight lint or review checklist before trying to
normalize every historical document.

### 8. The project still needs an evidence hierarchy

Question:

> When code, tests, docs, and memory disagree, what wins?

For current behavior, code plus active-path tests win. For intent, ADRs and
accepted specs win. For roadmap state, `docs/roadmap-status.md` wins. For user
instructions, current guides win. Memory and dated reviews are evidence, not
authority.

Required response: write this hierarchy into the documentation operating model.

## Skeptical Counterarguments

| Claim | Counterargument | Balanced answer |
| --- | --- | --- |
| "Just delete old docs." | Deletion destroys the learning trail and makes future agents repeat old research. | Keep dated docs; mark supersession clearly. |
| "Just add more validators." | Validators can become brittle and expensive if they parse every paragraph. | Guard only high-volatility, high-trust claims first. |
| "A big docs index solves discoverability." | A huge generated index can become another unreadable file. | Use a curated front door now; automate exhaustive inventory later. |
| "All risk docs should be centralized." | Module-local risks need local detail and ownership. | Centralize priority and escalation, not every detail. |
| "English-only docs are enough." | Language consistency helps, but stale English is still stale. | English-only for new durable project docs; truth rules matter more. |

## Required Fixes

1. Keep `docs/INDEX.md` as the curated documentation front door.
2. Keep `docs/acceptance.md` free of stale full-suite claims unless the command,
   interpreter, date, and commit are named.
3. Add the documentation operating model to the governance index.
4. Update roadmap H0 to include documentation-current-truth work.
5. Create a doc-vs-HEAD guard for volatile prose claims.
6. Audit P0/P1 module risk rows for upward links.
7. Create a generated inventory only after the curated front door proves useful.

## Decision

Request changes before treating the documentation corpus as stable.

The corpus is strong enough to be worth governing. It is not yet governed enough
to be self-trusting.

## Residual Risks

- This review did not inspect every Markdown line.
- Some stale claims likely remain in dated evidence files.
- `cx` confirms discoverability structure, not semantic truth.
- User-facing docs may still contain more project history than first-hour users
  need.
- Future agents may continue adding dated docs unless the index and operating
  model become part of the default workflow.
