# TASK-DD2-002 — Keep Explicit TUI Root Explicit
**Priority:** P1 | **Size:** S | **Phase:** A (Stop First-Hour Trust Failures)

---

## Root Cause Analysis

`TeaAgentTUI._load_tui_state()` at
[`teaagent/tui/__init__.py:1107`](../../../teaagent/tui/__init__.py) unconditionally
restores `self.root` from the saved state file:

```python
self.root = Path(data.get('root', str(self.root))).resolve()
```

This runs during `tui.run()` at `__init__.py:326` — after the constructor sets
`self.root = Path(root).resolve()` from the CLI argument (`:146`), but before
any user interaction. If the user previously ran `teaagent tui` in
`~/project-A`, the saved state contains `root: /home/user/project-A`. On the
next invocation from `~/project-B`, `_load_tui_state` silently moves the active
root to project-A.

The only guard is `_chat_explicit` for the `chat` flag (`:1119`) — `root` has no
equivalent guard.

**Result:** `cd ~/project-B && teaagent tui` silently works on project-A. The
user has no visibility into which root is active until they inspect state output
or notice wrong file paths in results.

---

## Acceptance Criteria

1. CLI/constructor-supplied root is never overridden by saved state.
   - `TeaAgentTUI(root='/B')` → after `_load_tui_state()` → `self.root == /B`.
2. When no explicit root is provided (default `'.'` resolves to CWD), the
   saved root is still applied as before.
3. `teaagent tui /path/to/project` prints the active root in the header or
   status line so the user can verify it.
4. A test covers the explicit-root-wins case and the no-root-uses-saved case.

---

## Test Strategy

### New tests

| Test | File | What it asserts |
|------|------|-----------------|
| `test_tui_explicit_root_not_overridden` | `tests/test_tui.py` | State file has root=A, construct TUI with root=B, call `_load_tui_state`, assert `self.root == /B` |
| `test_tui_no_explicit_root_restores_saved` | same | No explicit root (using default `.`), state has root=A, assert root=A after load |
| `test_tui_header_shows_active_root` | same | Output of `_print_header` contains the root path |

### Regression
All 104 existing TUI tests must continue to pass.

---

## Implementation Plan

### Step 1 — Track whether root was explicitly given

In `TeaAgentTUI.__init__` (`tui/__init__.py:141`), add a flag mirroring
`_chat_explicit`:

```python
# constructor signature gets a new sentinel or a bool flag:
def __init__(self, ..., root: str | Path = '.', ...):
    _cwd = Path('.').resolve()
    self._root_explicit: bool = Path(root).resolve() != _cwd
    self.root = Path(root).resolve()
```

A better approach: `run_tui` can pass `root_explicit=True` when the caller
provided an explicit path (i.e., CLI arg was not the default `.`). This avoids
fragile CWD comparison.

Simplest correct approach — mirror `_chat_explicit`:

```python
# In __init__:
self._root_explicit: bool = False
self.root = Path(root).resolve()
```

`run_tui` sets `tui._root_explicit = True` when `root` differs from `'.'`.

### Step 2 — Guard in `_load_tui_state`

```python
# tui/__init__.py:1107
if not self._root_explicit:
    self.root = Path(data.get('root', str(self.root))).resolve()
```

### Step 3 — Print root in header

In `_print_header` (`tui/__init__.py:1175`):

```python
self.output_fn(f'Root: {self.root}')
```

`_print_header` already calls `self.output_fn(f'TeaAgent TUI {__version__}')`;
add root on the next line.

### Step 4 — Expose via `run_tui`

```python
def run_tui(*, root: str | Path = '.', ...):
    tui = TeaAgentTUI(..., root=root)
    tui._root_explicit = str(root) != '.'
    ...
```

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Users relying on "last root is restored" even when they pass a path explicitly | Low | Current behavior is a bug, not a feature; guard is conservative |
| CWD comparison is path-sensitive (symlinks, case) | Low | Use `Path.resolve()` throughout for normalization |
| `_root_explicit` flag is bypassed if `TeaAgentTUI` is constructed directly in tests | Low | Tests that construct TUI directly always have an explicit root; set the flag in tests |

---

## Dependency Graph

```
TASK-DD2-002 (this)
  └─ co-ships with TASK-DD2-001 (initial task fires before _load_tui_state
       in the REPL loop, but both touch the run() entry; safer to land together)
  └─ independent of TICKET-12/13/14/15/16
```

No blocking dependencies; can ship immediately.
