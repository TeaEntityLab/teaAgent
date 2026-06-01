# Daily-Driver Third-Pass Post-Fix Audit
# 2026-06-01

**Purpose.** After the maintainer landed a large batch of fixes (the
`ChatSessionController`, surgical undo, honest suspension, cost wiring in the REPL),
re-audit the *current* code to (1) confirm what is genuinely fixed, and (2) surface the
new facts and tasks created by those fixes. This supersedes the open items in
`daily-driver-code-grounded-ux-findings-2026-06-01.md` and
`daily-driver-findings-second-pass-2026-06-01.md` for the findings listed as closed.

**Method.** Re-anchored every prior `file:line` against current HEAD; read the new
`teaagent/chat_session_controller.py` in full; read `chat_repl.py` and
`tui/__init__.py` task/undo/cost paths; ran `pytest tests/test_tui.py` (104 passed).

---

## 1. Confirmed FIXED (close these out)

| ID | Was | Now | Evidence (current HEAD) |
|----|-----|-----|-------------------------|
| CG-01 | `if result != 0` on a `RunResult` | branches on `result.status`, prints `final_answer.content` | `chat_session_controller.py:162-165`; REPL `chat_repl.py:576` |
| CG-02 | `/undo` ran `git checkout -- .` (data loss) | `/undo` → `controller.undo_last_run()` → `UndoJournal.restore()` | `chat_session_controller.py:182-220`; REPL `chat_repl.py:791-801`; no `git checkout -- .` remains in file |
| CG-03 (REPL) | `+= 10` placeholder | `session_state.session_cost_cents += result.cost_cents` | `chat_session_controller.py:168`; REPL syncs `:580,832` |
| CG-04 | `/compact` on a context the loop never filled | observations appended in controller, synced to `session_context` | `chat_session_controller.py:169`; `chat_repl.py:581,833` |
| CG-06 | `\033[2J\033[H` cleared scrollback each prompt | header printed, **no clear** | `tui/__init__.py:209` ("no clear screen - CG-06 fix") |
| CG-07 | TUI `compact` advertised but a stub | real `compact_chat_history` | `tui/__init__.py:712-740` |
| CG-09 | `/background` did `git checkout -b`, never returned, "manual setup" | no branch switch (`branch_created=False`); honest copy ("suspension checkpoint, not background execution") | `chat_repl.py:105-119,144-145` |
| CG-10 | suspension wrote a JSON `audit_trail`, no real event | emits `audit.record(event_type='session_suspended', …)` | `chat_repl.py:125-136` |

`ChatSessionController` (`teaagent/chat_session_controller.py`) is the real, well-built
root-cause fix recommended as CG-05/TICKET-5. It is correct **for the REPL**.

---

## 2. NEW findings (created or revealed by the fixes)

### CG-11 — [P1] TUI session cost is still never accumulated → `/cost` and budget show $0.00
The CG-03 fix landed in the controller, which the **REPL** uses. The **TUI** does not:
`_run_agent_task` calls `run_chat_agent` directly and uses `result.cost_cents` only to
build the run-summary (`tui/__init__.py:938`). `self._session_cost_cents` is set to
`0.0` at init (`:186`) and **only ever read** (`:744,748,762,791,805`) — there is no
`+=` anywhere in the file. So in a live TUI session, `/cost` and the budget bar always
report `$0.00` regardless of spend. This is the original CG-03 bug, surviving on the
always-on surface (the surface where, per J-6, the cockpit matters most).
- **Evidence:** `grep '_session_cost_cents *+=' tui/__init__.py` → no matches.

### CG-12 — [P1, root cause] The TUI never adopted `ChatSessionController`
The controller's own docstring claims it "unifies the execution logic between CLI and
TUI surfaces" (`chat_session_controller.py:3-5,43-45`), but `tui/__init__.py` does not
import or use it — it has its own `_run_agent_task`. CG-05 is therefore **half-fixed**:
the REPL and TUI have re-diverged, and every future controller fix (cost, undo, result
handling, suspension) silently bypasses the TUI. CG-11 and CG-15 are direct
consequences. The deprecation warning at `tui/__init__.py:890` (keyword-arg
`run_chat_agent`) is a secondary symptom of the un-migrated path.

