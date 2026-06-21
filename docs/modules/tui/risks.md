# TUI Module Risks

## Risk table

| ID | Risk | Severity | Current status | Guard | Upstream |
|----|------|----------|----------------|-------|----------|
| TUI-R-001 | Explicit root overwritten by saved state. | High | Mitigated; explicit root wins. | Explicit-root sentinel and path tests. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (state durability) |
| TUI-R-002 | Cost display diverges from run cost. | High | Mitigated; shared controller ledger is active. Provider usage availability remains an external limit. | Active-path cost and budget tests. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (CG-03 cost accounting; DS-01) |
| TUI-R-003 | TUI undo differs from REPL undo. | High | Mitigated; both use the run undo journal and TUI has no global fallback. | `tests/tui/test_tui_undo_scope.py`. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (DS-05 undo semantics) |
| TUI-R-004 | TUI chat bypasses controller semantics. | Medium-high | Mitigated; task execution delegates to `ChatSessionController`. | Surface-parity and command-path tests. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) |
| TUI-R-005 | Tests assert helper state only. | Medium-high | Mitigated for known daily-driver paths; monitor new commands. | Headless command-path fixtures. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) (test integrity) |
| TUI-R-006 | Approval prompt hides scope. | High | Mitigated; empty path scope is rejected. | Approval visibility and empty-scope tests. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (approval visibility; DS-12) |

## Review trigger

Review this file whenever `teaagent/tui/`, `teaagent/chat_session_controller.py`, or TUI
approval routing changes.
