# ADR 0029: Consensus Validation Deferred Behind Approval Queue

## Status

Accepted — 2026-06-10

**Expiry review:** 2026-12-10 (re-score whether `consensus_validation` should gate destructive actions)

## Context

Horizon H4 delivered `teaagent/consensus_validation.py` (~600 lines) with passing
tests but no production import path (ENG-R1). Sprint 2 wired policy engine and
RBAC in shadow/enforce mode. Consensus validation overlaps with:

- Existing centralized subagent approval queue (ADR 0022)
- Federated swarm consensus in `teaagent/consensus.py` (ADR 0019)

Shipping a third consensus surface without wiring invites doc⇄reality drift.

## Decision

**Defer** wiring `consensus_validation` into the destructive-action path until
2026-12-10. Until then:

1. `consensus_validation` remains labeled `experimental — unwired`.
2. Destructive actions continue to flow through the existing approval queue and
   JIT approval coordinator — no duplicate consensus gate.
3. WDA-006 acceptance is met by this ADR plus the wiring validator watch-list.

## Consequences

- Positive: avoids parallel consensus systems; Sprint 2 scope stays bounded.
- Negative: multi-agent consensus claims must not cite `consensus_validation` as live.
- Follow-up: on expiry, choose **wire behind approval queue** or **delete/quarantine**
  with import-graph evidence.

## References

- [Work Direction Decomposition (WDA-006)](../plans/work-direction-decomposition-2026-06-10.md)
- [Engineering Critique Refresh (ENG-R1)](../analysis/engineering-critique-refresh-2026-06-10.md)
- ADR 0019, ADR 0022