### CG-13 — [P2, data-safety smell] Controller swallows real errors as "mock detection"
`execute_task` wraps `store.logger_for_result(...)` and `undo_journal.save_to(...)` in
`try/except (AttributeError, TypeError): pass` with the comment "Audit logger is likely
a mock in tests" / "Store is likely a mock in tests" (`chat_session_controller.py:143-159`).
In production a genuine `AttributeError`/`TypeError` in either call is silently
discarded — meaning a run may not be persisted, or **an undo journal may fail to save
with no error surfaced**, quietly removing the recoverability that the CG-02 fix exists
to guarantee. Test-detection logic does not belong in the production path.

### CG-14 — [P3, clarity] Redundant `audit_trail` JSON field on suspension
`suspension_data['audit_trail']` (`chat_repl.py:89-93`) predates the CG-10 fix. Now that
a real `audit.record` event is emitted (`:129`), the JSON field is decorative and
misleading — a reader could mistake it for the governance record. Remove it.

### CG-15 — [P2] Undo mechanism now diverges *across surfaces* (CG-08 sharpened)
REPL `/undo` uses `UndoJournal` (surgical, via controller). TUI `/undo` calls
`_restore_checkpoint()`, a **git-stash**-based restore (`tui/__init__.py:641-708,812-813`).
Same command word, two different recovery models and blast radii depending on surface.
Additionally the REPL help text is now stale: `/undo  - Undo all changes (using
checkpoint)` (`chat_repl.py:168`) describes the *old* behavior; the actual path is
journal-first surgical undo with checkpoint only as fallback (`:791-800`).

### CG-16 — [P1, test integrity] A passing test masks CG-11
`test_tui_cost_shows_session_cost` (`tests/test_tui.py:1140-1145`) sets
`tui._session_cost_cents = 123.0` **by hand** and asserts the display shows `$1.23`. It
verifies formatting only and never runs a task, so it stays green while the accumulation
path (CG-11) is broken. 104 TUI tests pass with the live bug present. Tests that inject
the state they claim to verify give false confidence — this one actively hides a P1.

---

## 3. Severity & sequencing

CG-12 is the root cause (as CG-05 was); CG-11, CG-15 are its symptoms. Recommended order:

1. **CG-11 quick stop-gap** — one line: `self._session_cost_cents += result.cost_cents`
   in `_run_agent_task` after the run. Restores honest TUI cost immediately.
2. **CG-16** — add `test_tui_session_cost_accumulates` (stub adapter returning known
   `cost_cents`; assert counter rises) and fix the masking test. Do this *with* step 1
   so the fix is guarded.
3. **CG-12** — migrate `_run_agent_task` to `ChatSessionController` so CG-11/CG-15 cannot
   re-occur and the two surfaces share one truth. Folds in TUI undo (CG-15).
4. **CG-13** — replace mock-detection `except` clauses with explicit dependency
   injection / `is None` checks; let real errors surface.
5. **CG-14, CG-15-doc** — remove redundant `audit_trail`; fix REPL `/undo` help text.

## 4. Residual risks

- **R-6 (carried):** Until CG-12, any new chat behavior must be written twice or it
  diverges. CG-11 is proof the divergence is active, not theoretical.
- **R-7 (new):** CG-13's silent-swallow means an undo-journal save failure in production
  is undetectable — a recoverability gap that won't show up until a user needs undo.
- **R-8 (new):** The test suite's green status currently over-states correctness on the
  TUI surface (CG-16). Treat TUI test coverage as suspect until accumulation/undo paths
  are exercised end-to-end, not via injected state.

## 5. Cross-references
- Tickets: see new TICKET-12…TICKET-16 in `daily-driver-backlog-2026-06-01.md`.
- Prior passes: `daily-driver-code-grounded-ux-findings-2026-06-01.md` (CG-01…08),
  `daily-driver-findings-second-pass-2026-06-01.md` (CG-09/10).
- Controller: `teaagent/chat_session_controller.py`.
