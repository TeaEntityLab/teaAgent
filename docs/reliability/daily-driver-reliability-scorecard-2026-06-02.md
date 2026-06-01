# Daily-Driver Reliability Scorecard
# 2026-06-02

This scorecard rates readiness for daily use. It is intentionally conservative.

| Area | Current score | Reason | Next lift |
|------|---------------|--------|-----------|
| Audit logging | Strong | Run and tool evidence are core strengths. | Make evidence easier to inspect by run id. |
| Approval governance | Medium-strong | Approval model exists, but path scope needs hardening. | TASK-DD2-004. |
| REPL chat | Medium-strong | Controller-backed path fixed several trust bugs. | Keep parity tests. |
| TUI cockpit | Medium | Useful operational surface, but root/cost/undo caveats remain. | TASK-DD2-002 and TICKET-12. |
| TUI chat | Medium-low | Partial fixes exist, full controller parity pending. | TASK-DD2-003 and TICKET-12. |
| Agent resume | Medium-low | Review path is useful; resume continuity incomplete. | TICKET-16 Phase 2. |
| Dry-run/read-only | Medium-low | Side-effect contract needs clarification. | TASK-DD2-008. |
| Memory integrity | Medium-low | Corrupt state can be silent. | TASK-DD2-011. |
| Security boundaries | Medium | Strong intent, path containment gaps remain. | TASK-DD2-010. |

## Score meaning

- Strong: daily recommendation is reasonable.
- Medium-strong: usable with clear caveats.
- Medium: useful but needs operator awareness.
- Medium-low: do not rely on for high-trust workflows.
- Low: block daily-driver claim.

## Current readiness statement

TeaAgent is most convincing today as an audited agent harness and REPL chat tool. It is
less ready as a fully unified TUI chat cockpit until root, cost, undo, and lifecycle
parity are verified.
