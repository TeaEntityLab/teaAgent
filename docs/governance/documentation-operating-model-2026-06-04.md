# Documentation Operating Model
# 2026-06-04

## Purpose

This operating model turns TeaAgent's documentation governance into daily
practice. It complements:

- [Document State Model](document-state-model.md)
- [Risk Issue Roadmap Workflow](risk-issue-roadmap-workflow.md)
- [Documentation Taxonomy And Ownership](doc-taxonomy-and-ownership.md)
- [Documentation Maintenance Policy](doc-maintenance-policy-2026-06-02.md)

## Core Principle

Documentation is part of the product. A stale safety, test, roadmap, or
user-facing claim is a product defect, not a cosmetic docs issue.

## Claim Classes

Every governance-sensitive document should fit one dominant claim class.

| Claim class | Meaning | Examples | Freshness requirement |
| --- | --- | --- | --- |
| Current truth | Describes what users or maintainers should trust now. | `daily-driver-current-status.md`, `roadmap-status.md`, ticket index | Must be updated when behavior or status changes. |
| Evidence snapshot | Records what was observed at a date, commit, or review pass. | Dated audits, surveys, total-review docs | Must name date and evidence; do not silently rewrite history. |
| Plan | Describes intended work and acceptance criteria. | Master plans, ticket plans, work logs | Must link to status source and verification. |
| Proposal | Describes a proposed change not yet accepted or implemented. | ADRs in Proposed status, RFCs, design sketches | Should link to decision or superseding document when resolved. |
| Aspiration | Describes a future goal or direction without a committed timeline. | Roadmap outlook docs, strategy documents | Must not be cited as committed scope. |
| Non-goal | Describes something explicitly out of scope or deliberately not addressed. | "When not to use" pages, scope boundaries | Should be reviewed when adjacent scope changes. |
| Reference | Defines APIs, commands, schemas, or module behavior. | API docs, module docs, terminology | Must stay version-aware; stale references require correction. |
| Governance rule | Defines process or required standards. | Governance docs, release gates | Changes need review when they affect safety, status, or release claims. |
| User guide | Helps a user choose and execute commands. | TUI guide, chat reference, troubleshooting | Must be short, current, and practical. |

### Claim class label convention

Every governance-sensitive document should declare its claim class in a header
blockquote so readers and automated checks can distinguish current truth from
dated evidence from aspiration:

```markdown
> **Claim class:** current-truth | evidence-snapshot | plan | proposal | aspiration | non-goal | reference | governance-rule | user-guide
```

Analysis and strategy docs should use `evidence-snapshot` or `aspiration` unless they
are the canonical source of truth for a specific claim. Inline exceptions within a
doc (e.g., a current-truth table inside an evidence-snapshot doc) are fine but
should be explicitly scoped.

## Evidence Hierarchy

When sources disagree, use this hierarchy:

1. Current code plus active-path tests for runtime behavior.
2. Current stable front doors for user-facing truth.
3. Accepted ADRs and specs for design intent.
4. `docs/roadmap-status.md` for roadmap state.
5. Ticket plans and work logs for execution state.
6. Dated analysis and reviews for historical evidence.
7. Memory, chat transcripts, and old generated docs as clues only.

If an old evidence document conflicts with a higher source, do not delete it by
default. Add a supersession note or update an index.

## Freshness Windows

| Claim type | Expires when | Required proof to refresh |
| --- | --- | --- |
| Full-suite status | Any code, test, dependency, or CI environment change | Command, interpreter, date, commit, result. |
| Acceptance count | Any acceptance test file change | Acceptance collection or guard test. |
| Provider count | Any provider registry or provider docs change | Runtime provider registry check. |
| Dependency audit | Any dependency, extras, lock, or audit-scope change | Audit command and scope. |
| Security posture | Any approval, policy, sandbox, auth, audit, or persistence change | Targeted tests and human-review note. |
| Roadmap state | Any release gate, ticket closure, or priority change | Linked exit evidence. |
| Competitor survey | Any release planning or positioning claim | Dated sources or explicit "not refreshed" caveat. |

## Source-Of-Truth Matrix

| Question | Source of truth | Supporting docs |
| --- | --- | --- |
| What should users do today? | `docs/daily-driver-current-status.md` | Guides and troubleshooting docs. |
| Which findings are active? | Active findings ledger or successor | Dated review packages. |
| Which work is next? | `docs/plans/ticket-plans/index.md` and active work logs | Master plans. |
| Which roadmap horizon owns the work? | `docs/roadmap-status.md` | Roadmap rationale and work items. |
| Which subsystem owns a local risk? | `docs/modules/<module>/risks.md` | Module index and central risk register. |
| Which safety claim is release-blocking? | Governance release gates and security docs | Threat model, FMEA, risk register. |

## Supersession Rules

Add a supersession note when:

- A dated doc contains a claim that is now false or materially incomplete.
- A user-facing command recommendation changed.
- A risk was split, demoted, promoted, fixed, or moved to another owner.
- A test result or count changed.
- A roadmap row moved horizon or status.

Use this shape:

```markdown
> Supersession note, YYYY-MM-DD: This file is historical evidence. For current
> status, use `<new-source>`. The relevant item is now `<State>` because
> `<short evidence>`.
```

## Guarded Claims

Guard only high-value claims first. Do not try to parse every paragraph.

P0 guarded claims:

- Acceptance test count in `docs/acceptance.md`.
- Full-suite status if a stable doc states it as current.
- Provider count in README, architecture, and usage docs.
- Release-readiness claims.
- Security bypass or approval-safety claims in current guides.

P1 guarded claims:

- Roadmap row status and required fields.
- Proposed ADR owner and decision date.
- P0/P1 module risk upward links.
- Coverage omit reason and target re-entry date.
- Dependency audit scope labels for base package vs optional extras.

P2 guarded claims:

- Link health across all Markdown.
- Generated table of contents freshness.
- Competitor survey age.
- Guide command snippets that can be locally smoke tested.

## Merge Policy

| Situation | Preferred action |
| --- | --- |
| Two current docs answer the same question differently | Pick one canonical source; turn the other into a pointer. |
| A dated doc is stale but valuable | Keep it; add supersession note or index mapping. |
| A module risk duplicates central risk text | Keep module detail; centralize priority and owner. |
| A plan repeats a review | Shorten the plan; link the review. |
| A roadmap repeats implementation steps | Replace steps with ticket links and exit evidence. |
| A user guide contains history | Move history to analysis; keep the guide operational. |

## Documentation Definition Of Done

A governance-sensitive doc change is done when:

- Its claim class is clear.
- It links to the correct front door or active source of truth.
- Volatile facts include date, command, commit, and scope where applicable.
- It does not create a competing current-truth source.
- Historical contradictions are handled with supersession or index notes.
- Validation commands pass.

## Validation Commands

Run after documentation governance edits:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

Use `cx overview docs --limit 120` and relevant `cx symbols` searches to check
discoverability when adding front-door, status, risk, or roadmap docs.
