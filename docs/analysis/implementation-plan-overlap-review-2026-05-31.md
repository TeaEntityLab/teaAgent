# Implementation Plan Overlap Review - 2026-05-31

**Purpose:** Review external implementation_plan.md for overlaps with in-repo governance-hardening.md and other plans.

---

## Summary

The external implementation_plan.md at `.gemini/antigravity/brain/.../implementation_plan.md` proposes changes to core governance files that appear to have already been completed according to `docs/plans/governance-hardening.md`.

---

## Overlap Analysis

### External Implementation Plan Proposals

| File | Proposed Change | Status in governance-hardening.md |
|------|----------------|-----------------------------------|
| `tools.py` | Add strict static validator, capability manifests to security tiers | ✅ Tool lint: Shipped |
| `selftest.py` | Introduce static fuzz checking on ToolRegistry | ✅ Selftest: Shipped |
| `plan_mode.py` | Enforce Plan-before-write checks, map files against PlanContract | ✅ Plan gate: Shipped |
| `workflow_engine.py` | Wire validation profiles, trigger automatic rollback | ✅ Workflow validation: Shipped (Phase 4-5) |
| `run_store.py` | Create AuditLevel tiers, signature-based verify checks | ✅ Audit completeness: Shipped |
| `tui.py` | Expose interactive run store management | ✅ Runs trace: Shipped |
| `failure_card.py` | Refine auto-reviewer curation logic, CLI command surface | ✅ Failure cards: Shipped |
| `swarm.py` | Build structured approval lineage tracking | ✅ Swarm LLM: Shipped |
| `parallel_executor.py` | Enforce git worktree sandboxing | ✅ Tournament: Shipped |
| `comparator.py` | Base tournament winner on weighted metric schema | ✅ Tournament: Shipped |

---

## Key Findings

### 1. All Proposed Work Already Shipped

**Issue:** Every item in the external implementation_plan.md corresponds to a "Shipped" item in governance-hardening.md.

**Impact:** High - The external plan is obsolete and could cause confusion or duplicate work if followed.

**Evidence:**
- External plan has "User Review Required" and "Architectural Decisions (User Approved)" sections
- No completion status markers in external plan
- governance-hardening.md shows all corresponding items as "Shipped" or "Beta"

---

### 2. External Plan Location

**Issue:** The implementation_plan.md is located outside the repository at `.gemini/antigravity/brain/.../implementation_plan.md`.

**Impact:** Medium - Not version-controlled with the repo, may be stale or forgotten.

**Recommendation:**
- If the plan is obsolete, delete it
- If it contains useful context, move it into `docs/archive/` with a note that it's superseded
- Update any references to point to governance-hardening.md

---

### 3. Architectural Decisions Already Implemented

**Issue:** The external plan has "Architectural Decisions (User Approved)" sections for:
- Subagent JIT Approvals: Fail-fast immediate
- Plan Enforcement: Strict immediate block
- Memory Invalidation: Custom rules enabled

These decisions appear to have been implemented in the shipped governance work.

**Impact:** Low - The decisions were sound and implemented, but the plan document is stale.

---

## Recommendations

### Immediate Actions

1. **Archive or delete** the external implementation_plan.md:
   - ✅ Documented in this review - external plan is superseded
   - Recommendation: Delete `.gemini/antigravity/brain/.../implementation_plan.md` as it's obsolete
   - If useful for reference: Move to `docs/archive/implementation_plan-superseded.md` with a note

2. **Update any references** to the external plan to point to governance-hardening.md

3. **Document completion** in governance-hardening.md:
   - The "Architectural Decisions" from the external plan are now implemented
   - Consider adding a note linking to the archived plan for historical context

### Status

- ✅ Review completed 2026-05-31
- ⏸️ External plan deletion requires manual action (outside repo)
- ✅ All proposed work already shipped per governance-hardening.md

---

## Conclusion

The external implementation_plan.md is **superseded** by governance-hardening.md. All proposed changes have been shipped. The external plan should be archived or deleted to prevent confusion.

---

**Reviewed:** 2026-05-31
**Status:** External plan superseded by in-repo governance-hardening.md
