# runner — Public API Reference

## Data Models

### `ToolRequest`

```python
@dataclass(frozen=True)
class ToolRequest:
    tool_name: str                    # Name of the tool to call
    arguments: dict[str, Any]         # Tool arguments
    call_id: str                      # Unique call identifier (uuid4 hex, auto-generated)
    reasoning: str | None = None      # Optional model reasoning for the call
```

Immutable. `call_id` defaults to `uuid4().hex` if not provided.

---

### `FinalAnswer`

```python
@dataclass(frozen=True)
class FinalAnswer:
    content: str                      # The model's final textual answer
    metadata: dict[str, Any]          # Optional metadata dict (default: {})
```

When the `decide()` function returns this type, the run loop terminates with `status='completed'`.

---

### `Decision`

```python
Decision = Union[ToolRequest, FinalAnswer]
```

The return type of `DecisionFn`. Exactly one of `ToolRequest` or `FinalAnswer`.

---

### `DecisionFn`

```python
DecisionFn = Callable[[dict[str, Any]], Decision]
```

**Pre-conditions:**
- Receives `context: dict[str, Any]` with at minimum:
  - `context['task']`: the task string
  - `context['observations']`: list of previous tool call observations
- May read `context.get('decision_summary')`, `context.get('compacted_summary')`, `context.get('memory_keys')`.

**Post-conditions:**
- Must return either a `FinalAnswer` or a `ToolRequest`.
- May set `context['_cost_cents']`, `context['_input_tokens']`, `context['_output_tokens']` for budget tracking.

---

### `ApprovalRequest`

```python
@dataclass(frozen=True)
class ApprovalRequest:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    annotations: dict[str, bool]          # {'read_only', 'destructive', 'idempotent'}
    run_id: Optional[str] = None
    workspace_secret: Optional[bytes] = None
```

**Method:**

```python
def to_dict(self) -> dict[str, Any]
```

Returns serializable dict with `argument_digest` (HMAC-SHA256 if `workspace_secret` is set, SHA256 prefix otherwise) and `argument_digest_version` (`'v2'` or `'v1'`). Arguments are redacted via `redact_tool_arguments()`.

---

### `ApprovalHandler`

```python
ApprovalHandler = Callable[[ApprovalRequest], bool]
```

Called when a tool call requires human-in-the-loop approval. Must return `True` (approved) or `False` (denied).

---

### `BudgetPromptHandler`

```python
BudgetPromptHandler = Callable[[dict[str, Any]], bool]
```

Called when cost reaches 90% of budget. Receives a payload dict. Must return `True` to continue or `False` to cancel.

---

### `RunResult`

```python
@dataclass(frozen=True)
class RunResult:
    run_id: str
    final_answer: Optional[FinalAnswer]   # None on failure or pending_approval
    iterations: int                       # Total iterations executed
    tool_calls: int                       # Total tool call attempts (including failures)
    status: str                           # See status values below
    metadata: dict[str, Any]             # Additional metadata
    error_message: Optional[str]          # Set on failure
    cost_cents: float                     # Accumulated cost in cents
    input_tokens: int                     # Accumulated input tokens
    output_tokens: int                    # Accumulated output tokens
```

**Status values:**

Actual status strings are constructed from the `ErrorCategory` enum (`teaagent/errors.py`):

| Value | Meaning |
|-------|---------|
| `'completed'` | `FinalAnswer` returned by decide |
| `'pending_approval'` | Run paused, waiting for human approval |
| `'failed:model_logic'` | Iteration budget exhausted, model logic error, or budget exceeded |
| `'failed:permission'` | Tool was blocked and cannot be approved |
| `'failed:system'` | Unexpected exception or run cancelled |
| `'failed:transient'` | Transient error (retryable) |

---

## Classes

### `AgentRunner`

**Module:** `teaagent.runner._core`

The main run loop orchestrator.

#### `__init__`

