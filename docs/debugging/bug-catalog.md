# Bug Catalog
# teaagent — 2026-06-02

Per-defect reproduction steps, log signatures, diagnostics, and workarounds for all 13 known defeat scenarios (DS-01 through DS-13). Status as of HEAD at ledger date.

For cross-cutting themes and the decision matrix, see the source analysis:
[`docs/analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md`](../analysis/defeat-scenarios-and-cascade-effects-2026-06-02.md).

---

## Quick Triage Flowchart

```
What symptom are you seeing?
│
├─ Cost shows $0.00 ──────────────────────────────────────────────────→ DS-01
├─ TUI ignores recent fixes (undo wrong, cost wrong) ─────────────────→ DS-02
├─ Run appeared to succeed but undo journal is empty ─────────────────→ DS-03
├─ Suspension JSON has wrong/stale audit_trail field ─────────────────→ DS-04
├─ /undo reverted files I didn't touch ───────────────────────────────→ DS-05
├─ Test suite says cost works, live TUI doesn't ──────────────────────→ DS-06
├─ Parity test passes but TUI and REPL behave differently ────────────→ DS-07
├─ teaagent resume <id> errors "no run_started task" ─────────────────→ DS-08
├─ agent run --background <id> created a new nonsense run ────────────→ DS-09
├─ Resume has no memory of suspended session context ─────────────────→ DS-10
├─ teaagent chat "task" opened but didn't run the task ───────────────→ DS-11
├─ Approval with no path granted unexpected broad access ─────────────→ DS-12
└─ --max-estimated-cost-cents 0 didn't limit spending ────────────────→ DS-13
```

---

## DS-01 · CG-11 — TUI cost display always $0.00

**Severity:** P1 | **Ticket:** TICKET-12 | **Status:** OPEN

### Reproduce

```bash
teaagent tui
# Run any task that does LLM work (e.g., type a prompt)
/cost
# Expected: actual cost in cents
# Actual: $0.00
```

### Where it appears in logs

Does not appear in any log — the failure is completely silent. There is no warning, no error, no indicator that the counter is wrong.

### Diagnostic

```bash
# Confirm the real cost via audit.jsonl
grep '"event_type": "run_completed"' ~/.teaagent/audit.jsonl | tail -5 \
  | python -c "import sys,json; [print('cost_cents:', json.loads(l)['payload'].get('cost_cents','?')) for l in sys.stdin]"
```

If `cost_cents` is non-zero in audit but TUI shows $0.00, DS-01 is confirmed.

### Root cause

`TeaAgentTUI._session_cost_cents` is initialized to `0.0` at `tui/__init__.py:186` and is never incremented. `_run_agent_task` reads `result.cost_cents` only for the run summary formatter; there is no `+=` in the file.

```bash
# Confirm: should return nothing
grep '_session_cost_cents *+=' /Users/teee/dev/teaagent/teaagent/tui/__init__.py
```

### Workaround

Use `audit.jsonl` or the run summary printed after each task to track real cost. Do not trust the TUI budget bar or `/cost` for cumulative session cost.

```bash
# Check cumulative cost for current session (last N runs)
grep '"event_type": "run_completed"' ~/.teaagent/audit.jsonl | tail -20 \
  | python -c "
import sys, json
total = 0
for line in sys.stdin:
    c = json.loads(line)['payload'].get('cost_cents', 0) or 0
    total += c
print(f'total: {total} cents = \${total/100:.2f}')
"
```

### Fix location

`teaagent/tui/__init__.py` — add `self._session_cost_cents += result.cost_cents` inside `_run_agent_task` after the result is received (same pattern as `chat_session_controller.py:168`).

---

## DS-02 · CG-12 — TUI never adopted ChatSessionController

**Severity:** P1 (structural root cause) | **Ticket:** TICKET-12 | **Status:** OPEN

### Reproduce

Run any task via `teaagent tui`. Compare the result to the same task via `teaagent chat` (REPL). Any fix applied to `ChatSessionController` after CG-01…CG-10 will be absent in TUI output.

### Where it appears in logs

Does not appear. The TUI runs correctly from its own perspective; the divergence is only visible by comparing behaviour between surfaces.

### Diagnostic

```bash
# Confirm TUI calls run_chat_agent directly, not the controller
grep -n "run_chat_agent\|ChatSessionController\|execute_task" \
  /Users/teee/dev/teaagent/teaagent/tui/__init__.py | head -20
# Expected: run_chat_agent at ~line 890, ChatSessionController absent or not called
```

