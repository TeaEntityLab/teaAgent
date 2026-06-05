# P0 Acceptance Test Gaps - 2026-05-31

> Supersession note, 2026-06-05: This file is historical evidence. The gaps
> documented here were addressed in the Phase 0 trust repair work. For current
> acceptance coverage, use `docs/acceptance.md`. For implementation status,
> use `docs/plans/ticket-plans/index.md`.

**Purpose:** Document P0 acceptance test gaps identified in agent-ecosystem roadmap cross-reference

---

## P0 Gaps Identified

From the agent-ecosystem roadmap cross-reference, 3 P0 journeys have no acceptance tests:

### 1. Issue-to-Plan Intake

**Required test:** `test_issue_to_plan_acceptance_flow.py`

**Journey:** User pastes an issue, gets ambiguity score, plan artifact, safe command, and acceptance checklist.

**Current state:** Not implemented

**Complexity:** High - requires implementing issue parsing, ambiguity scoring, plan generation

**Dependencies:**
- Plan mode functionality
- Issue text parsing
- Ambiguity detection
- Plan artifact generation

**Recommendation:** Add to backlog-priority.md as P0 item with clear acceptance criteria

---

### 2. Plan Review and Revision

**Required test:** `test_plan_review_revision_flow.py`

**Journey:** User can compare two plan revisions before execution and bind run to the accepted plan hash.

**Current state:** Not implemented

**Complexity:** High - requires plan versioning, diff display, hash binding

**Dependencies:**
- Plan storage and versioning
- Plan diff/comparison
- Run-to-plan binding
- Hash verification

**Recommendation:** Add to backlog-priority.md as P0 item with clear acceptance criteria

---

### 3. Guided Recovery

**Required test:** `test_guided_recovery_flow.py`

**Journey:** Failed/partial run suggests resume, undo, inspect audit, or retry with safer mode.

**Current state:** Not implemented

**Complexity:** Medium - requires failure analysis, recovery suggestions

**Dependencies:**
- Failure classification
- Recovery strategy selection
- Integration with existing undo/resume functionality

**Recommendation:** Add to backlog-priority.md as P0 item with clear acceptance criteria

---

## Decision: Add to Backlog, Not Implement Now

**Rationale:**

1. **Scope:** These are major features, not simple test additions. They require significant implementation work.

2. **Dependencies:** Each gap depends on other functionality that may not exist yet.

3. **Priority:** While marked P0 in the roadmap, they are not blocking current work. The daily driver hardening is complete.

4. **Process:** These should go through proper planning, spec-writing, and implementation phases.

---

## Recommended Action

Add these items to `docs/backlog-priority.md` under "Open — High (P0)" with:

1. Clear acceptance criteria
2. Dependencies listed
3. Size estimates
4. References to the agent-ecosystem roadmap for context

---

## Alternative: Defer to Strategic Plans

These features align with the strategic plans:
- Issue-to-plan aligns with competitive positioning (README rewrite)
- Plan review aligns with governance hardening
- Guided recovery aligns with UX improvement roadmap

Consider keeping them in the strategic plans until they become active priorities.

---

**Decision Date:** 2026-05-31
**Decision:** Add to backlog as P0 items, not implement now
**Reason:** Major features requiring implementation, not just test additions
