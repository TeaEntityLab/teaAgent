# Daily-Driver Review — End-to-End Traceability Matrix
# 2026-06-01

One table that traces each finding through to its fix, test, the community theme it
closes, the ecosystem gap it touches, and the risk it retires. If a row has a hole, the
work is incomplete.

## Findings → fix → test → theme → gap → risk

| Finding | Evidence (`file:line`) | Fix (PLAN) | Acceptance test | Survey theme | Eco gap | Risk retired |
|---------|------------------------|------------|-----------------|--------------|---------|--------------|
| CG-01 | `chat_repl.py:820` | P0-1 | `test_chat_repl_displays_answer` | UX-F4, UX-F5 | — | PR-2 |
| CG-02 | `chat_repl.py:418,789-799` | P0-2 | `test_chat_repl_undo_scope` | UX-F4 | — | PR-1 |
| CG-03 | `chat_repl.py:563,825`; `tui:184` | P1-1 | `test_session_cost_real` | UX-F1, UX-F6 | — | PR-3 |
| CG-04 | `chat_repl.py:564` | P1-2 | `test_repl_compaction_real_history` | UX-F3 | — | PR-4 |
| CG-05 | `chat_repl.py` vs `tui/__init__.py` | P1-3 | `test_chat_surface_parity` | — | F-ECO-010 | PR-6 |
| CG-06 | `tui:205,189` | P1-4 | `test_tui_no_clear_screen` | UX-F3 | — | PR-5 |
| CG-07 | `tui:103,666` | P2-1 | (part of `test_undo_vocabulary`) | UX-F3 | — | — |
| CG-08 | `tui:76,108` | P2-1 | `test_undo_vocabulary` | UX-F4 | — | — |

## Design specs → gap → dependency → persona served

| Spec | Closes gap | Depends on | Primary persona | Acceptance anchor |
|------|-----------|-----------|-----------------|-------------------|
| SPEC-JM (journey maps) | F-ECO-002 | findings (blocking steps) | P-DEV, P-OPS | journey→acceptance matrix |
| SPEC-CKP (cockpit) | F-ECO-010 | P1-3, P1-4 | P-DEV, P-OPS | `test_cockpit_state_single_source` |
| SPEC-EVB (evidence bundle) | F-ECO-011 | P1-1 (truthful cost) | P-SEC, P-OPS | `test_evidence_files_changed_from_journal` |
| SPEC-PMR (risk table) | F-ECO-013 | — | P-SEC | `test_mode_capabilities` |

## Survey theme → grounded by → status

| Theme (May-31) | Grounded by | Closed when |
|----------------|-------------|-------------|
| UX-F1 rate/cap surprises | CG-03 | P1-1 ships |
| UX-F3 context rot / rendering | CG-04, CG-06, CG-07 | P1-2 + P1-4 + P2-1 |
| UX-F4 silent/irreversible | CG-01, CG-02, CG-08 | P0-1 + P0-2 + P2-1 |
| UX-F5 first 5 minutes | CG-01 | P0-1 |
| UX-F6 cost unpredictability | CG-03 | P1-1 |
| UX-F7 trust under autonomy | (governance baseline) | PMR + EVB legibility |
| F-ECO-010 cockpit parity | CG-05 | P1-3 + SPEC-CKP |

## Coverage holes (deliberately empty cells)

- CG-07 has **no standalone test** — it is verified as part of `test_undo_vocabulary`
  (P2-1). Acceptable: it's a help-text/stub fix folded into the consolidation work.
- CG-01–CG-04, CG-06 close survey themes but touch **no ecosystem gap** — they are
  correctness bugs, not ecosystem-fit gaps. Expected.
- UX-F2 (autonomous changes without permission) and UX-F8 (IDE lock-in) are **not**
  grounded by any 2026-06-01 finding — they are covered by existing governance and are
  out of this review's scope (chat/TUI correctness). Noted, not a hole.

## Decisions that gate rows

| Row affected | Gated by decision |
|--------------|-------------------|
| P1-4 size | DQ-3 |
| SPEC-EVB scope | DQ-2 |
| SPEC-PMR background row | DQ-4 |
| P1-1 cost source | DQ-5 |
| P2-1 undo rename | DQ-6 |

## How to read this matrix

A finding is "done" only when its **entire row** is satisfied: fix merged, test green,
theme demonstrably closed. Use this as the review checklist at release time.
</content>
