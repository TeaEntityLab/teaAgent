# TUI Root State Contract
# 2026-06-02

## Contract

When a user passes an explicit root to the TUI, that root is authoritative for the
session.

## Rules

- Explicit CLI root wins over saved state.
- Saved state may restore root only when no explicit root was supplied.
- The active root must be visible in status/header output.
- Any root change must be logged or displayed.

## Acceptance

- Saved state with root A cannot overwrite `teaagent tui --root B`.
- Default launch without explicit root may restore saved root if documented.
- Tests cover both explicit and default behavior.

## User risk

Wrong root means wrong files, wrong approvals, wrong run evidence, and possible data
loss. This is a P0/P1 trust boundary depending on write authority.
