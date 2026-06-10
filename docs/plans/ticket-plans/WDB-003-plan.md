# WDB-003: Fix Roadmap Contradictions (H2–H6 vs Milestones)

**Priority:** P0  
**Status:** Fixed  
**Sprint:** 2026-06-10 → 2026-06-17  
**Depends on:** WDA-001 evidence  
**Primary files:** `docs/roadmap-status.md`, `scripts/validate_docs_consistency.py`, `tests/test_validate_docs_consistency_mode.py`

## Problem

ENG-R2: `roadmap-status.md` shows H2/H3 Pending while M2/M3 Complete; H4–H6
Pending while commit log (`fe2a881`, `4e0a9e9`) claims Horizon implementation.
A trust product cannot ship contradictory canonical status.

## Scope

1. Reconcile horizon table with milestone table using evidence classes:
   - **Complete** — production entry path + acceptance citation.
   - **Partially implemented — unwired** — code + tests, no production import.
   - **Pending** — no substantive implementation.
2. Add validator rule: horizon status must not contradict linked milestone exit
   evidence (extend `validate_docs_consistency.py`).
3. Update header `Last updated` and `Last reviewed` to edit date.
4. Remove or qualify stale claims (e.g. "4758 tests pass" without run date/commit).

## Acceptance criteria

- No row pairs where milestone says Complete and horizon says Pending without
  `Partially implemented` or explicit note.
- H4/H5/H6 rows cite WDA-001 unwired state until WDA-002+ land.
- Validator test covers a seeded contradiction fixture.
- `validate_docs_consistency.py --test-quality-mode off` passes.

## Verification

```bash
python scripts/validate_docs_consistency.py --test-quality-mode off
python -m pytest tests/test_validate_docs_consistency_mode.py -q
```

## Risks

- Over-correcting to Complete when only tests exist — use import-graph truth
  from WDB-001, not commit message text.

## Do not

- Mark H4/H5/H6 Complete while WDB-001 reports unwired clusters.
