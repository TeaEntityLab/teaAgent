# Daily-Driver Verification Backlog
# 2026-06-02

Backlog of verification work created by the June 2 doc passes.

## P0/P1 tests

| ID | Test | Ticket |
|----|------|--------|
| VB-001 | Explicit TUI root beats saved root. | TASK-DD2-002 |
| VB-002 | `teaagent chat <task>` runs or refuses visibly. | TASK-DD2-001 |
| VB-003 | TUI cost increments through active task path. | TASK-DD2-003 |
| VB-004 | Approval missing path is rejected for write tools. | TASK-DD2-004 |
| VB-005 | Pinned file rejects absolute, parent, and symlink escape. | TASK-DD2-010 |
| VB-006 | Dry-run does not write hidden state or announces it. | TASK-DD2-008 |
| VB-007 | Corrupt run/memory state appears as degraded health. | TASK-DD2-011 |
| VB-008 | Resume refuses clearly when task context is absent. | TICKET-16 |

## P2 tests

| ID | Test | Ticket |
|----|------|--------|
| VB-009 | Failure-card unrelated common words do not inject warning. | TASK-DD2-012 |
| VB-010 | Docs current-status links exist. | TASK-DD2-014 |
| VB-011 | Help text contains no stale detach/background promise. | TASK-DD2-006 |

## Manual smoke

Manual smoke remains required for:

- Terminal rendering.
- Approval comprehension.
- Undo confidence.
- Resume/review clarity.
- Cost display trust.