### Root cause

`tui/__init__.py:890` calls `run_chat_agent(...)` directly. `ChatSessionController` is not instantiated in the TUI code path. All post-CG-01 fixes (CG-02 surgical undo, CG-11 cost accumulation, CG-15 undo scope) went into the controller; the TUI never received them.

### Workaround

Use `teaagent chat` (REPL) instead of `teaagent tui` for any workflow that depends on correct cost tracking, surgical undo, or session continuity. The REPL uses the controller and receives all fixes.

### Fix location

`teaagent/tui/__init__.py` — instantiate `ChatSessionController` and route `_run_agent_task` through `controller.execute_task(...)`. DS-01, DS-05, and any future controller fix are automatically resolved by fixing DS-02.

---

## DS-03 · CG-13 — Controller silently swallows real errors

**Severity:** P2 | **Ticket:** TICKET-13 | **Status:** OPEN

### Reproduce

This is hard to trigger in normal operation. To reproduce in a test or dev environment:

```python
# In a test, make the store's method raise AttributeError
from unittest.mock import MagicMock, patch

store = MagicMock()
store.logger_for_result.side_effect = AttributeError("simulated corruption")

# Run via controller
controller = ChatSessionController(store=store, undo_journal=...)
result = controller.execute_task("some task")
# Expected: exception or error log
# Actual: silent success, run not persisted
```

### Where it appears in logs

Nowhere — the `except (AttributeError, TypeError): pass` clause at `chat_session_controller.py:143-159` produces no log output.

### Diagnostic

```bash
# Check if a run_id appears in audit.jsonl but not in run store
grep '"event_type": "run_completed"' ~/.teaagent/audit.jsonl | grep "YOUR_RUN_ID"
teaagent agent show YOUR_RUN_ID   # if this errors, the run wasn't persisted
```

If the audit has a `run_completed` event but `agent show` errors, the save was swallowed.

### Root cause

`chat_session_controller.py:143-159`:

```python
try:
    store.logger_for_result(result)
    undo_journal.save_to(result)
except (AttributeError, TypeError):
    pass   # ← intended for test mocks, catches real production errors too
```

### Workaround

After any important run, verify persistence:

```bash
teaagent agent show <run_id>   # if this returns data, the save succeeded
```

If it errors, the undo journal is also lost. Use `git stash list` to check for a checkpoint instead.

### Fix location

`teaagent/chat_session_controller.py:143-159` — narrow the except to test-mock-specific patterns, or replace with a proper test seam (e.g., a `_store_result` method that tests can override). At minimum, add `logger.error("...", exc_info=True)` before `pass`.

---

## DS-04 · CG-14 — Redundant stale `audit_trail` field in suspension JSON

**Severity:** P3 | **Ticket:** TICKET-15 | **Status:** OPEN

### Reproduce

```bash
# In REPL
teaagent chat
/background
cat ~/.teaagent/suspension-*.json | python -m json.tool | grep -A5 '"audit_trail"'
# Sees a stale audit snapshot that diverges from audit.jsonl
```

### Where it appears in logs

Not in logs — visible only in the suspension JSON file.

### Diagnostic

Compare the `audit_trail` field's timestamp in the JSON against the matching event in `audit.jsonl`. If they diverge (which they will), the JSON field is stale.

### Root cause

`chat_repl.py:89-93` was the only audit record before CG-10 fixed it. After CG-10, a real `audit.record(...)` call was added but the vestigial field was not removed.

### Workaround

**Treat `audit.jsonl` as the authoritative audit record.** Ignore `audit_trail` in suspension JSON files for forensic purposes.

---

## DS-05 · CG-15 — TUI /undo uses git-stash-pop, REPL /undo uses surgical journal

**Severity:** P2 | **Ticket:** TICKET-12 | **Status:** OPEN

### Reproduce

```bash
# In TUI
teaagent tui
# 1. Make a manual file edit to any file
# 2. Run a task (which creates a checkpoint stash)
# 3. /undo
# Expected: only task's changes reverted
# Actual: manual edit also reverted (git stash pop restores to checkpoint)
```

### Where it appears in logs

Partial — the TUI prints "checkpoint restored" rather than "undo completed." The scope difference is not surfaced.

