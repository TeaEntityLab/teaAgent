# budget — Behavior Specification

## Overview

The budget module enforces per-run cost limits and provides long-term cost observability. It is composed of four components that operate at different timescales:

| Component | Timescale | Enforcement |
|---|---|---|
| `RunBudget` | per-run | hard limit; raises exception |
| `BudgetMonitor` | per-run | soft thresholds; callbacks/warnings |
| `CostTracker` | historical | read-only audit aggregation |
| `daily_cost` ergonomic | per-day | hard cap via `SystemExit` |

---

## Behavior Contract

### `RunBudget` (`budget.py`)

- **Guarantees**: Once constructed with valid limits, `check_cost_preflight()` always raises `BudgetExceededError` if the pre-flight estimate exceeds `max_estimated_cost_cents`. It never silently swallows over-budget conditions.
- **Pre-flight bypass**: If `max_estimated_cost_cents <= 0`, the check is skipped entirely (budget enforcement disabled).
- **No mutable state**: `RunBudget` is a `frozen=True` dataclass. All budget checks are pure reads.

### `BudgetMonitor` (`budget_monitor.py`)

- **Guarantees**: Each configured threshold (50%, 80%, 90%, 100%) fires **at most once** per monitor instance. Re-checking the same cost value never re-fires a previously emitted threshold.
- **Idempotency**: `_emitted_levels` tracks fired thresholds as `int` bucket values. Once added, they are never re-fired until `reset()` is called.
- **Action ordering**: `check()` returns the highest-priority `BudgetAction` across all newly crossed thresholds in a single call. Priority: `NONE < WARN < PROMPT_CONFIRM < SUGGEST_READ_ONLY`.
- **Non-interactive mode**: At 90%, the monitor auto-continues (returns `WARN`) instead of calling `on_prompt`. Controlled by env vars `TEAAGENT_NO_SUMMARY=1` or `TEAAGENT_INTERACTIVE=0`.
- **Prompt guard**: `on_prompt` is called at most once per monitor instance per run (guarded by `_prompted`).

### `CostTracker` (`cost_tracker.py`)

- **Guarantees**: Always returns well-formed summary dicts even if no run data exists (returns `{'runs': 0, 'cost_cents': 0.0, ...}`).
- **No side effects**: All methods are read-only. The tracker never writes or modifies audit logs.
- **Fallback timestamps**: If no `created_at` is found in a run's events, the file's mtime is used.

### `daily_cost` (`ergonomics/daily_cost.py`)

- **Guarantees**: `check_daily_cost_cap()` terminates the process with `SystemExit` if daily spend meets or exceeds `cap_cents`. It never raises any other exception type for the cap condition.
- **Bypass**: `cap_cents <= 0` disables the check entirely.

---

## Invariants

1. `RunBudget.max_iterations >= 1` always (enforced by `validate()`).
2. `RunBudget.max_tool_calls >= 0` always (enforced by `validate()`).
3. `RunBudget.max_estimated_cost_cents >= 0` always (enforced by `validate()`).
4. `BudgetMonitor._emitted_levels` grows monotonically until `reset()`.
5. `BudgetMonitor._prompted` is set to `True` at most once per run.
6. `CostTracker._parse_runs()` never raises; it silently skips unreadable files.
7. All `CostTracker` reports are derived solely from `.teaagent/runs/*.jsonl` under the configured root.

---

## State Machines

### BudgetMonitor State

```
                  reset()
          ┌────────────────────────────────────────┐
          ▼                                         │
  [IDLE / 0 thresholds emitted]
          │
          │ check(cost_cents) → percent >= 50%
          ▼
  [50% emitted] → BudgetAction.WARN
          │
          │ check(cost_cents) → percent >= 80%
          ▼
  [80% emitted] → BudgetAction.WARN
          │
          │ check(cost_cents) → percent >= 90%
          ▼                                   ┌──────────────────┐
  [90% emitted]                               │ non-interactive  │
          │                                   │ → BudgetAction.  │
          ├──[interactive + on_prompt]────────│   WARN           │
          │   _prompted=True                  └──────────────────┘
          │   on_prompt(payload) → bool
          │     False → BudgetAction.PROMPT_CONFIRM
          │     True  → BudgetAction.WARN
          │
          │ check(cost_cents) → percent >= 100%
          ▼
  [100% emitted] → BudgetAction.SUGGEST_READ_ONLY
```

### RunBudget pre-flight check

```
check_cost_preflight(provider, model, input_chars, max_output_tokens)
        │
        ├─ max_estimated_cost_cents <= 0  ──→ return (no check)
        │
        ├─ estimated > max_estimated_cost_cents ──→ raise BudgetExceededError
        │
        └─ estimated <= max_estimated_cost_cents ──→ return (OK)
```
