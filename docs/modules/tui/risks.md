# TUI Module Risks

## Risk table

| ID | Risk | Severity | Mitigation |
|----|------|----------|------------|
| TUI-R-001 | Explicit root overwritten by saved state. | High | Add explicit-root sentinel and tests. |
| TUI-R-002 | Cost display diverges from run cost. | High | Use shared ledger/controller and active-path tests. |
| TUI-R-003 | TUI undo differs from REPL undo. | High | Label mechanism or migrate to undo journal. |
| TUI-R-004 | TUI chat bypasses controller semantics. | Medium-high | Complete controller migration. |
| TUI-R-005 | Tests assert helper state only. | Medium-high | Use headless command-path fixtures. |
| TUI-R-006 | Approval prompt hides scope. | High | Reuse approval scope contract. |

## Review trigger

Review this file whenever `teaagent/tui/__init__.py` changes.
