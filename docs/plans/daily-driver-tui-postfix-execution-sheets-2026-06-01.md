# TUI Post-Fix Execution Sheets (TICKET-12…15)
# 2026-06-01

**Purpose.** Make the third-pass tickets executable by a developer/agent without
re-deriving context — exact files, line anchors, the change, and a falsifiable
Definition-of-Done with the test name. Mirror of
`daily-driver-execution-readiness-2026-06-01.md` Part 2, for the post-fix backlog.

**Pre-flight (run once before starting):**
- [ ] Re-anchor every `file:line` below against current HEAD (they drift).
- [ ] Confirm `ChatSessionController.execute_task` / `SessionState` API unchanged.
- [ ] `pytest tests/test_tui.py -q` green *before* you start (baseline = 104 passed).
- [ ] Write each test first; it must fail against current code (proves it bites).

**DoD for every ticket:** new test(s) green · `ruff` clean · `mypy` clean · manual smoke
(`teaagent tui`, `teaagent chat`) shows corrected behavior · no acceptance regression.

---

## TICKET-12 — TUI adopts `ChatSessionController` (CG-11, CG-12, CG-15)

**Sub-step 12a — cost stop-gap (ship first, independent):**
- **File:** `tui/__init__.py`, in `_run_agent_task` after `store.logger_for_result(...)`
  (~`:924`).
- **Change:** `self._session_cost_cents += result.cost_cents`.
- **DoD:** [ ] stub adapter returning `cost_cents=137` → after one task `/cost` shows
  `$1.37` [ ] second task accumulates [ ] `test_tui_session_cost_accumulates` green.

**Sub-step 12b — controller delegation:**
- **Controller change (`chat_session_controller.py`):** add `task_spec: Optional[str]=None`
  (forward to `run_chat_agent`) and `emit_answer: bool=True` (skip `:162-165` when False).
  Additive, REPL default unchanged.
- **TUI change:** replace `run_chat_agent(...)` (`:890-923`) with
  `self._controller.execute_task(task, config=cfg, adapter=adapter, audit=audit,
  undo_journal=undo_journal, task_spec=task_spec, initial_observations=...,
  resumed_from=..., emit_answer=False)`. Keep `:924-970` rendering. Make
  `self._session_cost_cents` a property over `controller.session_state.session_cost_cents`
  (or drop it and read the controller).
- **DoD:** [ ] TUI no longer calls `run_chat_agent` directly (deprecation warning gone)
  [ ] no double-printed answer [ ] `test_chat_surface_parity` green [ ] run-summary +
  JSON mode unchanged [ ] cost reads from controller.

**Sub-step 12c — TUI `/undo` via journal:**
- **File:** `_handle_undo` (`:812-813`).
- **Change:** call `self._controller.undo_last_run()`; keep `_restore_checkpoint`
  reachable only as an explicit `checkpoint restore` verb.
- **DoD:** [ ] TUI `/undo` restores only run-touched files (not unrelated manual edits)
  [ ] `test_tui_undo_uses_journal` green. **Human review (touches user data).**

---

## TICKET-13 — Controller stops swallowing real errors (CG-13)

- **File:** `chat_session_controller.py:143-159` (the two
  `except (AttributeError, TypeError): pass` blocks).
- **Change:** remove mock-detection. Make store/audit injected dependencies (already
  params) and check `is None` explicitly; let genuine errors propagate or log+re-raise.
  For tests, pass real temp-dir stores or explicit fakes, not "catch the exception".
- **DoD:** [ ] a forced `undo_journal.save_to` failure surfaces (not silent)
  [ ] `test_controller_surfaces_save_failure` green [ ] existing controller tests still
  pass with real/explicit fakes. **Size:** S.

---

## TICKET-14 — Un-mask the cost test (CG-16)

- **File:** `tests/test_tui.py:1140-1145` (`test_tui_cost_shows_session_cost`) and the
  sibling injectors at `:1132`.
- **Change:** keep one *formatting* test (inject value, assert `$X.XX`) clearly named
  `test_tui_cost_display_formatting`. Add `test_tui_session_cost_accumulates`: build a
  TUI with a stub `adapter_factory` whose result carries a known `cost_cents`, run a
  task, assert `_session_cost_cents` (or controller state) rose by that amount.
- **DoD:** [ ] new accumulation test FAILS on pre-12a code (proves it bites) [ ] passes
  after 12a [ ] formatting test retained and renamed. **Do together with 12a.**

---

## TICKET-15 — Cleanup (CG-14, CG-15-doc)

- **Redundant audit field:** delete `suspension_data['audit_trail']`
  (`chat_repl.py:89-93`); the real event is `audit.record('session_suspended', …)`
  (`:129`).
- **Stale help:** `chat_repl.py:168` — change `/undo  - Undo all changes (using
  checkpoint)` to describe journal-first surgical undo with checkpoint fallback.
- **DoD:** [ ] no `audit_trail` JSON key remains [ ] help text matches `:791-800` behavior
  [ ] `test_repl_undo_help_accurate` (assert help string) green. **Size:** XS.

---

## Recommended order

1. **12a + 14** together (cost honesty + the test that guards it) — smallest, highest trust.
2. **13** (stop hiding errors) — independent, small.
3. **12b** (controller delegation) — the unification; **human review**.
4. **12c** (undo via journal) — folds CG-15; **human review**.
5. **15** (cleanup) — trivial, last.

## Cross-references
- Findings: `daily-driver-third-pass-postfix-audit-2026-06-01.md`.
- Design: `daily-driver-tui-controller-migration-spec-2026-06-01.md`.
- Backlog: `daily-driver-backlog-2026-06-01.md` (TICKET-12…15).
