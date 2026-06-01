# TASK-DD2-003: Make TUI Cost Ledger Authoritative

**Priority:** P1
**Status:** Partially fixed; verify and complete
**Primary files:** `teaagent/tui/__init__.py`, `teaagent/chat_session_controller.py`, `tests/test_tui.py`

## Problem

The working tree now includes a stop-gap that adds `result.cost_cents` to the TUI
session cost counter. That reduces the false-zero risk, but the TUI still calls
`run_chat_agent` directly and does not yet use `ChatSessionController` as the single
chat ledger owner.

## Scope

- Keep or verify the stop-gap so `/cost` stops showing false zero.
- Move TUI chat cost state toward `ChatSessionController`.
- Ensure `/cost`, `/budget`, cockpit budget display, and run summary agree.
- Remove formatter-only tests that inject the state they claim to verify.

## Acceptance criteria

- Two stubbed TUI tasks with `cost_cents=137` show `$2.74` session cost.
- Budget display reads the same ledger as `/cost`.
- REPL and TUI chat use the same cost semantics.
- User-facing known-issues docs are updated only after tests pass.

## Verification

```bash
python3 -m pytest tests/test_tui.py -k cost
python3 -m pytest tests/acceptance/test_cost_tracking_flow.py
```

## Risks

- A one-line stop-gap can hide deeper controller drift.
- Tests can accidentally prove only the formatter.
- Budget cap enforcement and budget display can diverge.
