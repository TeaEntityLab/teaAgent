# TeaAgent Error Handling — 2026-06-02

What happens at each failure point: what is recorded, what is returned, whether the
run can recover, and what state is left behind.

---

## Error Taxonomy (`teaagent/errors.py`)

| Exception | `ErrorCategory` | `RunResult.status` | Recoverable? |
|---|---|---|---|
| `BudgetExceededError` | `model_logic` | `failed:model_logic` | Yes — increase budget, resume |
| `ToolValidationError` | `model_logic` | `failed:model_logic` | Yes — retry with better model |
| `ToolPermissionError` | `permission` | `failed:permission` or `pending_approval` | Conditional |
| `ToolExecutionError` | `system` | loop continues (obs appended) | Loop-local |
| `RunCancelledError` | `system` | `failed:system` | Yes — resume |
| Unexpected `Exception` | `system` | `failed:system` | No |

---

## 1. Agent Fails (LLM returns invalid response)

**Path:** `parse_model_decision()` raises `ToolValidationError`

```
decide(context) raises ToolValidationError
  ├─ AgentRunner catches AgentHarnessError
  ├─ audit.record('run_failed', category='model_logic', message=…)
  ├─ _emit_summary()
  └─ return RunResult(status='failed:model_logic', error_message=…)
```

**State left:** Audit JSONL has `run_failed` event. Checkpoint (if any) still valid
for resume. UndoJournal has committed entries for completed writes up to this point.

---

## 2. Approval Denied

**Subcase A — Interactive denial (handler returns False)**

```
approval_handler returns False
  ├─ audit.record('tool_call_denied')
  └─ ToolPermissionError re-raised → caught by AgentHarnessError handler
       ├─ audit.record('run_failed', category='permission')
       └─ RunResult(status='failed:permission')
```

**Subcase B — No handler (headless / API mode)**

```
approval_handler is None
  ├─ audit.record('run_paused', status='pending_approval')
  ├─ checkpoint_store.save(run_id, context)
  └─ return RunResult(status='pending_approval')
       metadata contains full approval_request dict
```

User must `resume <run_id>` after approving, or the run is abandoned.

---

## 3. Cost Exceeded

**Subcase A — Hard limit reached**

```
_assert_cost_budget(cost_cents) raises BudgetExceededError
  → caught by AgentHarnessError handler
  → audit.record('run_failed', category='model_logic', message='cost budget exceeded')
  → RunResult(status='failed:model_logic')
```

**Subcase B — Budget warning at 90% threshold (PROMPT_CONFIRM)**

```
BudgetMonitor.check_at_threshold returns PROMPT_CONFIRM
  → audit.record('budget_prompt', …, approved=False)
  → RunCancelledError raised
  → audit.record('run_failed', category='system')
  → RunResult(status='failed:system')
```

No checkpoint is saved automatically on cost failure. The run must be restarted
with a larger budget.

---

## 4. Audit Write Fails

```
path.open('a').write() raises OSError
  ├─ self._disk_error = exc  (with timestamp)
  ├─ AuditEvent('_disk_write_error') appended to in-memory list
  └─ run CONTINUES — audit failures are non-fatal

After _disk_error_cooldown_seconds (30 s):
  disk writes are retried on the next record() call
```

**State:** In-memory events list remains complete. JSONL file on disk is incomplete
(missing events from the error window). Chain integrity verification will detect the
gap. Sinks (UndoJournal, progress) still fire because they receive the in-memory
`AuditEvent` regardless of disk status.

---

## 5. Tool Crashes (`ToolExecutionError`)

```
registry.execute() raises ToolExecutionError
  tool_calls += 1
  error_observation = {call_id, tool_name, error: str(exc)}
  context['observations'].append(error_observation)
  audit.record('tool_call_failed', …)
  UndoJournal: discard pending entry (no snapshot committed)
  checkpoint_store.save()
  continue loop  ← run does NOT terminate; model sees the error and can retry
```

**State:** The errored tool left no file system changes (write tools fail atomically
or partially — partial writes are not snapshotted). The model receives the error text
as an observation and can choose a different approach.

