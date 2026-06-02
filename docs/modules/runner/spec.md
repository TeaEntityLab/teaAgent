# runner — Behavior Specification

## Overview

The `runner` module is the core agent execution engine. It owns the agent loop: call the decide function, process tool requests, enforce budgets and policy, record audit events, and return a `RunResult`.

---

## Behavior Contract

### What the module guarantees

1. **Every run has exactly one terminal audit event.** Either `run_completed`, `run_failed`, or `run_paused` is always recorded before `run()` returns.
2. **Budget limits are enforced.** If `max_iterations` is exceeded, `run()` returns with status `failed:model_logic`. If cost or tool-call budgets are exceeded, `run()` returns with `failed:budget_exceeded`.
3. **Cancellation is checked before each iteration.** If `cancel_token` is set, `RunCancelledError` is raised and recorded as `run_failed`.
4. **Every tool call has a matching lifecycle audit event.** A `tool_call_started` is always followed by exactly one of: `tool_call_completed`, `tool_call_failed`, `tool_call_blocked`, or `tool_call_denied`.
5. **Observations are append-only within a run.** The `context['observations']` list only grows (or is compacted, never deleted).
6. **The decide function receives updated context on every iteration.** Cost, tokens, and compaction state from the previous iteration are merged into `context` before `decide()` is called again.
7. **`RunResult` is always returned (never raises to caller).** All `AgentHarnessError` and bare `Exception` subclasses are caught, logged to audit, and converted to a failed `RunResult`.

### What the module does NOT guarantee

- Tool execution atomicity — a tool that partially succeeds and then raises `ToolExecutionError` will have its partial effects visible to subsequent tool calls.
- Context size — the compactor reduces observations but cannot guarantee the context fits within `max_context_tokens`.
- Plugin stability — plugin load failures are logged as warnings but do not abort the run.

---

## Invariants

| Invariant | Where enforced |
|-----------|----------------|
| `budget.max_iterations > 0` | `RunBudget.validate()` called in `__init__` |
| `cost_cents` is monotonically non-decreasing during a run | `_assert_cost_budget` called before and after `decide()` |
| `tool_calls` counter equals `len(initial_observations) + number of tool dispatches` | Initialized from `len(initial_observations)`, incremented on every dispatch |
| `compaction_warning_threshold` is clamped to `[0.0, 1.0]` | `__init__` line 90-91 |
| `max_context_tokens` is at least 1 | `__init__` line 92 |
| Budget warning levels (50, 80, 90, 100%) fire at most once per run | `_budget_warning_levels_emitted` set, checked before emitting |
| Compaction warning fires at most once per run | `_compaction_warning_emitted` flag |
| `auto_mode_manager` approval policy override is applied per-iteration, not globally | Lines 387-388: `self.approval_policy = auto_approve_policy` inside loop |

---

## State Machine: Agent Run Loop

```
          ┌──────────────────────────────────────────────────────┐
          │  run() called                                         │
          │  audit: run_started                                   │
          └────────────────────┬─────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  iteration_started   │◄────────────────────┐
                    │  (audit recorded)    │                      │
                    └──────────┬──────────┘                      │
                               │                                  │
              ┌────────────────▼──────────────────┐              │
              │  cancel_token check                │              │
              │  cost budget check (pre-decide)    │              │
              └────────────────┬──────────────────┘              │
                               │ ok                               │
              ┌────────────────▼──────────────────┐              │
              │          decide(context)            │              │
              └────┬──────────────────────┬────────┘              │
                   │ FinalAnswer           │ ToolRequest           │
                   │                      │                       │
    ┌──────────────▼──┐    ┌──────────────▼────────────────┐     │
    │ audit:           │    │ cost check (post-decide)       │     │
    │ run_completed    │    │ file_policy.assert_allowed     │     │
    │                  │    │ plan_validator.validate_write  │     │
    │ return RunResult │    │ auto_mode.validate_tool        │     │
    │ status=completed │    └───────────┬────────────────────┘     │
    └──────────────────┘               │ ok / ToolPermissionError  │
                                       │                           │
                          ┌────────────▼──────────────────┐       │
                          │  approval_policy.assert_allowed│       │
                          └────────┬──────────────────────┘       │
                                   │ raises ToolPermissionError    │
                      ┌────────────▼──────────────────────┐       │
                      │  can_request_approval?             │       │
                      └────┬──────────────────────────┬───┘       │
                     yes   │                          │ no         │
           ┌───────────────▼──┐             ┌─────────▼─────┐     │
           │ approval_handler │             │ record_blocked │     │
           │ call             │             │ re-raise       │     │
           └──────┬───────────┘             └───────────────┘     │
                  │ True/False                                      │
      ┌───────────▼──────────┐   False + no handler               │
      │ approved=True        │──────────────────────────►  return  │
      │ continue to execute  │                            pending  │
      └──────────────────────┘                           approval  │
                  │                                                 │
   ┌──────────────▼────────────────────────────────────────────┐   │
   │  audit: tool_call_started                                  │   │
   │  bind_parent_run_id / bind_tool_call_context               │   │
   │  registry.execute(tool_name, arguments)                    │   │
   └──────────────────────┬────────────────────────────────────┘   │
                          │ ok / ToolExecutionError                 │
              ┌───────────▼──────────────────┐                     │
              │  append observation to context│                     │
              │  audit: tool_call_completed   │                     │
              │         or tool_call_failed   │                     │
              │  checkpoint_store.save        │                     │
              │  compaction check             │                     │
              └───────────┬──────────────────┘                     │
                          │                                         │
                          └─────────────────────────────────────────┘
                                   (next iteration)

  Abnormal exits:
  ─────────────
  AgentHarnessError  →  audit: run_failed  →  return RunResult(failed:category)
  bare Exception     →  audit: run_failed  →  return RunResult(failed:system)
  iterations == max  →  audit: run_failed  →  return RunResult(failed:model_logic)
```

---

## Budget Warning State Machine

```
  cost_cents / max_cost_cents * 100  →  warning_level

  50%  fired? →  emit budget_warning(50)
  80%  fired? →  emit budget_warning(80)
  90%  fired? →  emit budget_warning(90)  →  if BudgetAction.PROMPT_CONFIRM → raise RunCancelledError
  100% fired? →  emit budget_warning(100) →  if BudgetAction.SUGGEST_READ_ONLY → emit budget_read_only_suggested
```

Each level fires at most once per run (guarded by `_budget_warning_levels_emitted`).
