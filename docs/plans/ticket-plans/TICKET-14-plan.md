# TICKET-14 — Fix the Test That Masks CG-11
**Priority:** P1 | **Size:** S | **CG Finding:** CG-16

> **Land this first.** Without it, TICKET-12's cost fix will appear green
> *before* and *after* the fix, giving no regression signal.

---

## Root Cause Analysis

`test_tui_cost_shows_session_cost` in
[`tests/test_tui.py`](../../tests/test_tui.py) (around line 1140) directly
sets `tui._session_cost_cents = 123.0` and then asserts the display string
shows `$1.23`. It verifies **formatting only** — it never calls
`_run_agent_task`, so it stays green whether or not cost accumulation is wired.

This is the live CG-11 bug: `self._session_cost_cents` is never incremented
in `_run_agent_task` (`tui/__init__.py:842-959` — no `+=` in the file). The
104-test suite passes green with the bug active.

---

## Acceptance Criteria

1. The existing formatting test is preserved (or refactored to cover formatting).
2. A new `test_tui_session_cost_accumulates` test:
   - Constructs a TUI with a stub adapter that returns `cost_cents=123`.
   - Calls `_run_agent_task` (or an equivalent invocation path).
   - Asserts `tui._session_cost_cents == 123.0` after one call.
   - Asserts `tui._session_cost_cents == 246.0` after two calls.
3. With CG-11 present (no `+=`), `test_tui_session_cost_accumulates` **fails**.
4. With TICKET-12's fix applied, both tests pass.

---

## Test Strategy

### `test_tui_session_cost_accumulates`

```python
def test_tui_session_cost_accumulates():
    # Stub adapter returns cost_cents=123 regardless of task
    class StubResult:
        status = 'completed'
        final_answer = SimpleNamespace(content='ok')
        cost_cents = 123.0
        input_tokens = 10
        output_tokens = 5
        run_id = 'test-run-1'
        error_message = None

    def stub_run_chat_agent(**kwargs):
        return StubResult()

    outputs = []
    tui = TeaAgentTUI(root='.', output_fn=outputs.append)
    tui.chat = True

    with patch('teaagent.tui.run_chat_agent', stub_run_chat_agent), \
         patch.object(tui, '_get_session_store'), \
         patch('teaagent.tui.RunStore'):
        tui._run_agent_task('task one')
        assert tui._session_cost_cents == 123.0, 'first run not accumulated'
        tui._run_agent_task('task two')
        assert tui._session_cost_cents == 246.0, 'second run not accumulated'
```

### Existing formatting test

Keep a minimal formatting-only test but rename it to make its scope clear:

```python
def test_tui_cost_display_format():
    tui = TeaAgentTUI(root='.')
    tui._session_cost_cents = 123.0
    out = []
    tui.output_fn = out.append
    tui._handle_cost()
    assert '$1.23' in out[-1]
```

---

## Implementation Plan

1. Locate `test_tui_cost_shows_session_cost` in `tests/test_tui.py`.
2. Rename it to `test_tui_cost_display_format` and trim to formatting only.
3. Add `test_tui_session_cost_accumulates` as above.
4. Run `pytest tests/test_tui.py::test_tui_session_cost_accumulates` — it must
   **FAIL** at this point (proving it detects the bug).
5. Then apply TICKET-12's cost stop-gap (`self._session_cost_cents += result.cost_cents`).
6. Re-run — test must pass.

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Stub adapter structure diverges from real `RunResult` | Low | Use `SimpleNamespace`; the accumulation path only needs `cost_cents` |
| `RunStore` or `SessionStore` side-effects in `_run_agent_task` | Medium | `patch` both (already done in existing TUI tests) |
| Test is too tightly coupled to `_session_cost_cents` field name | Low | Field is private but stable; name is the bug's exact symptom |

---

## Dependency Graph

```
TICKET-14 (this) — must land BEFORE TICKET-12 cost fix
  └─ TICKET-12 (TUI controller migration) — closes CG-11
  └─ TICKET-13 (error swallowing) — independent
  └─ TICKET-15 (cleanup) — independent
```
