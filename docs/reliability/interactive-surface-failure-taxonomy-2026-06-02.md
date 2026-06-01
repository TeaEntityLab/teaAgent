# Interactive Surface Failure Taxonomy
# 2026-06-02

This taxonomy helps classify bugs in TUI, chat, and agent mode.

## Failure classes

| Class | Description | Example |
|-------|-------------|---------|
| Silent no-op | Input accepted but no meaningful action. | Positional chat task dropped. |
| Decorative state | UI shows a value not wired to runtime truth. | TUI false zero cost. |
| Lifecycle drift | Words do not match runtime state. | Background text for suspended work. |
| Scope ambiguity | User cannot know authority or recovery scope. | Approval without exact path. |
| State override | Stored state beats explicit user intent. | Saved TUI root overwrites CLI root. |
| Evidence gap | Claim cannot be traced to audit/test proof. | Final answer says verified without run evidence. |
| Stale path | Tests or docs target unused implementation. | Old chat REPL path. |
| Silent degradation | Corrupt local state disappears from view. | Bad run JSON filtered out. |

## Severity guide

- P0: Can modify wrong files, overgrant authority, lose data, or lie about spend.
- P1: Misleads daily use or blocks reliable recovery.
- P2: Causes confusion, maintainability drag, or stale docs.

## Classification rule

Classify by user harm first, internal cause second.