```python
AgentRunner(
    *,
    registry: ToolRegistry,
    audit: AuditLogger,
    budget: Optional[RunBudget] = None,
    approval_policy: Optional[ApprovalPolicy] = None,
    approval_handler: Optional[ApprovalHandler] = None,
    budget_prompt_handler: Optional[BudgetPromptHandler] = None,
    budget_monitor: Optional[BudgetMonitor] = None,
    compactor: Optional[ContextCompactor] = None,
    compact_after_observations: int = 20,
    compaction_warning_threshold: float = 0.6,
    max_context_tokens: int = 200000,
    checkpoint_store: Any = None,
    cancel_token: Optional[threading.Event] = None,
    file_policy: Optional[FilePolicy] = None,
    auto_mode_config: Optional[AutoModeConfig] = None,
    jit_state: Optional[JITApprovalState] = None,
    workspace_root: Optional[Path] = None,
    require_plan: bool = False,
    skip_plan_check: bool = False,
    show_summary: bool = True,
    scratchpad: Any = None,
    decision_log: Any = None,
) -> None
```

**Pre-conditions:**
- `registry` must be a valid `ToolRegistry`.
- `audit` must be a valid `AuditLogger`.
- `budget.validate()` must pass (called in `__init__`).

**Post-conditions:**
- `self.approval_manager` is initialized.
- `self.plan_validator` is initialized.
- `self.auto_mode_manager` is initialized.
- If `workspace_root` is provided, `load_plugins(registry)` is called.
- If `permission_mode == READ_ONLY`, lint errors are collected and stored on `plan_validator`.

**Raises:**
- Any exception from `budget.validate()` if budget is invalid.

---

#### `run`

```python
def run(
    self,
    *,
    task: str,
    decide: DecisionFn,
    run_id: Optional[str] = None,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    initial_context_extra: Optional[dict[str, Any]] = None,
    run_started_extra: Optional[dict[str, Any]] = None,
) -> RunResult
```

**Pre-conditions:**
- `task` must be a non-empty string.
- `decide` must be callable and return `Decision`.
- If `run_id` is provided, it should be unique to avoid audit record collisions.

**Post-conditions:**
- Always returns a `RunResult`; never raises.
- Exactly one terminal audit event (`run_completed`, `run_failed`, or `run_paused`) is recorded.
- `RunResult.run_id` equals `run_id` if provided, or a new `uuid4().hex`.

**Raises:** Nothing (all exceptions are caught internally).

---

### `RunnerApprovalCoordinator` (runner._approval_manager)

Internal helper. Not part of the public `runner` package API (not re-exported from `__init__.py`).

#### `can_request_approval(destructive: bool) -> bool`

Returns `True` only if `destructive=True` and `permission_mode == PROMPT`.

#### `create_approval_request(...) -> ApprovalRequest`

Builds an `ApprovalRequest` with an optional workspace HMAC secret for v2 digest.

#### `handle_approval_request(...) -> bool`

Emits `tool_call_pending_approval` audit event. Calls `approval_handler` if set. Returns `True` if approved, `False` otherwise. Records `run_paused` and saves checkpoint when no handler is set.

#### `record_blocked(...) -> None`

Emits `tool_call_blocked` audit event.

---

### `AutoModeManager` (runner._auto_mode_manager)

Internal helper.

#### `is_enabled() -> bool`
#### `record_iteration() -> None`
#### `record_tool_call() -> None`
#### `is_tool_allowed(tool_name: str) -> bool`

#### `validate_tool_allowed(tool_name: str) -> None`

**Raises:** `ToolPermissionError` if auto mode is active and `tool_name` is not allowed.

#### `get_auto_approve_policy() -> Optional[ApprovalPolicy]`

Returns `ApprovalPolicy(permission_mode=DANGER_FULL_ACCESS, allow_all_destructive=True, full_access_acknowledged=True)` when auto mode is active, `None` otherwise. The `AutoModeGuard` still scopes which tools can use that temporary policy.

#### `summary() -> dict[str, Any]`

Returns auto mode activity summary from `AutoModeGuard.summary()`.

---

### `PlanValidator` (runner._plan_validator)

Internal helper.

#### `set_plan_contract(plan_contract: Any) -> None`
#### `set_read_only_lint_errors(errors: list[Any]) -> None`
#### `get_plan_contract() -> Any`

#### `validate_write_allowed(*, tool_name: str, context: dict[str, Any]) -> None`

Delegates to `governance.plan_gate.assert_write_allowed`. Raises `ToolPermissionError` if write is not allowed under the current plan contract.

#### `check_read_only_lint_errors() -> Optional[str]`

Returns an error string (blocking message) if `permission_mode == READ_ONLY` and lint errors are present, otherwise `None`.
