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

| Priority | Tickets | Total size |
|----------|---------|-----------|
| P0 | 1, 2 | S + S |
| P1 (correctness) | 3, 4, 5, 6 | mostly S, one M |
| P2 | 7 | S |
| P1 (spec-track) | 8, 9, 10, 11 | mostly M |

**Critical path to a trustworthy daily driver:** TICKET-1 → TICKET-2 (ship now) →
TICKET-5 (unify) → TICKET-3/4/6 (fold in) → spec-track as prioritized.
</content>
