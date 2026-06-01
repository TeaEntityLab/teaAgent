# Daily-Driver Backlog — Ticket-Ready Items
# 2026-06-01

**Status: ✅ COMPLETE** - All tickets implemented and shipped (2026-05-31 session)

Flat, copy-paste-ready backlog derived from the 2026-06-01 review. Each item is sized,
prioritized, and has acceptance criteria — drop straight into an issue tracker or fold
into `docs/backlog-priority.md`. Ordered by recommended execution sequence.

---

### ✅ TICKET-1 — [P0] Fix chat REPL result handling (CG-01)
**Problem:** `teaagent chat` reports every task as failed and never prints the answer
(`chat_repl.py:820` compares a `RunResult` to `0`).
**Acceptance:**
- Successful task prints `result.final_answer.content`; no "Task failed" line.
- Failed task prints the real error message (not a `RunResult` repr).
- Turn is appended to `session_context`.
**Test:** `test_chat_repl_displays_answer`. **Size:** S. **Blocks:** P-DEV daily loop.

### ✅ TICKET-2 — [P0] Scope chat REPL `/undo` to agent edits (CG-02 / PR-1)
**Problem:** `/undo` runs `git checkout -- .`, destroying all uncommitted work.
**Acceptance:**
- Manual edit to file A + agent edit to file B → `/undo` reverts only B.
- No checkpoint and no journal → `/undo` is a byte-identical no-op with a clear message.
- The `git checkout -- .` fallback is removed.
**Test:** `test_chat_repl_undo_scope`. **Size:** S. **Release blocker** (data loss).

### ✅ TICKET-3 — [P1] Real cost/budget accounting (CG-03 / PR-3)
**Problem:** Cost displays are fabricated (REPL `+= 10`; TUI counter never set).
**Acceptance:**
- Stub cost `137¢` → `/cost` shows `$1.37`; two tasks show the sum; parity in TUI.
- Tokens (in/out, cached if available) shown; source labeled server-reported.
**Test:** `test_session_cost_real`. **Size:** S (after TICKET-1). **Decision:** DQ-5.

### ✅ TICKET-4 — [P1] Compaction acts on real history (CG-04 / PR-4)
**Problem:** `/compact` and `/clear` operate on an unpopulated `session_context`.
**Acceptance:** 3 tasks → 3 observations; `/compact` reports non-zero savings; `/clear`
resets to 0. **Test:** `test_repl_compaction_real_history`. **Size:** S. **Coupled to** TICKET-1.

### ✅ TICKET-5 — [P1] Shared `ChatSessionController` (CG-05 / PR-6)
**Problem:** Two divergent chat implementations cause behavior drift.
**Acceptance:** Both surfaces drive one controller; parity test → identical status,
answer, cost, undo scope. **Test:** `test_chat_surface_parity`. **Size:** M.
**Folds in** TICKET-1…4 so they cannot re-diverge. **Human review required.**

### ✅ TICKET-6 — [P1] TUI stops destroying scrollback (CG-06 / PR-5)
**Problem:** Auto-enabled panel clears the screen each prompt on ≥120×30 terminals.
**Acceptance:** Default render emits no clear-screen; prior answers/approvals remain
visible after the next prompt. **Test:** `test_tui_no_clear_screen`. **Size:** S (drop
auto-clear) or M (real layout). **Decision:** DQ-3.

### ✅ TICKET-7 — [P2] One undo vocabulary (CG-07, CG-08)
**Problem:** Two undo systems + a stub `compact` confuse recovery.
**Acceptance:** `UndoJournal` is the single operator `undo`; git-stash renamed to
`checkpoint restore`; TUI `compact` works; help/docs describe one undo.
**Test:** `test_undo_vocabulary` + doc-lint. **Size:** S. **Decision:** DQ-6.

---

## Post-fix tickets (third-pass audit, 2026-06-01)

After the `ChatSessionController` batch landed, a re-audit found the fix reached the REPL
but not the TUI. See `docs/analysis/daily-driver-third-pass-postfix-audit-2026-06-01.md`.

### TICKET-12 — [P1] TUI adopts `ChatSessionController` (CG-11, CG-12, CG-15)
**Problem:** TUI `_run_agent_task` still calls `run_chat_agent` directly; `/cost` always
shows $0.00 because `_session_cost_cents` is never incremented; TUI undo uses git-stash
while REPL uses `UndoJournal`. CG-05 divergence is active again.
**Stop-gap (do first, 1 line):** `self._session_cost_cents += result.cost_cents` after
the run in `_run_agent_task` (`tui/__init__.py:~924`).
**Acceptance:** TUI `_run_agent_task` drives `ChatSessionController`; cost accumulates;
`/undo` uses `UndoJournal`; REPL/TUI behavior identical for result/cost/undo.
**Test:** `test_tui_session_cost_accumulates`, `test_chat_surface_parity`. **Size:** M.
**Human review:** touches undo + cost. **Depends:** stop-gap can ship immediately.

