# Daily-Driver Acceptance Test Catalog
# 2026-06-01

**Why.** The findings/plans name many tests as the falsifiable proof of each fix. This
catalog grounds those names against the **actual test suite** — which exist, which are
missing, and (critically) which exist but **do not test what their name claims**. It is
the falsifiability layer for the whole daily-driver package.

**Method.** `grep "def <test>" tests/` for every test named across the package; read the
bodies of the ones that exist to confirm they bite.

**Legend.** ✅ exists & bites · ⚠️ exists but weak/misleading · ❌ missing (to write).

---

## 1. Status of every named test

| Test | Guards | File | State | Note |
|------|--------|------|:-----:|------|
| `test_chat_repl_displays_answer` | CG-01 | `test_cli_chat.py` | ✅ | REPL result handling covered |
| `test_chat_surface_parity` | CG-05/CG-12 | `test_cli_chat.py` | ⚠️ | **Misleading — see CG-17.** Builds two `ChatSessionController`s and compares them; never instantiates `TeaAgentTUI`, so it does not test the real TUI surface |
| `test_tui_cost_shows_session_cost` | CG-03(TUI) | `test_tui.py` | ⚠️ | **Masks CG-11** — injects `_session_cost_cents`, asserts display (CG-16) |
| `test_chat_repl_undo_scope` | CG-02 | — | ❌ | CG-02 fix is real but has **no named guard test** |
| `test_session_cost_real` | CG-03 | — | ❌ | REPL cost accumulation unguarded by this name |
| `test_repl_compaction_real_history` | CG-04 | — | ❌ | |
| `test_tui_session_cost_accumulates` | CG-11 | — | ❌ | TICKET-14 — the test that would catch CG-11 |
| `test_controller_surfaces_save_failure` | CG-13 | — | ❌ | TICKET-13 |
| `test_background_audited_and_honest` | CG-09/10 | — | ❌ | fix landed; assert via this test |
| `test_repl_suspend_resume_roundtrip` | AG-01…03 | — | ❌ | TICKET-16 |
| `test_repl_undo_help_accurate` | CG-15-doc | — | ❌ | TICKET-15 |
| `test_controller_task_spec_forwarded` | migration MR-3 | — | ❌ | TICKET-12b |
| `test_controller_emit_answer_false_silent` | migration MR-1 | — | ❌ | TICKET-12b |
| `test_tui_undo_uses_journal` | CG-15 | — | ❌ | TICKET-12c |

## 2. New finding surfaced by this catalog

### CG-17 — [P1, test integrity] `test_chat_surface_parity` doesn't test the TUI
The test's docstring says *"CLI and TUI surfaces use the same controller (CG-05)"*, but
it constructs **two `ChatSessionController` instances** (`cli_controller`,
`tui_controller`) and calls `execute_task` on both (`test_cli_chat.py:483-552`). It never
imports or drives `TeaAgentTUI`. So it proves the controller is deterministic against
itself — **not** that the TUI uses the controller. It stays green precisely because it
avoids the code that diverges (CG-12). This is the same class as CG-16: a test whose name
over-states its coverage. A real parity test must instantiate `TeaAgentTUI` and run a
task through `_run_agent_task`, then compare to the REPL path.

## 3. What this catalog reveals

- **Two P0/P1 fixes (CG-02, CG-03-REPL) shipped without a named guard test** — they work
  today but are unprotected against regression. Add `test_chat_repl_undo_scope` and
  `test_session_cost_real`.
- **Two existing tests are misleading** (CG-16, CG-17) — they pass while the bug they
  appear to cover is live. These are higher priority than the missing tests because they
  actively suppress signal.
- **The honest-suspension fix (CG-09/10) is also unguarded** — add
  `test_background_audited_and_honest` so the no-branch-switch + real-audit-event behavior
  can't silently regress.

## 4. Recommended test-writing order

1. Fix the two misleading tests (CG-16 → split formatting/accumulation; CG-17 → drive the
   real TUI). **Highest priority — they hide live bugs.**
2. Backfill guards for shipped-but-unguarded fixes: `test_chat_repl_undo_scope`,
   `test_session_cost_real`, `test_background_audited_and_honest`.
3. Write the forward tests for open tickets (12b/c, 13, 16) *before* their code.

## 5. Cross-references
- Test-integrity detail: `daily-driver-test-integrity-audit-2026-06-01.md` (CG-16, +CG-17).
- Status of every finding: `daily-driver-findings-status-ledger-2026-06-01.md`.
- Execution detail: `daily-driver-tui-postfix-execution-sheets-2026-06-01.md`.
