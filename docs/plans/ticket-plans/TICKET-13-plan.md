# TICKET-13 — Controller Stops Swallowing Real Errors
**Priority:** P2 | **Size:** S | **CG Finding:** CG-13

---

## Root Cause Analysis

`ChatSessionController.execute_task` at
[`teaagent/chat_session_controller.py:143-159`](../../teaagent/chat_session_controller.py)
wraps two persistence calls in blanket `except (AttributeError, TypeError): pass`
blocks, with comments explaining the intent as mock detection:

```python
# Save result to store (skip if audit is a mock in tests)
try:
    if audit and hasattr(audit, 'path') and audit.path:
        store = RunStore(self.root)
        store.logger_for_result(result, audit)
except (AttributeError, TypeError):
    # Audit logger is likely a mock in tests
    pass

# Save undo journal if it has entries
if undo_journal.has_entries:
    try:
        store = RunStore(self.root)
        undo_journal.save_to(store.undo_path(result.run_id))
    except (AttributeError, TypeError):
        # Store is likely a mock in tests
        pass
```

Both `AttributeError` and `TypeError` are wide, semantically meaningful
exception types. A genuine coding error in `logger_for_result` or
`undo_journal.save_to` — e.g. a wrong attribute name, a type mismatch in a
newly refactored method — will be silently swallowed in production. The undo
journal save failure is especially dangerous: **the user will believe undo
is available, but the journal was never written**.

The correct solution for test isolation is dependency injection, not exception
swallowing.

---

## Acceptance Criteria

1. `execute_task` does not catch `AttributeError` or `TypeError` to detect mocks.
2. A fault-injected test that raises `AttributeError` from `undo_journal.save_to`
   propagates the exception (or logs it) rather than silently passing.
3. Tests that previously relied on mock objects that lack `.path` or `.undo_path`
   continue to pass — achieved by proper mock setup, not exception suppression.
4. No new `except Exception: pass` anti-patterns introduced.

---

## Test Strategy

### New test: `test_controller_surfaces_save_failure`

```python
def test_controller_surfaces_save_failure():
    """A save failure in undo_journal is not swallowed."""
    from teaagent.chat_session_controller import ChatSessionController

    outputs = []
    controller = ChatSessionController(root='.', output_fn=outputs.append)

    bad_journal = MagicMock()
    bad_journal.has_entries = True
    bad_journal.save_to.side_effect = AttributeError('injected: bad attr')

    with patch('teaagent.chat_session_controller.UndoJournal', return_value=bad_journal), \
         patch('teaagent.chat_session_controller.run_chat_agent') as mock_run, \
         patch('teaagent.chat_session_controller.RunStore'):
        mock_run.return_value = MagicMock(
            status='completed', cost_cents=0, run_id='r1',
            final_answer=MagicMock(content='ok'), error_message=None
        )
        with pytest.raises(AttributeError, match='injected'):
            controller.execute_task('test task', adapter=None, config=None)
```

If the ticket is resolved by logging instead of raising, assert the log message
contains the error and is at WARNING or ERROR level.

### Regression

`pytest tests/test_chat_session_controller.py` — all existing tests pass after
fixing mock setup (see Implementation Step 2).

---

## Implementation Plan

### Step 1 — Replace exception-based mock detection with `isinstance` guards

Replace both `try/except` blocks:

```python
# Store result
store = RunStore(self.root)
store.logger_for_result(result, audit)

# Save undo journal
if undo_journal.has_entries:
    store = RunStore(self.root)
    undo_journal.save_to(store.undo_path(result.run_id))
```

Remove the `try/except` wrappers entirely. Real errors will now propagate.

### Step 2 — Fix tests that relied on the swallowing

Audit `tests/test_chat_session_controller.py` for tests that pass mock objects
without `.path`, `.undo_path`, or similar. For each:

- If the test does not care about persistence, add explicit mocks:
  ```python
  with patch('teaagent.chat_session_controller.RunStore') as mock_store:
      mock_store.return_value.logger_for_result.return_value = None
      mock_store.return_value.undo_path.return_value = Path('/tmp/test.json')
      ...
  ```

- If `audit` is a mock that lacks `.path`, either pass `None` for audit or
  give the mock a `.path` attribute.

### Step 3 — Add the fault-injection test (see Test Strategy above)

### Optional Step 4 — Log-and-continue for non-fatal persistence failures

If strict raising breaks too many integration paths, an alternative is:

```python
try:
    store = RunStore(self.root)
    undo_journal.save_to(store.undo_path(result.run_id))
except Exception as exc:
    logger.warning('undo journal save failed: %s', exc)
    self.output_fn(f'[warning] undo journal could not be saved: {exc}')
```

This surfaces the failure to the user and log without crashing the session.
Prefer raising; use this only if the call site is proven non-fatal.

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Existing tests fail because mocks were silently broken | High | Audit and fix mock setup in Step 2 before removing the catches |
| `RunStore.__init__` itself raises in some test environments | Low | Mock `RunStore` at module level in tests that don't test persistence |
| Removing the catch exposes a latent production bug in `logger_for_result` | Low but real | This is the desired outcome — surface the bug |

---

## Dependency Graph

```
TICKET-12 (TUI controller migration) ──► TICKET-13 (this)
  TICKET-13 can also ship before TICKET-12 if applied to
  chat_session_controller.py independently — the fix is in the
  controller, not the TUI.

TICKET-13
  └─ independent of TICKET-14, TICKET-15, TICKET-16
```

Can ship after TICKET-12 Step B or independently against the current
controller.
