# TASK-DD2-011: Surface Corrupt Memory And Run State

**Priority:** P1
**Status:** In Progress — partial (re-verified 2026-10-27): memory-catalog corruption is surfaced by `preflight.py` via `catalog.health_report`, but `daily.py` reports only run-store corruption. No friction entry; held under DR-006
**Primary files:** `teaagent/memory/catalog.py`, `teaagent/run_store.py`, `teaagent/daily.py`

## Problem

Memory and run-store readers can silently skip malformed JSON or return `None` for
corrupt run summaries. Daily output can then omit degraded state and look healthier
than it is.

## Scope

- Track corrupt memory lines/files as warnings.
- Track corrupt run JSONL files as degraded run-store health.
- Show warnings in daily/preflight output.
- Preserve best-effort listing for healthy records.

## Acceptance criteria

- Malformed memory JSONL produces a visible warning.
- Malformed run JSONL produces a visible warning or degraded health item.
- Healthy records still load.
- Warnings include enough path context for repair without dumping sensitive content.

## Verification

```bash
python3 -m pytest tests -k "memory or run_store or daily"
```

Add tests that inject malformed memory and run JSONL in a temp workspace.

## Risks

- Too many warnings can overwhelm daily output.
- No warnings can hide state loss and make debugging harder.
