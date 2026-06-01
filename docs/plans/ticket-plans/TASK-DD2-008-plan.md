# TASK-DD2-008: Enforce Read-Only And Dry-Run Side-Effect Contract

**Priority:** P1
**Status:** Newly discovered
**Primary files:** `teaagent/ergonomics/dry_run.py`, `teaagent/preflight.py`, `teaagent/daily.py`, `teaagent/run_store.py`

## Problem

Commands advertised as dry-run or read-only can still initialize `.teaagent` directories
through preflight, daily brief, memory, or run-store helpers.

## Scope

- Decide whether first-run initialization is allowed during dry-run/read-only commands.
- If allowed, print explicit initialization wording.
- If not allowed, thread a readonly flag through helpers and avoid creating state.
- Add fresh-workspace before/after snapshot tests.

## Acceptance criteria

- A dry-run in a fresh workspace has deterministic, documented side effects.
- Read-only preflight does not create `.teaagent` unless explicitly allowed.
- Docs avoid saying "no writes" when initialization can happen.
- Any intentional initialization is visible to the user.

## Verification

```bash
python3 -m pytest tests -k "dry_run or preflight or daily"
```

Add a focused test that snapshots a temp workspace before and after dry-run/preflight.

## Risks

- Disabling initialization can remove useful first-run guidance.
- Allowing hidden initialization weakens operator trust.
