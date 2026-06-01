# Budget Module — Inspection

## Purpose

Provides three-layer cost control:
1. **Pre-flight hard stop** (`RunBudget`) — blocks a run before it starts if estimated cost exceeds the budget.
2. **Runtime soft warnings** (`BudgetMonitor`) — fires configurable callbacks at 50/80/90/100% consumption thresholds during a run.
3. **Historical cost aggregation** (`CostTracker`, `daily_cost`) — reads audit logs to produce cost reports and enforces a daily spending cap.

---

## Files and Responsibilities

| File | Class/Function | Responsibility |
|---|---|---|
| `teaagent/budget.py` | `RunBudget` | Frozen config dataclass; pre-flight cost check |
| `teaagent/budget_monitor.py` | `BudgetMonitor`, `BudgetAction` | Threshold-based warning/prompt callbacks |
| `teaagent/cost_tracker.py` | `CostTracker` | JSONL audit log aggregation and CSV export |
| `teaagent/ergonomics/daily_cost.py` | `daily_spend_cents`, `check_daily_cost_cap` | Daily cap enforcement via RunStore |

---

## Dependencies

### `budget.py`
- `teaagent.errors.BudgetExceededError` — exception type raised on limit exceeded
- `teaagent.llm.estimate_cost_preflight` — LLM cost estimation function

### `budget_monitor.py`
- `teaagent.budget.RunBudget` — holds the configured limits
- `os` (stdlib) — reads `TEAAGENT_NO_SUMMARY`, `TEAAGENT_INTERACTIVE` env vars
- `logging` (stdlib)
- `dataclasses`, `enum` (stdlib)

### `cost_tracker.py`
- `csv`, `io`, `json`, `collections`, `datetime`, `pathlib` (stdlib only)
- No teaagent internal imports

### `ergonomics/daily_cost.py`
- `teaagent.llm.estimate_cost_preflight`
- `teaagent.run_store.RunStore` — lists runs and retrieves per-run events

---

## Exported Symbols

### `budget.py`
- `RunBudget` (dataclass, frozen)

### `budget_monitor.py`
- `BudgetAction` (str Enum: `NONE`, `WARN`, `PROMPT_CONFIRM`, `SUGGEST_READ_ONLY`)
- `BudgetMonitor` (dataclass)

### `cost_tracker.py`
- `CostTracker` (class)

### `ergonomics/daily_cost.py`
- `estimate_run_cost_cents(events) -> float`
- `daily_spend_cents(root) -> float`
- `check_daily_cost_cap(root, cap_cents) -> None`

---

## Entry Points

| Entry Point | Called By |
|---|---|
| `RunBudget.check_cost_preflight()` | Agent runner before each LLM call |
| `BudgetMonitor.check()` | Agent runner after each iteration cost update |
| `BudgetMonitor.from_env()` | Agent runner initialization |
| `check_daily_cost_cap()` | CLI startup / agent initialization |
| `CostTracker.report_all()` | `teaagent cost` CLI command |

---

## Call Graph

```
BudgetMonitor.check(run_id, cost_cents)
  └── _handle_threshold(level, percent, cost_cents, max_cost, run_id)
        ├── on_status(str)               [optional callback]
        └── on_prompt(dict) -> bool      [optional callback, 90% only]

RunBudget.check_cost_preflight(provider, model, input_chars, max_output_tokens)
  └── teaagent.llm.estimate_cost_preflight(provider, model, chars, tokens)

CostTracker.report_all(days)
  ├── report_by_day(days)
  │     └── _parse_runs()
  │           └── _parse_single_run(jsonl_path)
  ├── report_by_model()
  │     └── _parse_runs()
  └── _build_summary(runs)

daily_spend_cents(root)
  └── RunStore(root).list_runs(limit=100)
        └── store.show_run(run_id)
              └── estimate_run_cost_cents(events)
                    └── teaagent.llm.estimate_cost_preflight(...)

check_daily_cost_cap(root, cap_cents)
  └── daily_spend_cents(root)
```

---

## Environment Variables Consumed

| Variable | Effect |
|---|---|
| `TEAAGENT_NO_SUMMARY=1` | Sets `BudgetMonitor.interactive=False` |
| `TEAAGENT_INTERACTIVE=0` | Sets `BudgetMonitor.interactive=False` |