### Diagnostic

```bash
# Confirm which undo handler was called
grep -n "_restore_checkpoint\|undo_last_run\|git stash" \
  /Users/teee/dev/teaagent/teaagent/tui/__init__.py | grep -A2 -B2 "641"
```

At `tui/__init__.py:641`, `/undo` calls `_restore_checkpoint()` (git stash pop), not `controller.undo_last_run()`.

### Workaround

Before typing `/undo` in the TUI:

```bash
git status            # check what will be affected
git stash list        # inspect the checkpoint stash
git stash show -p     # see what the stash will restore
```

If the stash would revert manual edits, do NOT use TUI `/undo`. Instead:

```bash
git diff HEAD         # review changes manually
git checkout <file>   # revert only specific files the run modified
```

### Fix location

`teaagent/tui/__init__.py` near line 641 — route `/undo` through the controller (requires DS-02 fix first) or at minimum call `UndoJournal.restore()` directly if the journal is present.

---

## DS-06 · CG-16 — Cost test injects state, masks DS-01

**Severity:** P1 (test integrity) | **Ticket:** TICKET-14 | **Status:** OPEN

### Reproduce

```bash
# The test always passes even with DS-01 live:
python -m pytest tests/test_tui.py -k "cost" -v
# Passes — but does not exercise the accumulation path
```

### Diagnostic

```bash
# Confirm the test injects state rather than exercising accumulation
grep -n "_session_cost_cents\|cost_cents" tests/test_tui.py | head -20
# Look for direct assignment: tui._session_cost_cents = 123.0
```

If the test sets `_session_cost_cents` directly (line ~1140-1145), it only validates the formatter, not the accumulation path.

### Workaround

Do not trust the TUI cost test as proof that cost accumulation works. Add a path-level test:

```python
# Correct test pattern:
tui = TeaAgentTUI(...)
tui._run_agent_task("some task")   # must invoke the real method
assert tui._session_cost_cents > 0   # accumulation happened
```

---

## DS-07 · CG-17 — Parity test never instantiates TUI

**Severity:** P1 (test integrity) | **Ticket:** TICKET-12b | **Status:** OPEN

### Reproduce

```bash
python -m pytest tests/test_cli_chat.py -k "parity" -v
# Passes — but TUI was never constructed
```

### Diagnostic

```bash
grep -n "TeaAgentTUI\|run_tui\|tui\.__init__" tests/test_cli_chat.py | head -20
# If no TeaAgentTUI instantiation found near the parity test, it's hollow
```

### Workaround

Treat parity test as non-authoritative until it instantiates both surfaces. Any behavioral difference between `teaagent chat` and `teaagent tui` should be assumed possible until proven otherwise.

---

## DS-08 · AG-01 — `teaagent resume <repl-id>` always errors

**Severity:** P1 | **Ticket:** TICKET-16 | **Status:** OPEN

### Reproduce

```bash
teaagent chat
/background        # prints: "To resume: teaagent resume {run_id}"
# Exit
teaagent resume {run_id}
# Error: {"status": "error", "message": "run '{run_id}' has no run_started task"}
```

### Where it appears in logs

The error is surfaced as a JSON message. Enable DEBUG on `teaagent.cli._handlers._agent` to see the internal ValueError from `run_store.py:143-149`.

### Diagnostic

```bash
# Confirm the suspension emitted session_suspended, not run_started
grep '"run_id": "YOUR_RUN_ID"' ~/.teaagent/audit.jsonl \
  | python -c "import sys,json; [print(json.loads(l)['event_type']) for l in sys.stdin]"
# Output: session_suspended   ← not run_started, hence resume errors
```

### Root cause

`agent_resume_command` calls `store.task_for_run(run_id)` which scans for `run_started` events. REPL suspension emits only `session_suspended`. The two halves used incompatible schemas.

### Workaround

```bash
# Use interactive-review instead — it works, though read-only
teaagent agent interactive-review {run_id}

# For actual continuation, copy the task from the suspension JSON and re-run
cat ~/.teaagent/suspension-{run_id}.json | python -c "
import sys, json
data = json.load(sys.stdin)
print('Task context:', data.get('task') or data.get('last_task', '(none saved)'))
"
```

---

## DS-09 · AG-02 — `agent run --background <id>` silently runs the id as a literal task

**Severity:** P1 | **Ticket:** TICKET-16 | **Status:** OPEN

