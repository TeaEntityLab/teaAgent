# TUI Module Risks

## Risk table

| ID | Risk | Severity | Mitigation | Upstream |
|----|------|----------|------------|----------|
| TUI-R-001 | Explicit root overwritten by saved state. | High | Add explicit-root sentinel and tests. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (state durability) |
| TUI-R-002 | Cost display diverges from run cost. | High | Use shared ledger/controller and active-path tests. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (CG-03 cost accounting; DS-01) |
| TUI-R-003 | TUI undo differs from REPL undo. | High | Label mechanism or migrate to undo journal. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (DS-05 undo semantics) |
| TUI-R-004 | TUI chat bypasses controller semantics. | Medium-high | Complete controller migration. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) |
| TUI-R-005 | Tests assert helper state only. | Medium-high | Use headless command-path fixtures. | [phase-0-trust-repair-risk-brief-2026-06-04.md](../../security/phase-0-trust-repair-risk-brief-2026-06-04.md) (test integrity) |
| TUI-R-006 | Approval prompt hides scope. | High | Reuse approval scope contract. | [risk-register-and-threat-model-2026-06-02.md](../../security/risk-register-and-threat-model-2026-06-02.md) (approval visibility; DS-12) |

## Review trigger

Review this file whenever `teaagent/tui/__init__.py` changes.
