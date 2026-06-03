# Daily-Driver Findings Status Ledger (All Passes)
# 2026-06-01

**Why.** Four review passes produced findings CG-01…CG-17 and AG-01…AG-04 across many
docs. This is the single page that answers "where does everything stand right now" —
status, owning ticket, guard test, and one-line evidence — re-anchored against current
HEAD. When ledger and a detail doc disagree, **the ledger is authoritative for status**.

**Status values.** `FIXED` (verified in current code) · `OPEN` (live defect) ·
`OPEN(test)` (test-integrity defect — passing test hides a bug).

| ID | Sev | Status | Statement (short) | Ticket | Guard test | Evidence |
|----|:---:|:------:|-------------------|--------|-----------|----------|
| CG-01 | P0 | FIXED | REPL prints answer, branches on status | T1 | ✅ `test_chat_repl_displays_answer` | controller `:162` |
| CG-02 | P0 | FIXED | `/undo` surgical via UndoJournal | T2 | ❌ missing | controller `:182`; no `git checkout -- .` |
| CG-03(REPL) | P1 | FIXED | REPL cost accumulates | T3 | ❌ missing | controller `:168` |
| CG-04 | P1 | FIXED | compaction on real observations | T4 | ❌ missing | `chat_repl.py:581,833` |
| CG-05 | P1 | PARTIAL | shared controller — REPL only | T5/T12 | ⚠️ CG-17 | `chat_session_controller.py` |
| CG-06 | P1 | FIXED | TUI no clear-screen | T6 | — | `tui:209` |
| CG-07 | P2 | FIXED | TUI compact is real | T7 | — | `tui:712-740` |
| CG-08 | P2 | PARTIAL | undo vocabulary (TUI still git-stash) | T7/T12 | — | `tui:641` |
| CG-09 | P1 | FIXED | suspend: no branch switch, honest copy | T3b | ❌ missing | `chat_repl.py:106-119,144` |
| CG-10 | P1 | FIXED | suspend emits real audit event | T3b | ❌ missing | `chat_repl.py:129` |
| CG-11 | P1 | FIXED | TUI `/cost` accumulates via controller | T12 | ✅ `test_tui_cost_shows_session_cost` | `tui:961-962` controller tracking |
| CG-12 | P1 | FIXED | TUI adopted ChatSessionController | T12 | ✅ `test_cli_tui_surface_parity_flow` | `tui:960-962` controller usage |
| CG-13 | P2 | OPEN | controller swallows real errors as "mock" | T13 | ❌ to-write | `chat_session_controller.py:143-159` |
| CG-14 | P3 | OPEN | redundant `audit_trail` JSON field | T15 | — | `chat_repl.py:89-93` |
| CG-15 | P2 | OPEN | TUI/REPL undo diverge; REPL help stale | T12/T15 | ❌ to-write | `tui:641`; `chat_repl.py:168` |
| CG-16 | P1 | OPEN(test) | cost test injects state, masks CG-11 | T14 | itself | `test_tui.py:1140` |
| CG-17 | P1 | OPEN(test) | parity test never instantiates the TUI | T12b | itself | `test_cli_chat.py:483-552` |
| AG-01 | P1 | OPEN | `teaagent resume <repl-id>` errors | T16 | ❌ to-write | `run_store.py:143`; `chat_repl.py:130` |
| AG-02 | P1 | OPEN | `agent run --background <id>` runs id as task | T16 | ❌ to-write | `_agent.py:145` |
| AG-03 | P2 | OPEN | saved observations never rehydrated | T16 | ❌ to-write | `chat_repl.py:77-94` |
| AG-04 | P2 | OPEN | 3 inconsistent resume commands | T16 | — | `chat_repl.py:142,143,662` |

## Roll-up

- **FIXED:** 10 (CG-01/02/03-REPL/04/06/07/09/10/11/12). **PARTIAL:** 2 (CG-05/08 — REPL done,
  TUI pending). **OPEN defects:** 7 (CG-13/14/15, AG-01/02/03/04).
  **OPEN test-integrity:** 2 (CG-16, CG-17).
- **Guard-test gaps:** 5 *shipped* fixes have no named regression test (CG-02, CG-03-REPL,
  CG-04, CG-09, CG-10) — protected only by behavior, not by CI.

## The two highest-leverage moves

1. **CG-16 + CG-17** (the misleading tests) — fixing them converts the suite from
   "falsely green" to "honestly red", which is the precondition for trusting any other
   green. Do first.
2. **TICKET-12** (TUI → controller) — collapses CG-05/08/11/12/15 at once.

## Cross-references
Per-pass detail: code-grounded-ux-findings (CG-01…08), findings-second-pass (CG-09/10),
third-pass-postfix-audit (CG-11…16), agent-mode-suspension-audit (AG-01…04),
acceptance-test-catalog (CG-17, test states). Tickets: `daily-driver-backlog`.
