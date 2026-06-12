# ADR 0031: Shadow Mode Exit Criteria

## Status

Proposed — 2026-06-12

**Expiry review:** 2026-09-12 (re-score whether policy/RBAC shadow mode should promote to enforce)

## Context

Sprint 2 wired policy engine and RBAC in shadow mode (log, don't enforce) as documented in:
- `teaagent/governance/h4_integration.py` (policy shadow code)
- `teaagent/runner/_approval_manager.py` (RBAC shadow code)
- Roadmap H4 rows cite WDA-002/003

Shadow mode allows production observation without enforcement risk, but lacks clear exit criteria. Without defined evidence requirements and an expiry date, "wired" quietly becomes the new "implemented but unwired" — the exact failure mode WDA-006 was designed to prevent.

## Decision

**Define** the evidence required to promote policy/RBAC from shadow to enforce mode, with an expiry date for shadow status.

### Exit Criteria

Policy/RBAC may be promoted from shadow to enforce mode only when **all** of the following evidence is satisfied:

1. **Audit trail validation**: Shadow-mode logs show zero false positives over a 30-day production window
   - Evidence: Automated analysis of audit logs showing no blocked actions that should have been allowed
   - Test: `tests/acceptance/test_policy_as_code_flow.py` with enforce-mode fixture passes

2. **Coverage completeness**: All policy rules have corresponding acceptance tests
   - Evidence: Claim-to-test traceability matrix shows 100% coverage for policy/RBAC claims
   - Test: `tests/acceptance/test_claim_traceability.py` passes for policy/RBAC section

3. **Performance impact**: Enforcement overhead stays within SLO
   - Evidence: Benchmark shows <50ms median latency for policy checks
   - Test: Performance regression gate passes with policy enforcement enabled

4. **Human review**: Security and governance owners sign off on promotion
   - Evidence: ADR acceptance with owner signatures
   - Process: PR review with explicit "Approve shadow→enforce promotion" sign-off

5. **Rollback plan**: Documented rollback path to shadow mode if issues arise
   - Evidence: Runbook entry for disabling enforcement without data loss
   - Test: Rollback procedure validated in staging environment

### Expiry

Shadow status for policy/RBAC enforcement **expires on 2026-09-12**. On expiry:

- If exit criteria are met: Promote to enforce mode via this ADR acceptance
- If exit criteria are not met: Either (a) extend shadow status with new ADR citing blocking evidence, or (b) revert shadow wiring and document gaps

### Implementation Steps for Promotion

When exit criteria are satisfied and expiry date is reached:

1. Update `teaagent/governance/h4_integration.py` to remove `shadow_mode=True` flag
2. Update `teaagent/runner/_approval_manager.py` to enable RBAC enforcement
3. Add acceptance test for enforce-mode behavior
4. Update roadmap H4 rows to mark policy/RBAC as "enforce" status
5. Accept this ADR with expiry date achieved

## Consequences

- Positive: Clear, evidence-based promotion path prevents "permanent shadow" anti-pattern
- Positive: Expiry date forces explicit decision-making (promote, extend, or revert)
- Negative: Requires additional validation work before enforcement can ship
- Negative: May delay enforcement if exit criteria are difficult to satisfy

## References

- [Work Direction Decomposition (WDA-002/003)](../plans/work-direction-decomposition-2026-06-10.md)
- [Intent Verification Delta (V3)](../analysis/intent-verification-delta-2026-06-12.md)
- ADR 0029 (consensus validation deferral precedent)
- `docs/architecture/control-loop-ownership-map-2026-06-11.md`