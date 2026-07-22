# ADR 0029: Consensus Validation Deferred Behind Approval Queue

## Status

Closed — Option D executed 2026-07-22

**Pre-deletion recovery anchor:** `4fde92f` (`docs: preserve consensus validation intent before deletion`)

## Context

Horizon H4 delivered `teaagent/consensus_validation.py` (~600 lines) with passing
tests but no production import path (ENG-R1). Sprint 2 wired policy engine and
RBAC in shadow/enforce mode. Consensus validation overlaps with:

- Existing centralized subagent approval queue (ADR 0022)
- Federated swarm consensus in `teaagent/consensus.py` (ADR 0019)

Shipping a third consensus surface without wiring invites doc⇄reality drift.

## Decision

ADR-0029 originally deferred wiring `consensus_validation` into the
destructive-action path until 2026-12-10. The owner resolved that expiry
direction early on 2026-07-22: **delete/quarantine** the unwired validation
module rather than wire it behind the approval queue.

Destructive actions continue to flow through the existing approval queue and
JIT approval coordinator. TeaAgent must not cite `consensus_validation` as live;
the runtime surface is deleted, and any future revival must recover it from git
history and pass a new owner/governance decision.

## Consequences

- Positive: avoids parallel consensus systems; Sprint 2 scope stays bounded.
- Negative: multi-agent consensus claims must not cite `consensus_validation` as live.
- Follow-up: on expiry, choose **wire behind approval queue** or **delete/quarantine**
  with import-graph evidence.

## Owner Disposition (2026-07-22)

Owner-ratified in the 2026-07-22 direction-review session: **delete/quarantine**
`consensus_validation` rather than wire it. Basis: zero production importers
(only a legacy path alias in `teaagent/_compat_modules.py` before this
execution); destructive actions already flow through the approval queue (ADR
0022) and swarm consensus (ADR 0019). Option D is now executed: the module,
legacy shim alias, wiring watch-list row, and tests that pinned the deleted
runtime surface were removed. The historical feature inventory and recovery
commands remain in the disposition spec.

Preservation requirement before deletion: keep the feature intent, symbol-level
inventory, wire-blockers, and git recovery commands in
`../specs/consensus-validation-disposition-spec-2026-07-11.md` §2. Deletion may
remove runtime files and tests, but it must not remove the historical record
needed to recover or evaluate the design from git history.

## References

- [Work Direction Decomposition (WDA-006)](../plans/work-direction-decomposition-2026-06-10.md)
- [Engineering Critique Refresh (ENG-R1)](../analysis/engineering-critique-refresh-2026-06-10.md)
- ADR 0019, ADR 0022
