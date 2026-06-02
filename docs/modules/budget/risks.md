# Budget Module — Risks, Failure Modes, and Edge Cases

## Risk Vectors

### BUD-R-001: Dead code in `BudgetMonitor.check()` — logic after early return
**File**: `budget_monitor.py`, lines 103–119

After the `return highest_action` on line 103, there is an unreachable block (lines 104–119) that duplicates the threshold iteration logic but uses an older single-return pattern. This dead code is never executed. The duplicate was left after a refactor and would cause confusion if someone modifies the visible lower block thinking it is active.

**Risk**: Maintenance confusion; unintended behavior if the dead block is accidentally activated (e.g., via reordering).

---

### BUD-R-002: `BudgetMonitor` — `on_prompt` returning `False` does NOT halt execution
**File**: `budget_monitor.py`, lines 186–188

When `on_prompt` returns `False` (user declined), the action returned is `BudgetAction.PROMPT_CONFIRM`. The monitor itself does **not** stop the run — it is the caller's responsibility to check the return value and abort. If the caller ignores the return value, the run continues past the 90% threshold with no user approval.

**Risk**: Silent over-budget execution if caller does not act on `PROMPT_CONFIRM`.

---

### BUD-R-003: `RunBudget.validate()` is never called automatically
**File**: `budget.py`, lines 21–27

`validate()` is a public method but is not called in `__post_init__` or `__init__`. A caller can construct a `RunBudget` with `max_iterations=0` or negative values and the object will exist without any validation error until `validate()` is explicitly called.

**Risk**: Runtime surprises if invalid `RunBudget` instances escape construction.

---

### BUD-R-004: Pre-flight estimate is approximate
**File**: `budget.py`, lines 38–45; `ergonomics/daily_cost.py`, lines 12–32

`check_cost_preflight` uses `estimate_cost_preflight(provider, model, approx_input_chars, max_output_tokens)`. In `daily_cost.py`, the estimate always uses hardcoded values (`approx_input_chars=12_000`, `max_output_tokens=2048`) regardless of actual run parameters. These are rough approximations — real costs may differ significantly from estimates, especially for long-context runs or non-default models.

**Risk**: Daily cap may be under- or over-enforced depending on actual vs. estimated run costs.

> **See also:** [context/risks.md](../context/risks.md) — token estimation inaccuracies

---

### BUD-R-005: `CostTracker` uses file mtime fallback for timestamp
**File**: `cost_tracker.py`, lines 75–79

If a JSONL log file has no `run_started` event, the file's modification time is used as `created_at`. On systems where files are copied or backed up, mtime can be incorrect, causing runs to appear on the wrong day in `report_by_day`.

**Risk**: Historical cost reports may mis-attribute runs to incorrect days.

---

### BUD-R-006: `CostTracker` silently drops malformed JSONL lines
**File**: `cost_tracker.py`, lines 57–60

`json.JSONDecodeError` is caught and the line is skipped. Partially written or corrupted audit logs are silently ignored. There is no alerting or warning logged when this happens.

**Risk**: Cost data loss without any user-visible signal.

---

### BUD-R-007: `check_daily_cost_cap` uses `SystemExit`, not a catchable exception
**File**: `ergonomics/daily_cost.py`, lines 52–59

`SystemExit` bypasses normal exception handling in most frameworks. If `check_daily_cost_cap` is called inside a thread or long-lived process, the `SystemExit` may not cleanly shut down all resources (audit logs, open file handles, etc.).

**Risk**: Unclean shutdown when daily cap is exceeded in threaded contexts.

---

### BUD-R-008: `BudgetMonitor.from_env()` has no error handling for malformed env vars
**File**: `budget_monitor.py`, lines 59–72

The env var values are compared as strings via `.lower()`. Any non-empty string other than `'1'`, `'true'`, `'yes'`, or `'0'` is treated as truthy/interactive. This is generally safe but the logic for `TEAAGENT_NO_SUMMARY` and `TEAAGENT_INTERACTIVE` uses different comparison semantics (one checks for truthy values, the other checks for the single value `'0'`).

**Risk**: Subtle misconfiguration if operators set unexpected env var values.

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| `max_estimated_cost_cents = 0` | Pre-flight check is skipped; monitoring returns `NONE` for all threshold checks |
| Cost is exactly at threshold boundary (e.g., exactly 50%) | Threshold fires — comparison is `percent < level` so 50.0 is NOT less than 50.0; fires at >= |
| `BudgetMonitor` reused across multiple runs without `reset()` | Previously emitted levels are not re-fired; new run gets no 50/80/90/100% warnings for thresholds already crossed in prior run |
| Empty `.teaagent/runs/` directory | `CostTracker._parse_runs()` returns `[]`; all reports return zero-run summaries |
| `CostTracker.export_csv` with no `total` key in data | Uses `.get('total', {})` default; produces empty rows without error |
| `estimate_run_cost_cents` with no `run_started` event | Defaults to `provider='gpt'`, `model='default'`; estimate may be inaccurate |
