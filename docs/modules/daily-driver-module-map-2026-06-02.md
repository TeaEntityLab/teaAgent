# Daily-Driver Module Map
# 2026-06-02

This map connects daily-driver risks to module docs.

| Risk area | Module docs | Primary tickets |
|-----------|-------------|-----------------|
| TUI root, cost, undo, command path | [tui/spec.md](tui/spec.md), [tui/risks.md](tui/risks.md) | TASK-DD2-001, TASK-DD2-002, TASK-DD2-003, TICKET-12 |
| Run evidence and resume | [run_store/spec.md](run_store/spec.md), [run_store/risks.md](run_store/risks.md) | TICKET-16, TASK-DD2-011 |
| Git sandbox lifecycle | [git_sandbox/spec.md](git_sandbox/spec.md), [git_sandbox/risks.md](git_sandbox/risks.md) | TASK-DD2-005 |
| Context-pack truth labels | [context_pack/spec.md](context_pack/spec.md), [context_pack/risks.md](context_pack/risks.md) | TASK-DD2-009 |
| Pinned-file containment | [pinned_file/spec.md](pinned_file/spec.md), [pinned_file/risks.md](pinned_file/risks.md) | TASK-DD2-010 |
| Existing approval/budget/chat/memory modules | Existing module directories under `docs/modules/` | TASK-DD2-004 and related tickets |

## Ownership note

Daily-driver reliability is cross-module. The TUI can display a bug that belongs to run
store, approval, memory, or git sandbox. Debug by following state ownership, not only the
surface where the user saw the symptom.
