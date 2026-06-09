# Active Findings Status Ledger
# 2026-06-06

> **Claim class:** Current truth for daily-driver finding closure status.
>
> **Owns:** Whether CG/AG/DS review findings from the June 1–4 passes are still
> open, partially fixed, or verified closed.
>
> **Does not own:** Roadmap horizon ownership (`docs/roadmap-status.md`), ticket
> execution steps (`docs/plans/ticket-plans/index.md`), or historical review
> prose in dated analysis files.
>
> **Review trigger:** Finding closure status or new CG/AG/DS ids.
> **Last reviewed:** 2026-06-09

**Successor to:** [Daily-Driver Findings Status Ledger (2026-06-01)](daily-driver-findings-status-ledger-2026-06-01.md)

When this ledger and a dated detail doc disagree on **status**, this ledger is
authoritative. Dated detail docs remain evidence for reasoning and test names.

## Roll-up (2026-06-06)

| Bucket | Count | Notes |
| --- | ---: | --- |
| Fixed | 18 | Verified in code + named regression or acceptance tests |
| Partially fixed | 0 | — |
| Active | 0 | No daily-driver defects remain open from the June 1 review package |

## Finding rows

| ID | Priority | State | Statement | Ticket / evidence | Verification |
| --- | --- | --- | --- | --- | --- |
| CG-01 | P0 | Fixed | REPL prints answer and branches on status | TICKET-12 / controller | `test_chat_repl_displays_answer` |
| CG-02 | P0 | Fixed | `/undo` surgical via UndoJournal | TICKET-12 | `test_task002_undo_honesty.py` |
| CG-03 (REPL) | P1 | Fixed | REPL cost accumulates | TICKET-12 | `test_task003_cost_truth.py` |
| CG-04 | P1 | Fixed | Compaction on real observations | chat REPL | `chat_repl.py` compaction path |
| CG-05 | P1 | Fixed | Shared controller on CLI and TUI | TICKET-12 | `test_task001_surface_parity.py` |
| CG-06 | P1 | Fixed | TUI no clear-screen regression | TUI | `test_tui.py` |
| CG-07 | P2 | Fixed | TUI compact is real | TUI | `test_tui.py` |
| CG-08 | P2 | Fixed | Undo vocabulary aligned (journal-first) | TICKET-12 / TASK-DD2-006 | `test_task002_undo_honesty.py` |
| CG-09 | P1 | Fixed | Suspend: honest copy, no branch switch | TICKET-16 Phase 1 | suspend tests in `test_cli_chat.py` |
| CG-10 | P1 | Fixed | Suspend emits real audit event | TICKET-16 Phase 1 | suspend audit assertions |
| CG-11 | P1 | Fixed | TUI `/cost` accumulates via controller | TICKET-12 | `test_tui_cost_shows_session_cost` |
| CG-12 | P1 | Fixed | TUI adopted ChatSessionController | TICKET-12 | `test_cli_tui_surface_parity_flow` |
| CG-13 | P2 | Fixed | Controller no longer swallows errors as mock | TICKET-13 | controller isinstance checks |
| CG-14 | P3 | Fixed | Redundant suspension `audit_trail` removed | TICKET-15 | review JSON tests |
| CG-15 | P2 | Fixed | TUI/REPL undo semantics aligned | TICKET-12 / TICKET-15 | surface parity + help text |
| CG-16 | P1 | Fixed | Misleading cost state-injection test removed | TICKET-14 | active-path cost tests |
| CG-17 | P1 | Fixed | Surface parity test exercises controller path | TICKET-12 | `test_task001_surface_parity.py` |
| AG-01 | P1 | Fixed | `teaagent resume <repl-id>` round-trip | TICKET-16 Phase 2 | `test_repl_suspend_resume_roundtrip` |
| AG-02 | P1 | Fixed | Background run no longer treats id as task | TICKET-16 | background UUID rejection test |
| AG-03 | P2 | Fixed | Observations rehydrated on resume | TICKET-16 Phase 2 | suspend/resume roundtrip |
| AG-04 | P2 | Fixed | Resume command vocabulary honest | TICKET-16 Phase 1 | chat help / suspend copy |
| DS-01 | P1 | Fixed | TUI cost accumulation | TICKET-12 | `test_task003_cost_truth.py` |
| DS-08 | P1 | Fixed | Resume after REPL suspend | TICKET-16 Phase 2 | `test_repl_suspend_resume_roundtrip` |
| DS-11 | P1 | Fixed | Positional chat task forwarded to TUI | TASK-DD2-001 | `test_cli_chat.py` task forwarding |
| DS-12 | P0 | Fixed | Empty-path approval rejected | TASK-DD2-004 | `test_empty_path_globs_rejected_ds12` |
| TASK-DD2-005 | P1 | Fixed | Git sandbox lifecycle | TASK-DD2-005 plan | `tests/test_git_tools.py`, `tests/test_cli_execution.py` sandbox tests |

## Superseded June 1 rows

The June 1 ledger marked CG-13, CG-14, CG-15, AG-01..04, and several guard-test
gaps as OPEN. Those rows are **superseded** by the June 4 ticket closure pass
documented in [Ticket Execution Plans](../plans/ticket-plans/index.md) and
verified by the regression guards listed above.

## Maintenance

Update this ledger when:

- A daily-driver finding reopens or a new review pass adds a CG/AG/DS id.
- Ticket index status changes for TICKET-12..16 or TASK-DD2-* items.
- User-facing docs change recommended chat, cost, undo, or resume behavior.

Verification:

```bash
python3 scripts/validate_docs_consistency.py
python3 -m pytest tests/test_docs_consistency.py -q
```
