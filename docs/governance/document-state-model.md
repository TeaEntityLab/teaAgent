# Document State Model
# 2026-06-02

This file defines the shared status vocabulary for findings, risks, issues,
tickets, roadmap items, and historical review documents.

The goal is simple: a future agent should not need to invent a new status
language when a risk changes, a ticket lands, or an old audit becomes stale.

## Canonical states

Use these states in new governance, risk, issue, ticket, and roadmap documents.
Existing historical documents may keep their original labels, but active indexes
must map those labels back to this model.

| State | Meaning | Required next action |
|-------|---------|----------------------|
| Proposed | A possible issue or direction has been observed but not triaged. | Assign an owner surface or reject with rationale. |
| Active | The issue is believed to affect current users, tests, docs, security, stability, or roadmap truth. | Link a ticket, mitigation, owner, or explicit defer decision. |
| Partially fixed | Code, docs, or process changed, but proof is incomplete or only one surface is covered. | Add active-path verification and update user-facing docs. |
| Verify/close | Implementation appears present; only closure evidence, docs sync, or stale-ticket cleanup remains. | Run the named verification and mark Fixed or Active. |
| Fixed | Active-path verification and docs agree that the issue no longer affects the current product. | Preserve evidence and remove from active queues. |
| Superseded | A newer finding, ticket, decision, or design replaces this item. | Add a supersession link to the replacement. |
| Archived | Historical context retained for audit or research value, with no active execution claim. | Do not use as current truth without checking a ledger or status page. |

## State mapping for existing labels

Older documents use several vocabularies. When updating an index or ledger,
translate them as follows.

| Existing label | Canonical state | Notes |
|----------------|-----------------|-------|
| OPEN | Active | Use for confirmed current defects or test-integrity gaps. |
| OPEN(test) | Active | Mark as test-integrity subtype in the row text. |
| PARTIAL | Partially fixed | Keep the owning ticket open. |
| FIXED | Fixed | Only valid when active-path proof exists. |
| Pending | Proposed | Roadmap rows may keep `Pending`, but governance indexes should treat it as Proposed unless already assigned. |
| In Progress | Active | The work is underway and should have an owner or ticket. |
| Complete | Fixed | Require exit evidence, not just implementation notes. |
| Closed | Fixed | Use only when the behavior was verified. |
| Deferred | Archived | If still likely to matter, use Proposed instead. |
| Stale | Superseded | Add the newer source of truth. |

## Required fields by artifact type

### Finding or risk row

Every active finding or risk should include:

- ID.
- Statement.
- Severity or priority.
- Canonical state.
- Source document.
- Owning surface.
- Linked ticket, roadmap row, or explicit defer decision.
- Verification evidence or missing evidence.
- Last reviewed date.

### Ticket row

Every ticket should include:

- ID.
- Goal.
- Canonical state.
- Dependencies.
- Acceptance criteria.
- Verification command or manual smoke.
- Risk class.
- Human review requirement.
- Closure evidence.

### Roadmap row

Every roadmap item should include:

- Horizon or track.
- Outcome.
- Canonical state.
- Owner or DRI placeholder.
- Next gate.
- Exit evidence.
- Linked risks and tickets.

## Source-of-truth rule

Use one active source of truth per question:

| Question | Source of truth |
|----------|-----------------|
| What should a daily user trust today? | `docs/daily-driver-current-status.md` |
| Which daily-driver findings are open or closed? | `docs/analysis/active-findings-status-ledger-2026-06-06.md` | Dated review packages and the June 1 ledger (superseded). |
| Which fix should be implemented next? | `docs/plans/ticket-plans/index.md` |
| Which roadmap horizon owns the work? | `docs/roadmap-status.md` |
| Which subsystem owns a local risk? | `docs/modules/<module>/risks.md` |
| Which decision explains why the design exists? | `docs/adr/` or `docs/decisions/` |

Historical dated analysis files are evidence. They are not current truth unless
an active ledger or index points to them.

## Supersession rule

When a new review changes an old claim, do not rewrite the old timeline. Add one
of these to the active index or to the top of the old file if the stale claim is
likely to mislead:

```markdown
> Supersession note, YYYY-MM-DD: This file is historical. For current status, use
> `<new-source>`. The relevant item is now `<State>` because `<short evidence>`.
```

Use a supersession note when:

- A defect was fixed or reclassified.
- A test now proves an old claim wrong.
- A roadmap item moved to a different horizon.
- A security or stability risk was split into multiple risks.
- A user-facing guide changed the recommended command.

## Closure rule

Do not mark an item Fixed because a patch exists. Mark Fixed only when:

- The active user or agent path was exercised.
- The relevant test or manual smoke is named.
- User-facing docs no longer advertise stale behavior.
- The owning index or ledger was updated.
- Residual risk is either absent, accepted, or moved to a new item.

## Human review rule

Mark Human Review Required when a state transition affects:

- Security boundaries.
- Approval scope.
- Data loss or undo semantics.
- Billing or budget behavior.
- Persistent state migration.
- Public claims about safety, reliability, or production readiness.

Human review is not required for routine archival, typo fixes, or adding links to
already verified evidence.
