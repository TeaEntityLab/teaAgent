# TASK-DD2-001 — Execute Or Reject `teaagent chat <task>`
**Priority:** P1 | **Size:** S | **Phase:** A (Stop First-Hour Trust Failures)

---

## Root Cause Analysis

The `chat` subparser at
[`teaagent/cli/_agent_parsers.py:634`](../../../teaagent/cli/_agent_parsers.py)
calls `add_agent_run_arguments(p, include_task_positional=True)`, which adds a
positional `task` argument (`nargs='?'`, default `None`) at
[`_agent_parsers.py:66-70`](../../../teaagent/cli/_agent_parsers.py).

The handler, `chat_command` at
[`teaagent/cli/_handlers/_chat.py:538`](../../../teaagent/cli/_handlers/_chat.py),
never reads `args.task`. It delegates immediately to `run_tui(chat=True, …)`
without forwarding the task. `run_tui` has no `initial_task` parameter, and
`TeaAgentTUI.run()` starts the REPL loop directly — no task injection path
exists at all.

The stale `run_chat_repl` at `_chat.py:589` does accept `initial_task` and has
a working execution path (`_chat.py:1003-1026`), but it is not called by
`chat_command`.

**Result:** `teaagent chat "fix the login bug"` silently drops `"fix the login
bug"` and opens an empty REPL — the user's first interaction produces no
visible effect on their stated intent.

**Secondary:** `--from-plan` is also forwarded without execution (same cause).

---

## Acceptance Criteria

1. `teaagent chat "do X"` either executes the task before the REPL loop opens,
   **or** exits with a clear `unsupported-syntax` error message and non-zero
   exit code (product decision required; see Risk).
2. When executed first: the TUI runs one agent task synchronously, appends the
   result to chat history, then enters the interactive REPL.
3. `teaagent chat` (no task) behaves identically to today — opens REPL.
4. `teaagent chat --from-plan <file>` respects the same execute-or-reject
   contract.
5. A handler-level test (not just parser shape) asserts the active CLI path.

---

## Test Strategy

### New tests

| Test | File | What it asserts |
|------|------|-----------------|
| `test_chat_command_executes_initial_task` | `tests/test_chat_handler.py` | `chat_command` with `args.task="do X"` calls `TeaAgentTUI._run_agent_task("do X")` before entering the loop |
| `test_chat_command_no_task_opens_repl` | same | `chat_command` with `args.task=None` enters loop without calling `_run_agent_task` |
| `test_chat_command_from_plan_executed` | same | `args.from_plan` path hits execution, not silent drop |
| `test_chat_parser_task_positional` | `tests/test_cli_parsers.py` | `parse_args(['chat','fix x'])` → `args.task == 'fix x'` |

### Regression
Run existing TUI tests (`pytest tests/test_tui.py`) — no chat-loop test should
break. If any test patches `run_tui`, ensure the new `initial_task` parameter
is accepted.

---

## Implementation Plan

### Option A — Execute-first (recommended)

1. **Add `initial_task` to `run_tui`** (`tui/__init__.py:1195`):
   ```python
   def run_tui(*, ..., initial_task: Optional[str] = None) -> int:
   ```

2. **Inject into `TeaAgentTUI.run()`** before the REPL loop
   (`tui/__init__.py:324`):
   ```python
   def run(self, *, run_setup=False, setup_write_env=False,
           initial_task: Optional[str] = None) -> int:
       ...
       if initial_task:
           self._run_agent_task(initial_task)
       while True:  # existing REPL loop
   ```

3. **Forward from `chat_command`** (`_chat.py:559`):
   ```python
   return run_tui(
       ...,
       initial_task=getattr(args, 'task', None) or None,
   )
   ```

4. **Handle `--from-plan`** similarly: read the plan file before calling
   `run_tui`, pass the content (or first task) as `initial_task`.

### Option B — Reject-with-error (simpler, loses feature)

At the top of `chat_command`:
```python
if getattr(args, 'task', None):
    print('[TeaAgent] Error: positional task is not supported with chat. '
          'Use "teaagent run" to run a single task.')
    return 2
```

**Recommendation:** Option A. The UX is clearly better, the code path
(`_run_agent_task`) already exists, and `run_chat_repl` at `:589` proves the
pattern works. The feature was clearly intended — only the wiring is missing.

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `_run_agent_task` blocks and never returns if the model call hangs | Low | Already true in the REPL loop; same timeout/interrupt handling applies |
| `_load_tui_state` overwrites `root` *after* `initial_task` is computed | Medium | See TASK-DD2-002; fix together or guard `initial_task` against re-routing |
| Parser positional order conflict (`task` vs `provider`) | Low | Already handled by `include_task_positional=True`; test covers it |
| `--from-plan` file not found | Low | Validate path before passing; return exit code 2 |

---

## Dependency Graph

```
TASK-DD2-001 (this)
  └─ independent of TICKET-12 (TUI controller migration)
  └─ should co-ship with TASK-DD2-002 (root override guard)
       because _load_tui_state runs before the first task fires
```

No blocking dependencies; can ship immediately.
