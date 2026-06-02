# chat_session_controller — Behavior Specification

## Purpose

`chat_session_controller.py` provides `ChatSessionController`, a shared facade used by both CLI and TUI surfaces to execute agent tasks with **consistent correctness guarantees** across the following known issues:

- **CG-01** — Result display: show the final answer on success, show the error message on failure.
- **CG-02** — Undo: record file mutations via `UndoJournal` and provide a `undo_last_run()` method that restores the most recent journaled run.
- **CG-03** — Cost tracking: accumulate `result.cost_cents` into `SessionState.session_cost_cents` across multiple task executions within the same session.
- **CG-09/CG-10** — Suspension honesty and audit: the controller wraps `run_chat_agent` and transparently records to the provided `AuditLogger`.

The module also exports `SessionState` (a mutable shared container for cross-task session data) and `ExecutionResult` (the return value from a single task execution).

---

## Behavior Contract

### `ChatSessionController.execute_task()`

1. **Audit logger creation** — If `audit` is not provided, creates one from `RunStore(root).audit_logger()`.
2. **Undo journal attachment** — If `undo_journal` is not provided, creates `UndoJournal(root)` and attaches it to `audit` via `audit.add_sink(undo_journal)`.
3. **Adapter creation** — If `adapter` is not provided, parses provider and model from `config.model` (format `"provider/model"`) and calls `create_llm_adapter(provider, model)`.
4. **Agent execution** — Calls `run_chat_agent(task, adapter, config, audit, initial_observations, initial_context_extra)`.
5. **Store persistence** — If `audit.path` is set and non-empty, calls `store.logger_for_result(result, audit)` (skipped if audit is a mock without `.path`).
6. **Undo journal save** — If `undo_journal.has_entries` is true, saves journal to `store.undo_path(result.run_id)`.
7. **Result display (CG-01)** — Calls `output_fn(final_answer.content)` on success, `output_fn(error_message or f'[{status}]')` on failure.
8. **Cost accumulation (CG-03)** — `session_state.session_cost_cents += result.cost_cents`.
9. **Observation recording** — Appends `{task, result, cost_cents}` dict to `session_state.observations`.

### `ChatSessionController.undo_last_run()`

1. Finds the latest run with an undo journal via `RunStore.latest_run_with_undo()`.
2. Loads the journal from `store.undo_path(run_id)`.
3. Calls `UndoJournal.restore()`.
4. On success, deletes the undo journal file and reports restored/deleted file counts.
5. On failure, reports error messages per failed file.
6. All exceptions are caught; `output_fn` is called with an error message and `False` is returned.

---

## Invariants

| Invariant | Description |
|-----------|-------------|
| `session_state.session_cost_cents` is monotonically non-decreasing | Cost is only added, never subtracted |
| `session_state.observations` is append-only within a session | Each `execute_task()` call adds exactly one observation entry |
| `output_fn` is always called exactly once per `execute_task()` call | Either the final answer or an error message |
| Undo journal is attached to audit before `run_chat_agent` is called | Guarantees all tool mutations are recorded |
| Store persistence errors are silently swallowed (try/except) | Test mocks with missing `.path` do not break production code |

---

## State Machine — Session Lifecycle

```
Initialize: ChatSessionController(root, output_fn, session_state?)
    │
    ├── session_state = provided or SessionState()
    │   session_state.session_cost_cents = 0.0
    │   session_state.observations = []
    │   session_state.compaction_count = 0
    │   session_state.targeted_files = set()
    │
    ▼
[IDLE — ready for tasks]
    │
    ├── execute_task(task, config, ...)
    │     ├── Setup: audit, undo_journal, adapter (if not provided)
    │     ├── run_chat_agent(...)
    │     │     └── Returns RunResult
    │     ├── Store: persist audit events + undo journal
    │     ├── Display: output_fn(answer or error)
    │     └── Accumulate: session_cost_cents += result.cost_cents
    │           observations.append(...)
    │
    ├── execute_task(task2, ...)  [repeated N times]
    │
    └── undo_last_run()
          ├── Find: store.latest_run_with_undo()
          ├── Load: UndoJournal from undo_path
          ├── Restore: journal.restore()
          └── Report: output_fn(count of restored/deleted files)

[Session ends when controller is garbage collected — no explicit close()]
```

---

## SessionState — Field Semantics

| Field | Type | Initial | Update Rule |
|-------|------|---------|-------------|
| `session_cost_cents` | `float` | `0.0` | `+= result.cost_cents` per task |
| `observations` | `list[dict]` | `[]` | Appended per task, never truncated by controller |
| `compaction_count` | `int` | `0` | Set by caller (TUI or REPL), not touched by controller |
| `targeted_files` | `set[Path]` | `set()` | Set by caller, not touched by controller |
