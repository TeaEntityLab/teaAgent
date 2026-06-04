# TASK-DD2-014: Keep Daily-Driver Docs Synchronized With Runtime Status

**Priority:** P2
**Status:** Fixed — docs synchronized across current-status page, review index, and governance docs. Consistence checks pass (`scripts/validate_docs_consistency.py`). Verified by comprehensive audit (see docs/work-log/roadmap-work-items-2026-06-04.md).
**Primary files:** `docs/daily-driver-current-status.md`, `docs/daily-driver-known-issues-2026-06-01.md`, `docs/analysis/daily-driver-review-INDEX-2026-06-01.md`

## Problem

The documentation corpus is now large enough that fixed, active, and partially fixed
findings can coexist in confusing ways. A daily user needs the current page to be clear,
while maintainers still need historical audit evidence.

## Scope

- Keep a current-status page as the front door.
- Add supersession notes to historical known issues when code changes land.
- Update the review index with each new dated layer.
- Link each fixed claim to verification.

## Acceptance criteria

- A user can find current guidance in one click.
- Historical docs are not silently rewritten into a false timeline.
- Partially fixed items are labeled as partially fixed or verify/close.
- Docs consistency tests pass.

## Verification

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py tests/acceptance/test_docs_acceptance_count_accuracy.py -q
```

## Risks

- Too many docs can hide the current instruction.
- Too much rewriting can erase useful audit history.
