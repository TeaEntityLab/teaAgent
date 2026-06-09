# LOCAL_FEEDBACK.md — Failure-Learning Log (T8)

> Every failure gets recorded, or the system just repeats it. Two non-negotiables:
> **a correction without Evidence is not a correction; a correction without an Anti-regression Rule is
> only a temporary patch.** Newest entries on top.

## Entry template
```markdown
### YYYY-MM-DD — <short title>
- **Step:** what was being attempted
- **Evidence:** the re-runnable proof of the failure (command + output, failing test, trace)
- **Error Type:** logic / spec / test-gap / permission / config / race / env
- **Root Cause:** the actual cause, not the symptom
- **Correction:** what changed
- **Verification:** the re-runnable proof it is now fixed
- **Anti-regression Rule:** the durable rule / test / check that stops recurrence
```

---

### 2026-06-09 — Governance framework adopted; T0 files were entirely missing
- **Step:** adopting Governed Agentic Engineering into teaagent; planning to apply it to SURF-010.
- **Evidence:** `for f in SPEC.md TEST_MATRIX.md AGENT_RULES.md LOCAL_FEEDBACK.md DONE_CHECKLIST.md; do ...`
  → all reported `missing` at HEAD `c37e181`. CI present (`ci.yml`, `security.yml`) but no mutation testing.
- **Error Type:** process gap (no spec/permission/feedback layer despite shipping L3 changes).
- **Root Cause:** governance scaffolding never created; L3 trust-boundary changes (e.g. resume auto-grant)
  shipped without an explicit spec or P0 security matrix.
- **Correction:** added `governance/` with framework doc, adoption roadmap, T0 five files, templates,
  and the first live spec + test matrix (SURF-010).
- **Verification:** files present and cross-linked from `governance/README.md`; this commit.
- **Anti-regression Rule:** any change classified L3 by the §4 cost model MUST carry a `specs/<ticket>.md`
  + `test-matrices/<ticket>.md` with P0 covered before merge. (To be CI-enforced per Roadmap A1.)

<!-- Add SURF-010 Step 5 spec-mutation result here once Steps 3–5 of the executable plan are run. -->
