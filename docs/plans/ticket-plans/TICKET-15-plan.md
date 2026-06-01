# TICKET-15 — Cleanup: Redundant Audit Field + Stale Help Text
**Priority:** P3 | **Size:** XS | **CG Findings:** CG-14, CG-15-doc

---

## Root Cause Analysis

### CG-14 — Redundant `audit_trail` in suspension JSON
`suspend_to_background` at
[`teaagent/cli/_handlers/chat_repl.py:89-93`](../../teaagent/cli/_handlers/chat_repl.py)
writes a `'audit_trail'` key into the suspension JSON:

```python
'audit_trail': {
    'suspension_time': __import__('time').time(),
    'original_mode': 'repl',
    'transition_type': 'keyboard_to_robot',
},
```

This predates the CG-10 fix (lines 125-136), which now emits a real
`audit.record(event_type='session_suspended', ...)`. The JSON field is now
decorative. A reader inspecting suspension files could mistake it for the
governance audit record; it is not — the real record is in the RunStore audit
log. Worse, `_agent.py:1279-1282` in `interactive-review` uses
`suspension_data.get('audit_trail', {})` when building the review summary,
perpetuating the false signal.

### CG-15-doc — Stale REPL `/undo` help text
`print_chat_help` (or the help string) in
[`teaagent/cli/_handlers/chat_repl.py`](../../teaagent/cli/_handlers/chat_repl.py)
contains:

```
/undo  - Undo all changes (using checkpoint)
```

Since CG-02, `/undo` calls `controller.undo_last_run()` → `UndoJournal.restore()`
(journal-first, surgical). The checkpoint is only a fallback. The help text
describes the old destructive behavior.

Also relevant: TUI help at `tui/__init__.py:110`:
```
undo  Undo all changes (using checkpoint — use teaagent agent undo for advanced).
```
This will be updated by TICKET-12; listed here for completeness.

---

## Acceptance Criteria

1. `suspension_data` dict written by `suspend_to_background` does not contain
   an `'audit_trail'` key.
2. `_agent.py:1279-1282` (review summary builder) does not reference
   `suspension_data.get('audit_trail')` for governance purposes.
3. REPL `/undo` help text reads: `undo last agent edit (journal-first)` or
   equivalent accurate description.
4. A doc-lint or snapshot test prevents the stale text from returning.
5. No behavior change — only data field removal and string update.

---

## Test Strategy

### Snapshot / assertion tests

```python
def test_suspension_data_no_audit_trail():
    """Suspension JSON must not contain the redundant audit_trail field."""
    with patch('teaagent.cli._handlers.chat_repl.RunStore'), \
         patch('subprocess.run', ...):
        run_id = suspend_to_background(config, {}, set())
    data = json.loads((root / f'.teaagent/suspension-{run_id}.json').read_text())
    assert 'audit_trail' not in data

def test_chat_help_undo_text_accurate():
    """REPL /undo help text must not say 'using checkpoint'."""
    output = []
    print_chat_help(output_fn=output.append)  # or capture stdout
    full_text = '\n'.join(output)
    assert 'checkpoint' not in full_text.lower() or 'fallback' in full_text.lower()
```

---

## Implementation Plan

### Step 1 — Remove `audit_trail` from `suspend_to_background`

In `chat_repl.py:89-93`, delete the `'audit_trail'` key from
`suspension_data`:

```python
# Before:
'audit_trail': {
    'suspension_time': __import__('time').time(),
    'original_mode': 'repl',
    'transition_type': 'keyboard_to_robot',
},

# After: (key removed entirely)
```

### Step 2 — Remove reference in `_agent.py` review builder

Find `suspension_data.get('audit_trail', {})` at `_agent.py:~1282` and
replace with a comment or the real audit log reference:

```python
# audit_trail was a pre-CG-10 placeholder; real governance record is in RunStore
```

Or, if the field was used to populate a display field, replace with an explicit
"(recorded via audit log)" string.

### Step 3 — Fix REPL `/undo` help text

In `print_chat_help` (`chat_repl.py:150+`), update:

```
/undo  - Undo last agent edit (journal-first; fallback to checkpoint).
```

### Step 4 — Add snapshot tests (see Test Strategy)

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Existing code reads `audit_trail` from saved suspension files | Low | `interactive-review` builder at `_agent.py:1282` — handle in Step 2 |
| Users have suspension files with `audit_trail` on disk | Very low | Old files are still valid JSON; only the new write path changes |
| Help text change breaks a snapshot test | Low | Update the snapshot in the same commit |

---

## Dependency Graph

```
TICKET-15 (this) — no upstream dependencies
  └─ ships after TICKET-12 if TUI help text is also updated in that ticket
  └─ independent of TICKET-13, TICKET-14, TICKET-16
```

XS change; can ship at any time.