---

## 6. Cancel Token Set

```
cancel_token.is_set() checked at top of each iteration
  └─ RunCancelledError raised
       └─ caught by AgentHarnessError handler
            ├─ audit.record('run_failed', category='system', message='run cancelled by cancel token')
            └─ RunResult(status='failed:system')
```

**State:** Checkpoint holds last clean context. UndoJournal has completed writes.
Run can be resumed with `resume <run_id>`.

---

## 7. Iteration Budget Exceeded

```
while iterations < budget.max_iterations: exhausted
  audit.record('run_failed', category='model_logic', message='iteration budget exceeded')
  _emit_summary()
  return RunResult(status='failed:model_logic', error_message='iteration budget exceeded')
```

---

## 8. Audit Sink Fails (UndoJournal, progress sink, OTel)

```
for sink in sinks:
    try:
        sink(event)
    except Exception as exc:
        logger.error('Audit sink … failed: %s', exc)
        failed_sinks.append((sink, exc))
logger.warning('%d audit sink(s) failed')
```

Sink failures are logged but **do not propagate**. The run continues. The UndoJournal
will have an incomplete snapshot if it failed; `/undo` may produce partial results.

---

## 9. File Policy Violation

```
file_policy.assert_allowed(tool_name, arguments) raises ToolPermissionError
  reason_code = DenialReasonCode.FILE_POLICY_DENIED
  ├─ approval_manager.can_request_approval(destructive)?
  │   ├─ True  → trigger interactive approval flow
  │   └─ False → record_blocked(), re-raise
  └─ run fails with status='failed:permission'
```

---

## 10. State Recovery Matrix

| Failure | Audit complete? | Undo available? | Resumable? | Action |
|---|---|---|---|---|
| LLM invalid response | Yes | Yes (partial) | Yes | `resume <run_id>` |
| Approval denied (interactive) | Yes | Yes | No | Restart with approval |
| Approval paused (headless) | Yes | Yes | Yes | `approve` then `resume <run_id>` |
| Cost exceeded | Yes | Yes | Yes | Increase budget, `resume` |
| Tool crash | Yes | Yes | Yes | `resume <run_id>` |
| Cancel token | Yes | Yes | Yes | `resume <run_id>` |
| Audit disk write fails | Partial | Yes (in-memory) | Yes | Fix disk, `resume` |
| Iteration limit | Yes | Yes | Yes | Increase `max_iterations`, `resume` |
| UndoJournal corrupted | Yes | No | No | Manual git revert |
| Unexpected exception | Yes | Partial | No | Investigate, restart |

---

## 11. Error Paths in TUI Commands

```
TUI handle_command(raw_command)
  ├─ shlex.split fails → output_fn('error: …') → return True (loop continues)
  ├─ unknown command → output_fn('error: unknown command') → return True
  ├─ _run_agent_task raises OSError/ValueError/TypeError/RuntimeError
  │   └─ logger.warning(); _print_json({'error': …, 'status': 'failed:system'})
  ├─ resume / undo: FileNotFoundError/ValueError → output_fn('error: …') → return True
  └─ EOFError / KeyboardInterrupt → _stop_file_watcher(); return False (exit loop)
```

The TUI is designed to survive errors in individual commands and return the user
to the prompt.

---

## 12. Git Checkpoint Failure Modes

```
/checkpoint:
  git stash push -m <ref>
    ├─ returncode == 0 → checkpoint_created = True
    ├─ 'No local changes to save' → checkpoint_created = True (clean workspace)
    └─ non-zero → output_fn('warning: checkpoint failed: …')

/undo:
  git stash list → verify stash exists
  git stash show → list stashed files
  git checkout HEAD -- <files> → restore tracked files
  git stash pop → apply stash
    ├─ success → output 'checkpoint restored'
    └─ conflicts → 'stash pop had conflicts — checkpoint preserved' (manual resolution required)
```

If git is not in PATH, `FileNotFoundError` → `output_fn('error: git not found in PATH')`.
