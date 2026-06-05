# Strategic Plans Consolidation Decision - 2026-05-31

> Supersession note, 2026-06-05: This decision document is historical evidence.
> The consolidation was completed: active work moved to
> `docs/plans/daily-driver-complete-work-plan-risk-roi-2026-06-04.md`, strategic
> docs to `docs/strategy/`, and governance rules to
> `docs/governance/documentation-operating-model-2026-06-04.md`. The indexed
> plans remain as archived reference material.

**Purpose:** Decide whether to consolidate strategic plans into backlog-priority.md or keep them as reference documents.

---

## Strategic Plans Reviewed

| Plan | Purpose | Size | Status |
|------|---------|------|--------|
| `competitive-positioning-plan-2026-05-31.md` | README rewrite, security whitepaper, demo scripts | Medium | Not started |
| `ux-improvement-roadmap-2026-05-31.md` | Post-run summary, budget warnings, undo UX, memory/context | Medium | Not started |
| `future-roadmap-risk-usability-backlog-2026-05-31.md` | Large strategic backlog with horizons | Large | Not started |

---

## Decision: Keep as Reference Documents

**Rationale:**

1. **Strategic vs. Tactical:** These plans contain strategic positioning, UX research, and long-term roadmap items. They are not immediate implementation tickets.

2. **Different Audience:**
   - `backlog-priority.md` is for developers implementing features
   - Strategic plans are for product decisions, marketing, and long-term planning

3. **Size and Complexity:** The future-roadmap document is very large with horizons and detailed analysis. Consolidating it would make backlog-priority.md unwieldy.

4. **Reference Value:** These plans contain research, evidence, and reasoning that should be preserved as reference material.

5. **No Completion Tracking Needed:** These are aspirational/strategic documents, not execution sheets. They don't need the same completion tracking as daily driver plans.

---

## Recommended Action

**Keep strategic plans as reference documents in `docs/plans/` with:**

1. **Add status header** to each plan:
   ```markdown
   **Status:** Reference document - not an active execution plan
   ```

2. **Extract actionable items** into backlog-priority.md:
   - If a specific item from these plans becomes a priority, add it to backlog-priority.md
   - Reference the strategic plan for context

3. **Add cross-reference** in backlog-priority.md:
   ```markdown
   ## Strategic Reference Documents

   For long-term planning, positioning, and UX research, see:
   - `docs/plans/competitive-positioning-plan-2026-05-31.md`
   - `docs/plans/ux-improvement-roadmap-2026-05-31.md`
   - `docs/plans/future-roadmap-risk-usability-backlog-2026-05-31.md`
   ```

4. **Archive truly obsolete plans** to `docs/archive/`:
   - Daily driver plans (already marked as COMPLETE, could be archived)
   - Any superseded plans

---

## Next Steps

1. Add status headers to strategic plans
2. Add cross-reference section to backlog-priority.md
3. Archive completed daily driver plans to `docs/archive/`
4. Keep backlog-priority.md as the single source of truth for active implementation work

---

**Decision Date:** 2026-05-31
**Decision:** Keep strategic plans as reference documents
**Reason:** Strategic vs. tactical separation, different audiences, reference value
