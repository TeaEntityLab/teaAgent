# Risk Review: approval pending stale-index skip

**Date**: 2026-09-14
**Change**: `collect_pending_approval_views` catches `FileNotFoundError` from `store.show_run(run_id)` and skips the entry.

## Risk

- **Low**: skips stale index entries (deleted run files) instead of crashing.
- **No security impact**: read-only path; no approval decisions changed.
- **No data loss**: stale entries are already unreachable; skipping them is correct.

## Verification

- `teaagent approval pending` lists pending approvals without crashing.
- `run --route-model` emits `model_route` with real `run_id` (no phantom `pending` run).
