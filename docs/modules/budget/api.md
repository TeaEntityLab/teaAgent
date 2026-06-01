# Budget Module — Public API Reference

## `budget.py`

### `class RunBudget`

```python
@dataclass(frozen=True)
class RunBudget:
    max_iterations: int = 25
    max_tool_calls: int = 25
    max_estimated_cost_cents: int = 100
```

Frozen dataclass representing hard limits for a single agent run. All fields have defaults; construct with keyword arguments to override.

**Fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `max_iterations` | `int` | `25` | Maximum number of agent loop iterations |
| `max_tool_calls` | `int` | `25` | Maximum total tool calls across all iterations |
| `max_estimated_cost_cents` | `int` | `100` | Pre-flight cost ceiling in US cents |

---

#### `RunBudget.validate() -> None`

**Pre-conditions**: None  
**Post-conditions**: Returns `None` if all limits are valid  
**Raises**: `ValueError` if `max_iterations < 1`, `max_tool_calls < 0`, or `max_estimated_cost_cents < 0`

---

#### `RunBudget.check_cost_preflight(provider, model, approx_input_chars, max_output_tokens) -> None`

**Signature**:
```python
def check_cost_preflight(
    self,
    provider: str,
    model: str,
    approx_input_chars: int,
    max_output_tokens: int,
) -> None
```

**Pre-conditions**:
- `provider` and `model` must be strings recognized by `teaagent.llm.estimate_cost_preflight`
- `approx_input_chars >= 0`, `max_output_tokens >= 0`

**Post-conditions**: Returns `None` if estimated cost is within budget  
**Raises**: `BudgetExceededError` if `estimated_cost > max_estimated_cost_cents`  
**Bypass**: If `max_estimated_cost_cents <= 0`, returns immediately without checking

---

## `budget_monitor.py`

### `class BudgetAction` (str Enum)

```python
class BudgetAction(str, Enum):
    NONE = 'none'
    WARN = 'warn'
    PROMPT_CONFIRM = 'prompt_confirm'
    SUGGEST_READ_ONLY = 'suggest_read_only'
```

Priority order (ascending): `NONE < WARN < PROMPT_CONFIRM < SUGGEST_READ_ONLY`

---

### `class BudgetMonitor`

```python
@dataclass
class BudgetMonitor:
    budget: RunBudget
    thresholds: tuple[float, ...] = (50.0, 80.0, 90.0, 100.0)
    interactive: bool = True
    on_status: Optional[Callable[[str], None]] = None
    on_prompt: Optional[Callable[[dict[str, Any]], bool]] = None
```

**Fields**

| Field | Type | Description |
|---|---|---|
| `budget` | `RunBudget` | The budget limits to monitor against |
| `thresholds` | `tuple[float, ...]` | Percentage thresholds to fire at |
| `interactive` | `bool` | If `False`, skips `on_prompt` at 90% |
| `on_status` | `Optional[Callable[[str], None]]` | Called with a status string at each threshold |
| `on_prompt` | `Optional[Callable[[dict], bool]]` | Called at 90% if interactive; returns `True` to continue |

---

#### `BudgetMonitor.from_env(budget) -> BudgetMonitor` (classmethod)

**Signature**:
```python
@classmethod
def from_env(cls, budget: RunBudget) -> 'BudgetMonitor'
```

Reads `TEAAGENT_NO_SUMMARY` and `TEAAGENT_INTERACTIVE` to set `interactive`.  
Returns a new `BudgetMonitor` instance.

---

#### `BudgetMonitor.check(*, run_id, cost_cents) -> BudgetAction`

**Signature**:
```python
def check(self, *, run_id: str, cost_cents: float) -> BudgetAction
```

**Pre-conditions**: `cost_cents >= 0.0`  
**Post-conditions**: Returns the highest-priority `BudgetAction` for any newly crossed thresholds. Returns `BudgetAction.NONE` if no new thresholds crossed.  
**Side effects**: Adds crossed threshold levels to `_emitted_levels`; may call `on_status` and `on_prompt`; sets `_prompted = True` on first prompt call.

**`on_prompt` payload dict**:
```python
{
    'run_id': str,
    'percent': float,
    'cost_cents': float,
    'max_cost_cents': float,
}
```

---

#### `BudgetMonitor.check_at_threshold(*, run_id, cost_cents, threshold) -> BudgetAction`

Force-fire a specific threshold level. Primarily for testing.

**Signature**:
```python
def check_at_threshold(self, *, run_id: str, cost_cents: float, threshold: int) -> BudgetAction
```

---

#### `BudgetMonitor.reset() -> None`

Clears `_emitted_levels` and `_prompted`. Allows monitor reuse across runs.

---

## `cost_tracker.py`

### `class CostTracker`

```python
class CostTracker:
    def __init__(self, root: str | Path = '.') -> None
```

Reads from `<root>/.teaagent/runs/*.jsonl` audit logs. All methods are read-only.

---

#### `CostTracker.report_by_label(label) -> dict`

**Signature**:
```python
def report_by_label(self, label: str) -> dict[str, Any]
```

**Returns**: Summary dict for all runs matching the given label.

**Output shape**:
```python
{
    'runs': int,
    'cost_cents': float,
    'input_tokens': int,
    'output_tokens': int,
    'run_ids': list[str],  # absent when runs == 0
}
```

---

#### `CostTracker.report_by_day(days=30) -> dict`

**Returns**:
```python
{
    'days': int,
    'by_day': {
        'YYYY-MM-DD': { 'runs': int, 'cost_cents': float, ... },
        ...
    }
}
```

---

#### `CostTracker.report_by_model() -> dict`

**Returns**:
```python
{
    'by_model': {
        'model_name': { 'runs': int, 'cost_cents': float, ... },
        ...
    }
}
```

---

#### `CostTracker.report_all(days=30) -> dict`

**Returns**:
```python
{
    'by_label': { label: summary_dict, ... },
    'by_day':   { 'YYYY-MM-DD': summary_dict, ... },
    'by_model': { model: summary_dict, ... },
    'total':    summary_dict,
}
```

---

#### `CostTracker.export_csv(data) -> str` (staticmethod)

**Signature**:
```python
@staticmethod
def export_csv(data: dict[str, Any]) -> str
```

**Pre-conditions**: `data` should be the output of `report_all()`  
**Returns**: CSV string with sections for totals, by-label, by-day, by-model  
**Raises**: Nothing — missing keys produce empty rows

---

## `ergonomics/daily_cost.py`

### `estimate_run_cost_cents(events) -> float`

```python
def estimate_run_cost_cents(events: list[dict[str, Any]]) -> float
```

**Pre-conditions**: `events` is a list of audit event dicts from a run log  
**Post-conditions**: Returns a non-negative float in US cents  
**Returns**: `0.0` on any exception during estimation  
**Note**: Always uses fixed `approx_input_chars=12_000`, `max_output_tokens=2048` regardless of actual run content

---

### `daily_spend_cents(root) -> float`

```python
def daily_spend_cents(root: str | Path) -> float
```

**Returns**: Estimated total spend in cents for today's date. Returns `0.0` if no runs found for today.

---

### `check_daily_cost_cap(root, cap_cents) -> None`

```python
def check_daily_cost_cap(root: str | Path, cap_cents: int) -> None
```

**Pre-conditions**: `cap_cents` is an integer  
**Post-conditions**: Returns `None` if spend is below cap  
**Raises**: `SystemExit` (not a regular exception) if `spent >= cap_cents`  
**Bypass**: No-op if `cap_cents <= 0`
