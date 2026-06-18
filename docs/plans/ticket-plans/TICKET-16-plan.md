# TICKET-16 — Honest, Then Working Suspend→Resume
**Priority:** P1 | **Size:** XS (honesty) + M (real feature)
**CG Findings:** AG-01, AG-02, AG-03, AG-04
**Human Review Required:** governance handoff path

## Progress

- Phase 1 honesty patch has shipped: REPL `/background` now prints only the
  checkpoint/review path and no longer advertises bogus continuation hints.
- Phase 2 guard has started: `teaagent agent run --background <id>` now refuses
  id-shaped inputs that match a known run or suspension record.
- Full REPL-originated resume rehydration remains open.

---

## Root Cause Analysis

After `/background` in the REPL, `suspend_to_background` prints three
follow-up commands. Two are broken:

### AG-01 — `teaagent resume <id>` always fails

`agent_resume_command` at
[`teaagent/cli/_handlers/_agent/resume.py:16`](../../../teaagent/cli/_handlers/_agent/resume.py)
calls `store.task_for_run(args.run_id)`. `task_for_run` at
[`teaagent/run_store.py:143`](../../../teaagent/run_store.py) scans run events for
a `run_started` event and **raises `ValueError`** if none exists (`:149`).

`suspend_to_background` at
[`teaagent/cli/_handlers/chat_repl.py:56-136`](../../../teaagent/cli/_handlers/chat_repl.py)
generates a `uuid4()[:8]` run ID (`:56`) and records only a
`session_suspended` event (`:129-136`). It never writes a `run_started` event
to `RunStore`. So `task_for_run` always raises for REPL-originated suspensions.
`agent_resume_command` catches it (`:218-220`) and returns JSON
`{"status":"error"}`.

### AG-02 — `teaagent agent run --background <id>` runs the id as a task

`_agent_parsers.py:286-289` documents `--background` as "run detached". The
`<id>` positional is consumed as the `task` argument (`nargs='?'`). So the
command starts a **new detached run whose task is the literal uuid string** —
silently wrong.

### AG-03 — Saved context is dead

`suspend_to_background` saves up to 10 observations into
`suspension-<id>.json` (`:80`). `agent_resume_command` at `:239-244` reads
observations from `RunStore` / checkpoint, **not** from the suspension JSON.
The two halves were built independently and never connected.

### AG-04 — Broken commands undo the CG-09/10 honesty fix

The suspend message is honest (`"suspension checkpoint, not background
execution"` at `:144`). But the three commands printed immediately after
reintroduce exactly the dishonesty CG-09/10 set out to remove.

Additionally, `:145` still prints:
```
'[TeaAgent] Use "teaagent agent run --detach" for actual background tasks.'
```
`--detach` does not exist in the current CLI (the flag is `--background`).

---

## Acceptance Criteria

### Phase 1 — Honesty (XS, ships immediately)
1. `/background` prints only the command that actually works:
   `teaagent agent interactive-review <run_id>`.
2. The broken `teaagent resume <id>` hint is removed.
3. The `--detach` reference is removed or replaced with `--background`.
4. No behavior change beyond the printed strings.

### Phase 2 — Real resume (M)
5. `teaagent resume <id>` for a REPL-originated suspension succeeds:
   reconstructs the task and observations from the suspension JSON (or from a
   `run_started` event written at suspend time).
6. Resumed session has the same last N observations as the suspended one.
7. `teaagent agent run --background <existing-id>` errors with "did you mean
   `teaagent resume <id>`?" rather than running the id as a task.
8. `test_repl_suspend_resume_roundtrip` passes.

---

## Test Strategy

### Phase 1 tests

```python
def test_suspend_prints_only_working_command():
    with patch('teaagent.cli._handlers.chat_repl.RunStore'), \
         patch('subprocess.run'):
        with io.StringIO() as buf, redirect_stdout(buf):
            run_id = suspend_to_background(config, {}, set())
            output = buf.getvalue()
    assert 'teaagent agent interactive-review' in output
    assert 'teaagent resume' not in output
    assert '--detach' not in output
    assert '--background' not in output or 'agent run' not in output
```

### Phase 2 tests

