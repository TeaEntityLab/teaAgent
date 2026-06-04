# TICKET-12 — TUI Adopts `ChatSessionController`
**Priority:** P1 | **Size:** M | **CG Findings:** CG-11, CG-12, CG-15
**Human Review Required:** touches undo + cost

## Progress

- 2026-06-04: Current code imports and uses `ChatSessionController` from the
  TUI surface, stores session cost in controller state, and routes TUI `/undo`
  through `ChatSessionController.undo_last_run()` before checkpoint fallback.
- Verification evidence in this package includes
  `tests/test_tui.py::test_tui_session_cost_accumulates`,
  `tests/test_tui.py::test_tui_handle_undo_calls_controller_first`, and
  `tests/test_tui.py::test_tui_undo_uses_journal`.
- Treat this ticket as fixed in the current branch, with release-profile
  verification still required before claiming production readiness.

> **Land TICKET-14 first** (un-masking test). The stop-gap (Step A below) can
> ship immediately and independently.

---

## Root Cause Analysis

### CG-12 (root cause)
`ChatSessionController` (`teaagent/chat_session_controller.py`) was introduced
to unify CLI and TUI execution. Its docstring at lines 3-5 and 43-45 claims it
"unifies the execution logic between CLI and TUI surfaces." However,
`tui/__init__.py` does not import or use it — `_run_agent_task` at
[`tui/__init__.py:842`](../../teaagent/tui/__init__.py) calls `run_chat_agent`
directly.

### CG-11 (symptom: cost $0.00)
`self._session_cost_cents` is initialized to `0.0` at
[`tui/__init__.py:186`](../../teaagent/tui/__init__.py) and **read** at lines
744, 748, 762, 791, 805 but **never incremented**. `grep '_session_cost_cents
+=' tui/__init__.py` → zero matches. The controller's cost accumulation at
`chat_session_controller.py:168` (`session_state.session_cost_cents +=
result.cost_cents`) never fires for TUI sessions.

### CG-15 (symptom: divergent undo)
TUI `_handle_undo` at [`tui/__init__.py:812`](../../teaagent/tui/__init__.py)
calls `_restore_checkpoint()` — a git-stash path (`tui/__init__.py:641-707`).
REPL `/undo` uses `UndoJournal.restore()` via the controller
(`chat_session_controller.py:182-220`). Same command word, different recovery
model per surface.

The help text at `tui/__init__.py:109-110`:
```
undo  Undo all changes (using checkpoint — use teaagent agent undo for advanced).
```
This describes the *old* pre-controller behavior; surgical journal undo is not
mentioned.

---

## Acceptance Criteria

### Stop-gap (Step A, XS — ships first)
1. After one task with `cost_cents=N`, `tui._session_cost_cents == N`.
2. After two tasks, `tui._session_cost_cents == 2N`.
3. `test_tui_session_cost_accumulates` passes (from TICKET-14).

### Full migration (Steps B–D)
4. `_run_agent_task` drives `ChatSessionController`; `run_chat_agent` is not
   called directly from TUI.
5. TUI `/undo` uses `UndoJournal` (journal-first, checkpoint fallback) —
   identical to REPL.
6. `test_chat_surface_parity` runs the same task through both surfaces and
   asserts identical `status`, `final_answer`, `session_cost_cents`, and undo
   scope.
7. TUI help text describes surgical journal undo.
8. No regression in `pytest tests/test_tui.py` (all 104+ tests pass).

---

## Test Strategy

### New tests
| Test | What it asserts |
|------|-----------------|
| `test_tui_session_cost_accumulates` | (TICKET-14) — cost after two tasks |
| `test_tui_undo_uses_journal` | `_handle_undo` with a journal entry restores via `UndoJournal`, not `_restore_checkpoint` |
| `test_tui_undo_falls_back_to_checkpoint` | no journal → `_restore_checkpoint` is called |
| `test_chat_surface_parity` | same stub-cost task via REPL and TUI → identical result/cost/undo |

### Regression
`pytest tests/test_tui.py` — all existing tests pass. Pay attention to tests
that patch `run_chat_agent` directly; they will need updating if TUI no longer
calls it.

---

## Implementation Plan

### Step A — Cost stop-gap (1 line, ship now)

In `_run_agent_task` at `tui/__init__.py:924`, after `store.logger_for_result`:

```python
# CG-11 fix: accumulate session cost
self._session_cost_cents += result.cost_cents
```

Add this immediately after the `run_chat_agent` call returns (around line 924).
This is a one-line fix that unblocks honest `/cost` and budget display.

### Step B — Wire ChatSessionController

1. Import at top of `tui/__init__.py`:
   ```python
   from teaagent.chat_session_controller import ChatSessionController, SessionState
   ```

2. Add to `__init__` (`tui/__init__.py:141`):
   ```python
   self._chat_controller: Optional[ChatSessionController] = None
   ```

3. Add a factory method:
   ```python
   def _get_chat_controller(self) -> ChatSessionController:
       if self._chat_controller is None:
           self._chat_controller = ChatSessionController(
               root=self.root,
               output_fn=self.output_fn,
           )
       return self._chat_controller
   ```

4. In `_run_agent_task`, replace the `run_chat_agent(...)` block and manual
   `store.logger_for_result` / `undo_journal.save_to` calls with:
   ```python
   controller = self._get_chat_controller()
   controller.execute_task(
       task=task,
       adapter=adapter,
       config=config,
       initial_observations=initial_observations,
       resumed_from=resumed_from,
   )
   # Sync cost from controller's session state
   self._session_cost_cents = controller.session_state.session_cost_cents
   ```

   The controller already handles result display (`output_fn`), cost
   accumulation, observation appending, store logging, and undo journal saving.

5. Update `self.last_run_id` from `controller.last_run_id` after the call.

### Step C — Migrate TUI undo to UndoJournal

Replace `_handle_undo` (`tui/__init__.py:812`):

```python
def _handle_undo(self) -> None:
    controller = self._get_chat_controller()
    result = controller.undo_last_run()
    self.output_fn(result)
```

`controller.undo_last_run()` is already journal-first, checkpoint-fallback
(`chat_session_controller.py:182-220`).

Keep `_restore_checkpoint` as the internal implementation of `checkpoint restore`
but remove it from the `undo` dispatch.

### Step D — Update help text

At `tui/__init__.py:109-110`:
```
undo [run_id]  Undo last agent edit (journal-first, checkpoint fallback).
checkpoint     Create manual git checkpoint.
```

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Existing tests patch `run_chat_agent` directly on TUI | High | Update patches to use controller.execute_task or patch at `run_chat_agent` level (still called by controller) |
| `ChatSessionController` output_fn is called at different points than TUI expected | Medium | Run `test_chat_surface_parity` to catch output ordering differences |
| `_session_cost_cents` and `controller.session_state.session_cost_cents` drift on error path | Low | Sync via assignment after each call; controller is authoritative |
| `_restore_checkpoint` tests break if `_handle_undo` no longer calls it | Low | Rename tests to `test_checkpoint_restore_path` and assert via `_handle_checkpoint` |

---

## Dependency Graph

```
TICKET-14 (un-mask test) ──► TICKET-12 Step A (cost stop-gap)
                          ──► TICKET-12 Steps B-D (full migration)
                                └─► TICKET-13 (stop swallowing errors)
                                └─► TICKET-15 (cleanup)
```

Step A is independent and should land before Steps B–D.