### Reproduce

```bash
# After /background, the REPL prints:
# "teaagent agent run --background {run_id}"
teaagent agent run --background a3f9c12b-1234-...
# Creates a NEW run whose task is the literal string "a3f9c12b-1234-..."
# No error. Costs money.
```

### Where it appears in logs

```bash
# Find the bogus run:
grep '"event_type": "run_started"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    task = e['payload'].get('task', '')
    # UUID pattern in task = the DS-09 bogus run
    if len(task) == 36 and task.count('-') == 4:
        print('BOGUS RUN:', e['run_id'], 'task=', task)
"
```

### Root cause

`agent_run_task` uses `task` as a positional arg with `nargs='?'`. The run_id is consumed as the task string with no UUID-shape guard.

### Workaround

Do not use `agent run --background <run_id>`. Use `agent interactive-review <run_id>` instead (the only working path for REPL suspensions). If a bogus run was created:

```bash
# Check it completed (wasted money)
teaagent agent show {bogus_run_id}
# The run_id you care about is the original suspension's run_id, not the new one
```

---

## DS-10 · AG-03 — Suspended session observations are never rehydrated

**Severity:** P2 | **Ticket:** TICKET-16 | **Status:** OPEN

### Reproduce

```bash
# Run a long session with many observations
teaagent chat
# (run 10+ tasks)
/background
teaagent agent interactive-review {run_id}
# Agent has no context from the suspended session
```

### Where it appears in logs

No log — the resume path reads from RunStore/SQLite, not from the suspension JSON. There is no warning that context was dropped.

### Diagnostic

```bash
# Check what was saved in the suspension JSON
cat ~/.teaagent/suspension-{run_id}.json | python -c "
import sys, json
d = json.load(sys.stdin)
print('observations:', len(d.get('observations', [])))
print('keys saved:', list(d.keys()))
"
```

### Root cause

`suspend_to_background` writes `suspension-{id}.json` with observations. `agent_resume_command` reads from `RunStore`/SQLite checkpoint. `_load_suspension_data` in `_agent.py:1057` reads the JSON for `interactive-review` but does not feed observations into execution. Two independently written halves with no bridge.

### Workaround

Before suspending, manually note the key observations you need for continuation. After resuming via `interactive-review`, provide context manually in the review session.

---

## DS-11 · UXD-001 — `teaagent chat "task"` silently drops the initial task

**Severity:** P1 | **Ticket:** Not yet ticketed | **Status:** OPEN (stop-gap landed in TASK-DD2-001)

### Reproduce

```bash
teaagent chat "refactor the auth module"
# REPL opens
# Task is NOT submitted — user sees empty prompt
```

Note: a stop-gap fix was committed in TASK-DD2-001 (commit `47710d9`). Verify whether your build includes that commit before assuming this is live.

### Where it appears in logs

Enable DEBUG on `teaagent.cli._handlers._chat`:

```bash
LOG_LEVEL=DEBUG teaagent chat "my task" 2>&1 | grep "initial_task\|args.task\|run_tui"
```

If you see `args.task` read but not passed to `run_tui`, the task was dropped.

### Diagnostic

```bash
# Check if the fix from TASK-DD2-001 is in your build
grep -n "initial_task\|args.task" \
  /Users/teee/dev/teaagent/teaagent/cli/_handlers/_chat.py | head -20
# If initial_task is passed to run_tui/run_chat_repl, fix is present
```

### Root cause (pre-fix)

`chat_command` at `_chat.py:538` called `run_tui(...)` without passing `args.task`. `run_tui` had no `initial_task` parameter. `run_chat_repl` had `initial_task` support but was unreachable from `chat_command`.

### Workaround (if fix not present)

```bash
# Submit the task inside the REPL after it opens, or use agent run
teaagent agent run "refactor the auth module"
```

---

## DS-12 · UXD-005 — Empty path in approval creates implicit global grant

**Severity:** P1 (security) | **Ticket:** Not yet ticketed | **Status:** FIXED / VERIFY-CLOSE

**Current status — 2026-06-05:** This is no longer a live behavior in the
current code path. Blank scoped patterns are rejected by `ApprovalPresetStore`,
path-scoped interactive approval without an extractable path returns denied, and
non-session persistent grants require at least one explicit `path_glob` or
`command_prefix`. Keep this catalog entry as a trace signature for old runs and
for regression triage.