```python
def test_repl_suspend_resume_roundtrip(tmp_path):
    """Suspend a session; resume it; observations are rehydrated."""
    config = ChatAgentConfig(root=tmp_path, ...)
    context = {'observations': [{'type': 'tool', 'content': 'obs1'}]}
    run_id = suspend_to_background(config, context, set())

    # Now resume
    args = Namespace(run_id=run_id, root=str(tmp_path), fresh_restart=False,
                     checkpoint_store=None, ...)
    with patch('teaagent.cli._handlers._agent.run_chat_agent') as mock_run:
        mock_run.return_value = MagicMock(status='completed', ...)
        result = agent_resume_command(args)
    assert result == 0
    call_kwargs = mock_run.call_args[1]
    obs = call_kwargs.get('initial_observations', [])
    assert any(o.get('content') == 'obs1' for o in obs)

def test_agent_run_background_rejects_existing_id(tmp_path):
    """--background with a known suspension id shows a helpful error."""
    # Create a suspension file
    (tmp_path / '.teaagent').mkdir()
    (tmp_path / '.teaagent' / 'suspension-abc12345.json').write_text('{}')
    args = Namespace(task='abc12345', background=True, root=str(tmp_path), ...)
    out = []
    result = agent_run_task(args)
    assert result != 0  # or check for error message
```

---

## Implementation Plan

### Phase 1 — Honesty patch (XS)

In `suspend_to_background` at `chat_repl.py:140-145`, replace the printed
block:

```python
# Remove these three lines:
print(f'[TeaAgent] To resume: teaagent resume {run_id}')
print(f'[TeaAgent] To review: teaagent agent interactive-review {run_id}')
print('[TeaAgent] Use "teaagent agent run --detach" for actual background tasks.')

# Replace with:
print(f'[TeaAgent] To review: teaagent agent interactive-review {run_id}')
print('[TeaAgent] (Resume from REPL session not yet supported via CLI.)')
```

This unblocks Phase 1 in a single commit.

### Phase 2 — Real resume (M)

**Option A — Write `run_started` at suspend time (preferred)**

At the end of `suspend_to_background`, after writing the suspension JSON,
write a `run_started` event into RunStore:

```python
store = RunStore(root)
store.log_event(
    run_id=run_id,
    event_type='run_started',
    payload={
        'task': session_context.get('last_task', '(resumed from REPL suspension)'),
        'suspended_from': 'repl',
    }
)
```

This makes `task_for_run(run_id)` succeed, and `agent_resume_command`'s
existing observation-loading path (`:239-244`) will pick up the saved
observations via `store.observations_for_run(run_id)`.

Additionally: write the `observations` from `suspension_data` as
`tool_call_completed` events into RunStore at suspend time so
`observations_for_run` returns them.

**Option B — `agent_resume_command` falls back to suspension JSON**

Modify `agent_resume_command` at `_agent.py:214`:

```python
try:
    original_task = store.task_for_run(args.run_id)
except (FileNotFoundError, ValueError):
    # Fall back to suspension file
    suspension = _load_suspension_data(Path(args.root), args.run_id)
    if suspension is None:
        print_json({'status': 'error', 'message': f"run '{args.run_id}' not found"})
        return 1
    original_task = suspension.get('last_task', '(resumed from REPL suspension)')
    initial_observations = suspension.get('session_context', {}).get('observations', [])
```

Option B is less invasive but requires `suspension_data` to carry the last task
(add it to the `suspend_to_background` JSON).

**Guard AG-02 in `agent_run_task`:**

In `_agent.py` `agent_run_task`, before starting the run:

```python
if args.background and args.task:
    tea_dir = Path(args.root) / '.teaagent'
    if (tea_dir / f'suspension-{args.task}.json').exists():
        print(f'[TeaAgent] Error: {args.task!r} looks like a suspension ID. '
              f'Did you mean: teaagent resume {args.task}')
        return 2
```

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Writing `run_started` event creates a duplicate run ID in RunStore | Low | RunStore is append-only; duplicate run_id is unusual but handled by `task_for_run` returning the first match |
| Observation rehydration gives the model stale context | Medium | Auto-compact on resume already exists (`_agent.py:245-252`); use it |
| Phase 2 scope creep if observation serialization is complex | Medium | Ship Phase 1 first; track Phase 2 separately |
| `_load_suspension_data` ACP version check at `_agent.py:1086` blocks old files | Low | Suspension files written by the same code will always have `acp_version` |

---

## Dependency Graph

```
TICKET-16 Phase 1 (honesty) — no dependencies, ships immediately
TICKET-16 Phase 2 (real resume)
  └─ independent of TICKET-12/13/14/15 — different code surface
  └─ TASK-DD2-001 (chat initial task) is conceptually related but not blocking
```
