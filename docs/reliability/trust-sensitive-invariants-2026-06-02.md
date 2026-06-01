# Trust-Sensitive Invariants
# 2026-06-02

These invariants should be protected by tests, manual smoke, and docs.

## Invariants

| ID | Invariant | Failure impact |
|----|-----------|----------------|
| INV-001 | A submitted task executes or is rejected visibly. | Silent no-op. |
| INV-002 | Explicit root wins over saved state. | Wrong repository work. |
| INV-003 | Cost display is real or marked unknown. | Spend confusion. |
| INV-004 | Approval scope is exact and visible. | Overbroad authority. |
| INV-005 | Undo names its mechanism and scope. | Manual work loss. |
| INV-006 | Run id maps to durable evidence. | No audit continuity. |
| INV-007 | Resume restores task and observations. | Fake continuity. |
| INV-008 | Read-only means no hidden writes or explicit initialization. | Trust break. |
| INV-009 | Corrupt state is visible as degraded health. | False clean cockpit. |
| INV-010 | Tests drive active user paths. | False confidence. |

## Review rule

Any PR touching these invariants needs:

- Path-level tests.
- Docs update if user behavior changes.
- Manual smoke for terminal-visible behavior.
- Human review for approval, root, undo, cost, or sandbox changes.