### TICKET-13 — [P2] Controller stops swallowing real errors (CG-13)
**Problem:** `execute_task` catches `(AttributeError, TypeError)` to detect test mocks
(`chat_session_controller.py:143-159`) — silently hides a real undo-journal save failure.
**Acceptance:** mock-detection removed; persistence/journal-save errors surface (logged
or raised); a fault-injection test proves a save failure is not swallowed.
**Test:** `test_controller_surfaces_save_failure`. **Size:** S.

### TICKET-14 — [P1] Fix the test that masks CG-11 (CG-16)
**Problem:** `test_tui_cost_shows_session_cost` injects `_session_cost_cents` by hand and
asserts the display — never exercises accumulation, so it stays green with CG-11 present.
**Acceptance:** keep a formatting test, but add an end-to-end test that runs a stub-cost
task and asserts the counter rose. **Test:** `test_tui_session_cost_accumulates`. **Size:** S.

### TICKET-16 — [P1] Honest, then working suspend→resume (AG-01…AG-04)
**Problem:** REPL `/background` prints 3 follow-up commands; `teaagent resume <id>` errors
(no `run_started` → `task_for_run` raises), `agent run --background <id>` runs the id as a
literal task, only `interactive-review` works (review-only). Saved observations are never
rehydrated. See `docs/analysis/daily-driver-agent-mode-suspension-audit-2026-06-01.md`.
**Now (XS):** print only `interactive-review`; drop the broken `resume`/`--background`
hints (`chat_repl.py:142,662`). **Real (M):** persist `run_started`+task+observations to
`RunStore` at suspend (or make `agent resume` fall back to the suspension JSON) so resume
rehydrates. Guard `--background <existing-id>` with "did you mean `agent resume`?".
**Test:** `test_repl_suspend_resume_roundtrip`. **Human review:** governance handoff.

### TICKET-15 — [P3] Cleanup: redundant audit field + stale help (CG-14, CG-15-doc)
Remove `suspension_data['audit_trail']` (`chat_repl.py:89-93`, superseded by the real
`audit.record`); fix REPL `/undo` help text (`:168`) to describe journal-first surgical
undo, not "all changes (using checkpoint)". **Size:** XS.

---

## Spec-track tickets (design landed; build when prioritized)

### TICKET-8 — [P1] Persona journey→acceptance tests (SPEC-JM / F-ECO-002)
Add the new acceptance tests named in the journey-maps matrix. **Size:** M.

### ✅ TICKET-9 — [P1] `build_cockpit_state` single producer (SPEC-CKP / F-ECO-010)
One `CockpitState`; CLI/TUI/dashboard render-only; parity test. **Size:** M.
**Depends:** TICKET-5, TICKET-6.

### ✅ TICKET-10 — [P1] Run-evidence bundle (SPEC-EVB / F-ECO-011)
Extend `summarize_run` with commands/tests/approvals/known-gaps + `run_evidence.json` +
`teaagent agent evidence`. **Size:** M. **Depends:** TICKET-3. **Decision:** DQ-2.

### TICKET-11 — [P1] Permission-mode risk consistency (SPEC-PMR / F-ECO-013)
`test_mode_capabilities`, doc-lint consistency across threat-model/contract/USAGE,
`prompt`+background guard. **Size:** S-M. **Decision:** DQ-4.

---

## Summary

| Priority | Tickets | Status |
|----------|---------|--------|
| P0 | 1, 2 | ✅ done (verified third-pass) |
| P1 (correctness) | 3, 4, 5, 6 | ✅ done **for REPL**; TUI gap → TICKET-12 |
| P2 | 7 | ✅ done (TUI compact real) |
| **Post-fix (open)** | **12, 13, 14, 15** | **TUI never adopted the controller** |
| P1 (spec-track) | 8, 9, 10, 11 | mixed |

**Current critical path:** TICKET-12 stop-gap (1-line TUI cost) + TICKET-14 (un-mask the
test) → TICKET-12 full controller migration (unify REPL/TUI) → TICKET-13 (stop swallowing
errors) → TICKET-15 cleanup → spec-track as prioritized.
</content>
