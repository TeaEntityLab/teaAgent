# WDG-002: Suite Tiering (Smoke / Acceptance / Nightly)

**Priority:** P0  
**Status:** Fixed  
**Sprint:** 2026-06-10 → 2026-06-17  
**Depends on:** WDG-001 findings (tier boundaries)  
**Primary files:** `pyproject.toml`, `tests/conftest.py`, `docs/acceptance.md`, CI workflows, `scripts/validate_docs_consistency.py`

## Problem

ENG-R5 / WDG-001: Single monolithic suite exceeds constrained environment CPU
budgets. Merge gates need a fast smoke tier; release needs acceptance; mutation
and eval belong on nightly.

## Scope

1. Register pytest markers: `smoke`, `acceptance`, `nightly` (align with existing
   acceptance dir where possible).
2. Define profiles:
   - **smoke:** &lt;2 min, gates every PR
   - **acceptance:** current `tests/acceptance` + regression (~628 tests)
   - **nightly:** full suite + mutation + eval fixtures
3. Document which tier gates merge vs release vs nightly CI.
4. Extend docs validator to warn when README/roadmap cites full count without
   tier label (WDB-004 precursor).

## Acceptance criteria

- `pytest -m smoke` completes in &lt;2 min on CI runner class used by project.
- Acceptance profile documented with exact command and test count at HEAD.
- CI runs smoke on PR; acceptance on main; nightly scheduled.
- `validate_docs_consistency.py --test-quality-mode off` passes.

## Verification

```bash
python -m pytest -m smoke -q --tb=no
python -m pytest tests/acceptance -q --tb=no
# Document nightly command in docs/acceptance.md
```

## Risks

- Marker migration is large — start by marking slow/mutation tests `nightly`,
  default remainder to smoke+acceptance split per directory convention.

## Do not

- Remove full suite; demote to nightly, do not delete.
