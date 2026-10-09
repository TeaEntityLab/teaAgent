# ADR-0031 Extension Decision — 2026-10-09

> **Claim class:** Dated owner decision record (recorded in session by the agent at the owner's direction). Not a scheduling authority beyond the decision it records.
> **Owner:** owner-operator (decision); docs (record)
> **Last reviewed:** 2026-10-09
> **Review trigger:** B1 session booked or held; 2026-11-15 reached; any change to ADR-0031.
> **Authority:** [ADR-0031](../adr/0031-shadow-mode-exit-criteria.md), [DR-006](../strategy/dr-006-owner-decision-2026-06-22.md), [Roadmap Status](../roadmap-status.md).
> **Action register:** G-P2-21.

## Context

The ADR-0031 shadow→enforce review date of 2026-09-29 (itself an extension from 2026-09-12) passed with the [readiness checklist](adr-0031-2026-09-29-readiness-checklist.md) at 0/8 and no promote/extend/revert entry anywhere in the repository. The [2026-10-09 roadmap review](../reviews/roadmap-review-and-improvement-plan-2026-10-09.md) §3.2 flagged this as the permanent-shadow anti-pattern the ADR exists to prevent and put the decision to the owner with **revert** as the default.

Evidence state at decision time (unchanged since 2026-09-17): H4 packet 9 observed / 22 reachable / 1 candidate (`D1`, `owner_verdict: null`), verdict `needs_review`; criterion 2 passes vacuously (0 policies, 0 roles); criterion 3 median ≈ 0.5 ms; criterion 5 rollback dry-run `ok=true`; criterion 4 human sign-off outstanding; `promotion_ready` is a hardcoded `false`; 0 `origin: owner` runs in the run index.

## Decision (owner, 2026-10-09, in session)

**Extend once more to no later than 2026-11-15**, bound to a booked **B1 owner-observed coding session** (one real coding task through the harness with actual tool activity, approval/rejection, receipt inspection and undo, recorded by the owner). The session date is **to be booked**; the owner chose to record the deadline now and supply the date later.

**Fallback:** if the B1 session has not been held by 2026-11-15, the disposition is **revert** (remove the shadow wiring that lacks justified demand, preserving evidence and decision history) **without a further review**. No agent may flip any mode or claim Human Review in the meantime.

Rejected alternatives: *revert now* (the review's default; the owner prefers to keep the option open for one bounded window) and *defer without a date* (forbidden by the ADR's own expiry rule).

## What this changes

| Artifact | Change |
| --- | --- |
| `docs/adr/0031-shadow-mode-exit-criteria.md` | Expiry 2026-09-29 → 2026-11-15; decision log added |
| `docs/work-log/adr-0031-2026-09-29-readiness-checklist.md` | Trigger and close date → 2026-11-15; item 0 (B1 booked and held) added; revert fallback stated |
| `docs/roadmap-status.md` | H4 Next Gate restated; owner-decisions paragraph added; no status moved |
| `docs/backlog-priority.md` | RBAC enforce-flip row carries the extension; header date |
| `docs/specs/held-roadmap-forward-spec-index-2026-07-11.md` | §8 decision-queue row date |
| `docs/plans/current-roadmap-execution-plan-2026-08-26.md` | Header note; §6 dates marked historical |

## What this does not change

- No `TEAAGENT_H4_*` mode changes; `shadow` stays `shadow`.
- No agent-generated verdict for D1; criterion 4 remains owner sign-off.
- No new evidence: the extension buys time for the owner session, not a different criterion.

## Falsifier

This record is wrong if a dated ADR-0031 disposition made between 2026-09-29 and 2026-10-09 exists outside the repository; the owner should then supersede this file with that record.
