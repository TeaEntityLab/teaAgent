# runner — Risk Vectors, Failure Modes, Edge Cases, Known Issues

## Risk Vectors

### RUN-R-001: Policy override in auto mode (HIGH)

**File:** `_core.py:387-388`

```python
auto_approve_policy = self.auto_mode_manager.get_auto_approve_policy()
if auto_approve_policy is not None:
    self.approval_policy = auto_approve_policy
```

**Risk:** `self.approval_policy` is mutated in-place on the `AgentRunner` instance every time a tool call is processed while auto mode is active. This means the policy for subsequent non-auto-mode tool calls in the same run is permanently overwritten with a `danger-full-access` auto-approval policy. If auto mode is toggled off mid-run, the old policy is never restored.

**Impact:** Destructive tools may be auto-approved after auto mode exits if the instance is reused.

---

### RUN-R-002: Bare exception swallowing (`# pragma: no cover`) (MEDIUM)

**File:** `_core.py:556-582`

```python
except Exception as exc:  # pragma: no cover - defensive boundary
```

The catch-all `except Exception` silently converts any unexpected error (including programming errors, `AttributeError`, etc.) into a `failed:SYSTEM` `RunResult`. The `# pragma: no cover` comment means this path is never tested. Bugs in the run loop body will be swallowed rather than propagated.

---

### RUN-R-003: `tool_calls` counter initialisation includes replayed observations (LOW/CORRECTNESS)

**File:** `_core.py:302`

```python
tool_calls = len(observations)
```

For resumed runs, `initial_observations` pre-populates observations. The counter is seeded from `len(observations)` which means the `max_tool_calls` budget check on line 366 counts replayed calls against the budget, potentially allowing fewer new tool calls than intended for resumed runs.

---

### RUN-R-004: Double cost-budget assertion (LOW/REDUNDANT)

**File:** `_core.py:321` and `_core.py:334`

`_assert_cost_budget` is called twice per iteration — once before `decide()` and once after. The second check occurs because `cost_cents` is updated from `context.get('_cost_cents', cost_cents)` after the `decide()` call. However, if `_cost_cents` is set by `decide()` to a value exceeding the budget, the exception raised on line 334 will be caught by `except AgentHarnessError` (line 529) and converted to a `run_failed` event with a `budget_exceeded` status, which is the correct behavior. There is no real risk — this is belt-and-suspenders.

---

### RUN-R-005: Context mutation by `decide()` function (MEDIUM)

**File:** `_core.py:322-325`

```python
cost_cents = context.get('_cost_cents', cost_cents)
input_tokens = context.get('_input_tokens', input_tokens)
output_tokens = context.get('_output_tokens', output_tokens)
```

The runner reads cost/token accounting from the shared `context` dict populated by the `decide()` function. If `decide()` sets these keys to negative values, garbage, or forgets to set them, the budget checks and audit records will be wrong. There is no validation of these values.

---

### RUN-R-006: `file_policy.assert_allowed` on wrong tool (MEDIUM)

**File:** `_core.py:375-379`

```python
if self.file_policy is not None:
    self.file_policy.assert_allowed(
        tool_name=decision.tool_name,
        arguments=decision.arguments,
    )
```

`file_policy` is checked before `approval_policy`. A tool that passes `file_policy` but fails `approval_policy` will be silently allowed for file-policy purposes but still blocked by approval. The audit sequence will show `tool_call_started` was never emitted, which is correct, but the `file_policy` check occurs even for tools that would be policy-blocked, which is redundant work.

---

### RUN-R-007: `ToolPermissionError` re-raised without proper audit event (LOW)

**File:** `_core.py:451-458`

```python
if not approved:
    if self.approval_manager.approval_handler is None:
        ...
        return RunResult(status='pending_approval')
    raise  # re-raises ToolPermissionError
```

When `approval_handler` returns `False` (explicit denial) and `approval_handler is not None`, the `ToolPermissionError` is re-raised. This is caught by `except AgentHarnessError` (line 529) and recorded as `run_failed`. The audit will show a `tool_call_denied` event followed by `run_failed`, which is technically correct but may surprise operators who expect `run_paused`.

---

### RUN-R-008: Thread safety of `approval_policy` mutation (MEDIUM)

**File:** `_core.py:388`

```python
self.approval_policy = auto_approve_policy
```

`AgentRunner` is not documented as thread-safe and does not use locks. However, `run()` holds no lock around the policy swap. If the same `AgentRunner` instance is shared across threads (unlikely in practice, but possible), the policy assignment is not atomic.

---

### RUN-R-009: Plugin load failure only logs a warning (LOW)

**File:** `_core.py:124-129`

```python
plugin_result = load_plugins(registry)
if not plugin_result.ok:
    logger.warning(...)
```

Plugin load failures are silently swallowed. A plugin that was expected to register a required tool will not appear in the registry, and the first call to that tool will fail with a `ToolNotFoundError` rather than a clear initialization error.

---

### RUN-R-010: `compactor.compact()` replaces observations list, may lose in-flight context (LOW)

**File:** `_core.py:514-528`

Context compaction replaces `context['observations']` with a compacted version in the same iteration as a successful tool call. If the decide function for the next iteration fails to process the injected `[System: Context compaction completed...]` message, the agent may behave as if it never received the most recent tool result.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `initial_observations` is not empty and tool_calls budget is small | Replayed observations count against `max_tool_calls`. Run may exhaust tool budget before executing any new tool. |
| `decide()` never returns `FinalAnswer` but also never raises | Loop runs until `max_iterations`, then returns `failed:MODEL_LOGIC` |
| `approval_handler` returns `True` after receiving a `pending_approval` checkpoint | The run must be resumed from the checkpoint; re-submitting to the same `AgentRunner` instance will not re-check the stored approval |
| `workspace_root=None` | `_emit_summary()` returns immediately (line 263); no summary is produced |
| `BudgetMonitor.check_at_threshold()` raises | Not caught; will propagate as `AgentHarnessError` if it subclasses it, or as bare Exception otherwise |
| `file_lock` deadlock on audit file | `AuditLogger` acquires `file_lock(path)` inside `record()`. If `_core.py` holds any lock at that point, a deadlock is possible. Currently no lock is held. |

---

## Known Issues

None explicitly documented in source. See risk items above for issues identified from code inspection.