### Reproduce

```bash
# At an approval prompt for a file-write tool:
# Press Enter without entering a path (or path field is pre-filled empty)
# The agent now has blanket write access to the entire workspace
```

### Where it appears in logs

```bash
# Check audit.jsonl for approvals with empty path_scope
grep '"event_type": "approval_granted"' ~/.teaagent/audit.jsonl \
  | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    scope = e['payload'].get('path_scope') or e['payload'].get('scope', '')
    if not scope or scope == '':
        print('IMPLICIT GLOBAL GRANT:', json.dumps(e, indent=2))
"
```

### Historical root cause

`ApprovalManager` creates an `ApprovalRule` with no path restriction when `path_scope` is empty or None. The rule-matching logic then grants the approval for any path.

### Regression evidence

- `tests/integration/test_destructive_approval_lifecycle.py::test_empty_path_globs_rejected_ds12`
- `tests/test_ergonomics.py::test_approval_preset_store_rejects_blank_scoped_patterns`
- `tests/test_smart_hitl.py::test_smart_hitl_approval_p_without_path_stays_denied`
- `tests/test_tui.py::test_tui_path_approval_without_path_stays_denied`

### Workaround for older versions

**Reject any approval prompt where the path field is empty.** Deny the request, then re-run the task with an explicit path specified in the prompt. Inspect `audit.jsonl` for any past empty-scope grants and revoke them by restarting the session.

### Security note

In `prompt` permission mode, this silently converts a scoped approval into a session-wide blanket, effectively downgrading to `auto-approve` for that tool type.

---

## DS-13 · UXD-007 — `0` cost cap means "unlimited", not "block all"

**Severity:** P2 | **Ticket:** Not yet ticketed | **Status:** FIXED / VERIFY-CLOSE

**Current status — 2026-06-05:** The current budget model uses `None` as the
only unlimited sentinel. `0` is a real zero-spend cap and blocks any positive
preflight or runtime estimate. CLI, chat, and TUI paths preserve `None` and `0`
instead of coercing them to defaults.

### Reproduce

```bash
teaagent chat --max-estimated-cost-cents 0 "expensive task"
# Expected/current: no spend allowed
# Historical bug: unlimited spend (0 was the "no cap" sentinel)
```

### Historical log signature

No log or warning. The `<= 0` check at `runner/_core.py:142` silently skips the budget check.

### Diagnostic

```bash
# Confirm the interpretation at each location
grep -n "max_estimated_cost_cents\|<= 0\|or 1000" \
  /Users/teee/dev/teaagent/teaagent/runner/_core.py \
  /Users/teee/dev/teaagent/teaagent/chat_repl.py 2>/dev/null | head -20
```

Historical independent interpretations of `0`:
- `runner/_core.py:142`: `<= 0` → unlimited
- `chat_repl.py:255`: `or 1000` → treat 0 as $10 default
- Parser: `0` is the default sentinel for "not set"

### Regression evidence

- `tests/test_budget.py::test_zero_cost_budget_blocks_preflight`
- `tests/integration/test_runner_cost_tracking.py::test_zero_cost_cap_blocks_positive_cost_run`
- `tests/test_automation_run_budget.py::test_chat_agent_config_cost_cap_none_passes_through`
- `tests/test_tui.py::test_tui_budget_zero_wired_to_agent_run`

### Workaround for older versions

Do not use `0` as a budget sentinel. To enforce a tight cap, use a small non-zero value:

```bash
# Allow up to 1 cent (effectively blocks any real LLM call)
teaagent chat --max-estimated-cost-cents 1 "task"
```

To set "no cap" explicitly, omit the flag entirely (default behaviour).

---

## Cross-Cutting Patterns

| Theme | Bugs affected | Implication |
|-------|--------------|------------|
| Silent TUI failures | DS-01, DS-05, DS-09, DS-11 | Any TUI behavior that looks correct may not be |
| Write-only data paths | DS-05 (undo journal), DS-10 (suspension JSON) | Data is written but never read; deferred data loss |
| Broken suspend→resume chain | DS-08, DS-09, DS-10 | No working path from `/background` to execution continuation |
| Hollow tests mask bugs | DS-06, DS-07 | Green CI is not proof of correctness for TUI paths |
| Security boundary violation | DS-12 | Empty-path approvals must be treated as security events |
