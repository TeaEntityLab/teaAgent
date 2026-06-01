# TUI Chat Parity Design Notes
# 2026-06-02

Design notes for making TUI chat match REPL chat.

## Parity targets

| Behavior | Target |
|----------|--------|
| Task submission | Same execute/refuse semantics. |
| Answer display | Same visible success/failure semantics. |
| Cost | Same ledger and formatting. |
| Budget | Same cap and display source. |
| Undo | Same journal semantics or clear mechanism labels. |
| Compact | Same session compaction semantics. |
| Approvals | Same authority model. |
| Run evidence | Same run id and audit chain. |

## Migration direction

- Use `ChatSessionController` as the shared chat owner.
- Keep TUI-specific rendering outside core chat semantics.
- Avoid a parallel TUI ledger.
- Keep tests at the surface boundary.

## Completion signal

Parity is done when a daily user can move between `teaagent chat` and TUI chat without
relearning cost, undo, result, or approval semantics.
