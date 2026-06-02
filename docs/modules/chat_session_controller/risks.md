# chat_session_controller — Risk Vectors, Failure Modes, Edge Cases, Known Issues

## Risk Vectors

### CSC-R-001: Duplicate `handle_memory_failures`, `handle_pin`, etc. across `_chat.py` and `chat_commands.py`

- **File:lines** — `_chat.py:26–93` and `chat_commands.py:54–115`
- **Description** — Both files define `handle_memory_failures`, `handle_pin`, `handle_unpin`, `handle_pinned`, `handle_memory_clear`, `get_failure_warnings`, and `execute_shell_command`. The implementations are slightly different: `_chat.py` uses emoji in some print messages; `chat_commands.py` uses plain text. The `execute_shell_command` implementations differ in their denylist logic (executable-based vs string-pattern-based).
- **Impact** — Divergent behavior depending on which import path is used. Maintenance burden. Security risk: the older `chat_commands.py` version checks for `'rm -rf /'` as a substring, which is bypassable (e.g., `rm -rf /tmp`), while `_chat.py` uses a proper executable denylist.
- **Severity** — Medium (security difference in `execute_shell_command`).

---

### CSC-R-002: `_chat.py::run_chat_repl` uses placeholder cost (`session_cost_cents += 10`)

- **File:lines** — `_chat.py:1029`, `_chat.py:1292`
- **Description** — The legacy `run_chat_repl` in `_chat.py` adds a hardcoded `10` cents per task instead of using `result.cost_cents`. The newer `chat_repl.py::run_chat_repl` uses `ChatSessionController` which properly accumulates `result.cost_cents`. The legacy version is still imported and exported from `_chat.py`.
- **Impact** — Any code path using `_chat.py::run_chat_repl` directly (rather than through `ChatSessionController`) will always show `$0.10 * n_tasks` regardless of actual cost. This is CG-03 unresolved in the legacy path.
- **Severity** — Medium (cost display bug in legacy path).

---

### CSC-R-003: `suspend_to_background` in `_chat.py` creates a git sandbox branch on dirty workspace

- **File:lines** — `_chat.py:486–526`
- **Description** — The legacy `suspend_to_background` in `_chat.py` runs `git checkout -b suspended-{run_id}` on a dirty workspace without user confirmation. The newer version in `chat_repl.py` does NOT create a branch (warns instead). The two implementations are inconsistent.
- **Impact** — Surprise git branch creation when using the legacy code path. The new version is safer.
- **Severity** — Low (only triggered by `/background` command).

---

### CSC-R-004: `ChatSessionController` silently swallows store persistence errors

- **File:lines** — `chat_session_controller.py:143–159`
- **Description** — Both the result-store save and undo-journal save are wrapped in `try/except (AttributeError, TypeError)` with comment "Audit logger is likely a mock in tests." Real persistence failures (e.g., disk full, permission denied) would also be caught and silently ignored.
- **Impact** — Lost run history and undo journals without any user-visible error.
- **Severity** — Medium.

---

### CSC-R-005: `undo_last_run()` broad exception catch hides bugs

- **File:lines** — `chat_session_controller.py:218–219`
- **Description** — The outer `except Exception as exc` catch-all in `undo_last_run()` means any programming error (e.g., `AttributeError` on a refactored `UndoJournal`) returns `False` and outputs `[TeaAgent] Error in undo: {exc}` rather than propagating the traceback.
- **Impact** — Debugging undo failures is difficult since the exception type and full stack trace are swallowed.
- **Severity** — Low (correct behavior for users; painful for developers).

---

### CSC-R-006: `complete_symbol` / `complete_file_path` in `_chat.py` are redundant with `chat_completion.py`

- **File:lines** — `_chat.py:311–413` vs `chat_completion.py:8–110`
- **Description** — The completion functions are duplicated verbatim (same logic). `chat_repl.py` imports from `chat_completion.py`; the legacy `_chat.py` defines its own copies.
- **Impact** — Any fix to completion logic must be applied in two places.
- **Severity** — Low.

---

### CSC-R-007: `chat_repl.py::run_chat_repl` cost variable desync

- **File:lines** — `chat_repl.py:580–581`, `chat_repl.py:831–832`
- **Description** — After `controller.execute_task()`, the code syncs back:
  ```python
  session_cost_cents = int(session_state.session_cost_cents)
  ```
  This casts the float to int, losing fractional cents. The `show_effort_status()` function uses `session_cost_cents` (the local int), not `session_state.session_cost_cents` (the float). The `/cost` command in the REPL uses the local variable directly (line 670).
- **Impact** — Displayed cost is always rounded down to the nearest cent.
- **Severity** — Low.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| `execute_task()` called with `resumed_from=None` | `initial_context_extra` is not passed to `run_chat_agent` (condition at line 138) |
| `undo_last_run()` when no runs exist | `store.latest_run_with_undo()` returns `None`; outputs `Nothing to undo` |
| `execute_task()` with a mock audit that has `.path = None` | Store persistence is skipped silently (line 145: `if audit.path`) |
| `config.model` is `None` (no `/` separator) | `provider = 'gpt'`, `model_part = None` → creates default GPT adapter |
| `config.model = 'claude'` (no `/`) | Same as above: provider inferred as `'gpt'`, not `'claude'` — potential provider mismatch |

---

## Known Issues

| ID | Description | Location |
|----|-------------|----------|
| CG-03 (partial) | Legacy `_chat.py::run_chat_repl` hardcodes 10-cent cost per task | `_chat.py:1029, 1292` |
| Duplicate implementation | `handle_pin`, `handle_unpin`, `handle_memory_failures`, etc. exist in both `_chat.py` and `chat_commands.py` with subtle behavioral differences | Multiple locations |
| Provider inference bug | If `config.model = 'claude'` (no slash), provider is inferred as `'gpt'` not `'claude'` | `chat_session_controller.py:119–129` |
